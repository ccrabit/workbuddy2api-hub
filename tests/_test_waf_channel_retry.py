"""渠道校验 400（code 11128）：换一个号再试，别让抽样判定打死整轮。

线上现场（2026-10-27 22:28，设备 workbuddy2api.log）：

    22:28:39  chat: msgs=95 effort=high stream=True -> 400 (408ms)
              400 body: {"code":11128,"msg":"Illegal API invocation from an
                        unapproved channel","displayMsg":{"en":"Request
                        blocked. Please send it again"}}
    22:28:40  chat: msgs=95 effort=high stream=True -> 200 acct=7e54d1a9

同一形状、同一秒，一条被拒一条通过 —— 微信上游的渠道校验是**抽样**判定，不是
确定性的内容指纹。上游自己的文案就是「Please send it again」。

旧实现里 400 一律原样透传（见 open_upstream 的 400 分支），于是一次抽样判定
就把整轮对话打死，而隔壁账号两条街外就能服务。这里钉住修法：

  1. 400 里 code=11128 → 换一个账号重试，最多 WB_WAF_RETRY_ATTEMPTS（默认 3）次，
     每次换号前按 WAF_RETRY_DELAYS 退避（真机 1.3 秒内连打三次全被拒，采样点
     根本没换）；
  2. 换号不记账：被拒的账号既不加 fails 也不进冷却（它没做错什么）；
  3. 预算用完仍失败、且提示模式是 passthrough/append → 只借这一条请求换成中性
     系统提示再试一次（自定义提示不动，进程级降级窗口立刻复位，不波及后续请求）；
  4. 仍失败 → 把原始 400 交回去，且正文对 HTTP handler 仍可读；
  5. 每次被拒把请求形状落到 WB_WAF_DUMP_DIR（默认 /tmp/wb-waf-dumps），
     下次现场直接比对，不必再猜指纹；
  6. 其它 400（客户端自己的错）保持原样：一次出站、立即抛出；
  7. WB_WAF_RETRY_ATTEMPTS=0 关掉换号，恢复旧行为。

    python tests/_test_waf_channel_retry.py
"""
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
import urllib.error

_TMP = tempfile.mkdtemp(prefix="wb-waf-retry-")
os.environ["ACCOUNTS_DIR"] = os.path.join(_TMP, "accounts")
os.environ["WB_PROXY_USAGE_DIR"] = _TMP
os.makedirs(os.environ["ACCOUNTS_DIR"], exist_ok=True)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import wb_accounts
import wb_proxy as P


WAF_BODY = json.dumps({
    "code": 11128,
    "msg": "Illegal API invocation from an unapproved channel",
    "requestId": "01a17dc363a97614a3ff0f3be496f229",
    "displayMsg": {"en": "Request blocked. Please send it again",
                   "zh": "请求被拦截，请重新发送"},
}).encode("utf-8")

PLAIN_400_BODY = json.dumps({
    "code": 11135, "msg": "invalid image data",
}).encode("utf-8")

#: 现场真正的信封形状（同款 11101 正文实测 684 字节）：displayMsg + displayTips
#: 各三种语言，再加 actions。`http_error_detail` 只留 600 字节，所以真实 11128 正文
#: **一定**被截断、`json.loads` 一定失败——1.8.0.1 就是在这里悄无声息地失效的
#: （2026-10-28 08:52 设备上两次真实 11128 都原样透传，一条换号日志都没有）。
WAF_BODY_REAL = json.dumps({
    "code": 11128,
    "msg": "Illegal API invocation from an unapproved channel",
    "requestId": "01a17ffe29a47839bac0153ac3d510cb",
    "displayMsg": {
        "en": "Request blocked. Please send it again",
        "zh": "请求被拦截，请重新发送",
        "zh-hant": "請求被封鎖，請重新傳送",
    },
    "displayTips": {
        "en": ("The server rejected the request, possibly because required "
               "information is missing. Please retry; if it keeps failing, "
               "submit feedback."),
        "zh": "服务端检查请求没通过，可能缺少必要信息。请重试，一直失败请提交反馈。",
        "zh-hant": "服務端檢查請求未通過，可能缺少必要資訊。請重試，持續失敗請提交回饋。",
    },
    "actions": ["RETRY", "SUBMIT_FEEDBACK"],
}).encode("utf-8")


def http_error(code, body):
    return urllib.error.HTTPError("https://upstream/chat", code, "err", {},
                                  io.BytesIO(body))


class FakeResp(object):
    pass


def make_account(uid):
    return wb_accounts.Account({"uid": uid, "accessToken": "t-" + uid,
                                "realm": "intl"})


class StubPool(object):
    def __init__(self, accounts):
        self.accounts = accounts
        self.affinity = wb_accounts.SessionAffinity()

    def count_ready(self, realm, model=None):
        return sum(1 for a in self.accounts
                   if a.realm == realm and a.ready(model=model))

    def pick_for_session(self, realm=None, session_key=None, exclude=(),
                         model=None, page=None):
        for a in self.accounts:
            if a.uid in exclude:
                continue
            if realm and a.realm != realm:
                continue
            if a.ready(model=model):
                return a
        return None

    def apply_remaining_weights(self, weights=None):
        return None

    def apply_daily_token_limit(self, value=None, usage=None):
        return value or 0

    def apply_daily_credit_limit(self, value=None, credits=None, free_models=None):
        return value or 0

    def apply_model_daily_token_limit(self, value=None, per_model=None):
        return value or 0


class ScriptedUpstream(object):
    def __init__(self, script):
        self.script = list(script)
        self.calls = []

    def __call__(self, req, timeout=None, proxy=None):
        self.calls.append(req)
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


PAYLOAD = {"model": "deepseek-v4.1-flash",
           "messages": [{"role": "user", "content": "hi"}]}


class WafRetryTests(unittest.TestCase):
    def setUp(self):
        self.old_pool = P.POOL
        self.old_budget = os.environ.get("WB_WAF_RETRY_ATTEMPTS")
        self.old_prompt_mode = P.prompt_mode_config
        self.old_dump_dir = P.WAF_DUMP_DIR
        self.dump_dir = tempfile.mkdtemp(prefix="waf-dump-test-")
        P.WAF_DUMP_DIR = self.dump_dir
        # 默认把提示模式钉在 custom：降级兜底是用户没选的路径，其余用例只测换号。
        P.prompt_mode_config = lambda: {"mode": "custom", "file": "", "text": ""}
        P.PROMPT_DEGRADE.reset()

    def tearDown(self):
        P.POOL = self.old_pool
        P.prompt_mode_config = self.old_prompt_mode
        P.WAF_DUMP_DIR = self.old_dump_dir
        shutil.rmtree(self.dump_dir, ignore_errors=True)
        P.PROMPT_DEGRADE.reset()
        if self.old_budget is None:
            os.environ.pop("WB_WAF_RETRY_ATTEMPTS", None)
        else:
            os.environ["WB_WAF_RETRY_ATTEMPTS"] = self.old_budget

    def _run(self, accounts, script, payload=None):
        P.POOL = StubPool(accounts)
        upstream = ScriptedUpstream(script)
        real_urlopen = wb_accounts.urlopen
        wb_accounts.urlopen = upstream
        try:
            result = P.open_upstream(dict(payload or PAYLOAD), target_realm="intl")
            raised = None
        except Exception as exc:
            result = None
            raised = exc
        finally:
            wb_accounts.urlopen = real_urlopen
        return upstream, result, raised

    def test_channel_check_400_rotates_to_the_next_account(self):
        first = make_account("w1-first")
        second = make_account("w2-second")
        upstream, result, raised = self._run(
            [first, second], [http_error(400, WAF_BODY), FakeResp()])
        self.assertIsNone(raised, "抽样拦截不该打死整轮")
        self.assertEqual(len(upstream.calls), 2, "应当换一个账号重试")
        self.assertEqual(result[1].uid, "w2-second")
        # 被拒的号没有被记账：它没做错什么，是上游抽样。
        self.assertEqual(first.fails, 0, "渠道校验不该给账号记失败")
        self.assertTrue(first.ready(), "被拒账号仍应在池里可用")

    def test_budget_is_bounded_then_the_raw_400_goes_back(self):
        accounts = [make_account("b1"), make_account("b2"), make_account("b3"),
                    make_account("b4")]
        upstream, result, raised = self._run(
            accounts, [http_error(400, WAF_BODY) for _ in range(4)])
        self.assertIsNone(result)
        self.assertIsInstance(raised, urllib.error.HTTPError)
        self.assertEqual(raised.code, 400)
        self.assertEqual(len(upstream.calls), P.WAF_RETRY_ATTEMPTS_DEFAULT + 1,
                         "预算外不能再打上游")
        # HTTP handler 事后还要读正文，缓冲必须留在异常上。
        self.assertIn("11128",
                      P.read_http_error(raised, 600).decode("utf-8", "replace"))

    def test_other_400_is_still_passed_straight_through(self):
        upstream, result, raised = self._run(
            [make_account("p1"), make_account("p2")],
            [http_error(400, PLAIN_400_BODY), FakeResp()])
        self.assertIsInstance(raised, urllib.error.HTTPError)
        self.assertEqual(len(upstream.calls), 1, "客户端自己的 400 不该换号")

    def test_zero_budget_restores_the_old_behaviour(self):
        os.environ["WB_WAF_RETRY_ATTEMPTS"] = "0"
        upstream, result, raised = self._run(
            [make_account("z1"), make_account("z2")],
            [http_error(400, WAF_BODY), FakeResp()])
        self.assertIsInstance(raised, urllib.error.HTTPError)
        self.assertEqual(len(upstream.calls), 1)

    def test_default_budget_and_code_table(self):
        self.assertEqual(P.WAF_RETRY_ATTEMPTS_DEFAULT, 3)
        self.assertIn(11128, P.WAF_TRANSIENT_ERROR_CODES)
        detail = WAF_BODY.decode("utf-8")
        self.assertEqual(P.upstream_error_code(detail), 11128)
        os.environ["WB_WAF_RETRY_ATTEMPTS"] = ""
        self.assertEqual(P.waf_retry_attempts(), 3)
        os.environ["WB_WAF_RETRY_ATTEMPTS"] = "junk"
        self.assertEqual(P.waf_retry_attempts(), 3)

    # 1.8.0.1 装到设备后补丁没生效：真实正文比 600 字节的留存上限长，截断后的
    # JSON 解析不出来，11128 被当成「普通 400」原样透传。下面三条把它钉死。

    def test_real_length_envelope_still_rotates(self):
        """真实现场长度的 11128 正文（>600 字节）仍然要换号。"""
        self.assertGreater(len(WAF_BODY_REAL), 600,
                           "这条用例的意义就在于正文超过留存上限")
        head = WAF_BODY_REAL.decode("utf-8")[:600]
        with self.assertRaises(Exception):
            json.loads(head)  # 截断后确实不是合法 JSON，这正是旧实现的死因
        self.assertEqual(P.upstream_error_code(head), 11128)
        first = make_account("r1-first")
        second = make_account("r2-second")
        upstream, result, raised = self._run(
            [first, second], [http_error(400, WAF_BODY_REAL), FakeResp()])
        self.assertIsNone(raised, "字节变长不该让换号失效")
        self.assertEqual(len(upstream.calls), 2, "应当换一个账号重试")
        self.assertEqual(result[1].uid, "r2-second")

    def test_truncated_envelope_still_rotates(self):
        """正文在半截 UTF-8 / 半截 JSON 处被截断，也要认得 11128。"""
        first = make_account("t1-first")
        second = make_account("t2-second")
        upstream, result, raised = self._run(
            [first, second], [http_error(400, WAF_BODY_REAL[:300]), FakeResp()])
        self.assertIsNone(raised, "截断后的正文仍要按 11128 处理")
        self.assertEqual(len(upstream.calls), 2, "应当换一个账号重试")
        self.assertEqual(result[1].uid, "t2-second")

    def test_truncated_envelope_budget_still_bounded(self):
        """截断正文上的预算同样有界，用完把原始 400 交回去。"""
        accounts = [make_account("u%d" % i) for i in range(4)]
        upstream, result, raised = self._run(
            accounts, [http_error(400, WAF_BODY_REAL[:300]) for _ in range(4)])
        self.assertIsNone(result)
        self.assertIsInstance(raised, urllib.error.HTTPError)
        self.assertEqual(len(upstream.calls), P.WAF_RETRY_ATTEMPTS_DEFAULT + 1)

    def test_error_code_survives_truncation(self):
        """`upstream_error_code` 对截断正文按头部兜底，其它垃圾仍返回 None。"""
        full = WAF_BODY_REAL.decode("utf-8")
        self.assertEqual(P.upstream_error_code(full), 11128)
        self.assertEqual(P.upstream_error_code(full[:250]), 11128)
        self.assertEqual(P.upstream_error_code(full[:600]), 11128)
        self.assertIsNone(P.upstream_error_code(""))
        self.assertIsNone(P.upstream_error_code('{"msg":"no code here"}'))
        self.assertIsNone(P.upstream_error_code("internal server error"))


    # 1.8.0.3（Phase S）：真机 09:22 两个请求 1.3 秒内把预算打完，三个账号全被拒。
    # 抽样判定的收手概率随时间/次数上升，所以换号之间要留时间差，预算再大一格，
    # 并且把「这条被拒的请求长什么样」落到 /tmp（数据目录不碰），最后才是降级提示。

    def test_rotation_waits_between_attempts(self):
        """每次换号前按 WAF_RETRY_DELAYS 等，不再 1.3 秒内把预算打光。"""
        accounts = [make_account("s%d" % i) for i in range(5)]
        script = [http_error(400, WAF_BODY) for _ in range(P.WAF_RETRY_ATTEMPTS_DEFAULT)]
        script.append(FakeResp())
        slept = []
        real_sleep = P.time.sleep
        P.time.sleep = lambda seconds: slept.append(seconds)
        try:
            upstream, result, raised = self._run(accounts, list(script))
        finally:
            P.time.sleep = real_sleep
        self.assertIsNone(raised, "多等一会儿就该换到能服务的号")
        self.assertEqual(len(upstream.calls), P.WAF_RETRY_ATTEMPTS_DEFAULT + 1)
        waf_waits = [s for s in slept if s >= min(P.WAF_RETRY_DELAYS)]
        self.assertEqual(waf_waits, list(P.WAF_RETRY_DELAYS[:P.WAF_RETRY_ATTEMPTS_DEFAULT]),
                         "换号等待必须逐次拉长")
        self.assertEqual(P.waf_retry_delay(1), P.WAF_RETRY_DELAYS[0])
        self.assertEqual(P.waf_retry_delay(99), P.WAF_RETRY_DELAYS[-1])
        self.assertEqual(P.waf_retry_delay(0), 0.0)

    def test_budget_exhausted_borrows_the_neutral_prompt_once(self):
        """预算打完仍被拒 → 只借这一条请求换中性系统提示，窗口立刻复位。"""
        P.prompt_mode_config = lambda: {"mode": "passthrough", "file": "", "text": ""}
        accounts = [make_account("g%d" % i) for i in range(5)]
        payload = {"model": "deepseek-v4.1-flash",
                   "messages": [{"role": "system", "content": "SENTINEL-SYSTEM"},
                                {"role": "user", "content": "hi"}]}
        script = [http_error(400, WAF_BODY_REAL[:300])
                  for _ in range(P.WAF_RETRY_ATTEMPTS_DEFAULT + 1)]
        script.append(FakeResp())
        upstream, result, raised = self._run(accounts, list(script), payload=payload)
        self.assertIsNone(raised, "中性提示重试后应该能过")
        self.assertEqual(len(upstream.calls), P.WAF_RETRY_ATTEMPTS_DEFAULT + 2,
                         "换号预算 + 一次中性提示重试都要真的出站")
        first, last = upstream.calls[0].data, upstream.calls[-1].data
        self.assertIn(b"SENTINEL-SYSTEM", first, "前几次必须用客户端自己的系统提示")
        self.assertNotIn(b"SENTINEL-SYSTEM", last, "最后一次必须换成中性提示")
        self.assertFalse(P.PROMPT_DEGRADE.active(),
                         "只借这一条请求：不能把整天其余请求的提示也换掉")

    def test_degraded_prompt_retry_is_only_tried_once(self):
        """降级之后还被拒就交回原始 400，不无限重试。"""
        P.prompt_mode_config = lambda: {"mode": "append", "file": "", "text": ""}
        accounts = [make_account("h%d" % i) for i in range(8)]
        script = [http_error(400, WAF_BODY) for _ in range(12)]
        upstream, result, raised = self._run(accounts, list(script))
        self.assertIsNone(result)
        self.assertIsInstance(raised, urllib.error.HTTPError)
        self.assertEqual(raised.code, 400)
        self.assertEqual(len(upstream.calls), P.WAF_RETRY_ATTEMPTS_DEFAULT + 2,
                         "预算 + 一次降级重试，不能再多")

    def test_rejection_dump_records_the_system_prompt_shape(self):
        """被拒时把请求形状（不写数据目录）落盘，下次现场直接比对。"""
        dump_dir = os.path.join(_TMP, "waf-dumps")
        old_dir = P.WAF_DUMP_DIR
        P.WAF_DUMP_DIR = dump_dir
        try:
            payload = {"model": "deepseek-v4.1-flash",
                       "messages": [{"role": "system", "content": "S" * 400},
                                    {"role": "user", "content": "hi"}]}
            accounts = [make_account("d1"), make_account("d2")]
            upstream, result, raised = self._run(
                accounts, [http_error(400, WAF_BODY_REAL), FakeResp()],
                payload=payload)
        finally:
            P.WAF_DUMP_DIR = old_dir
        self.assertIsNone(raised)
        names = sorted(n for n in os.listdir(dump_dir) if n.startswith("waf-"))
        self.assertEqual(len(names), 1, "一次被拒一条 dump")
        record = json.load(open(os.path.join(dump_dir, names[0]), encoding="utf-8"))
        self.assertEqual(record["waf_code"], 11128)
        self.assertEqual(record["msgs"], 2)
        self.assertEqual(record["system_role"], "system")
        # 出站正文里的 system 已经过提示模式处理，长度与入站不同，只钉形状。
        self.assertGreater(record["system_len"], 0)
        self.assertEqual(len(record["system_head"]), record["system_len"])
        self.assertTrue(record["body_sha256"])
        self.assertEqual(record["tail_msgs"][-1], ["user", 2])
        self.assertNotIn("ACCOUNTS_DIR", json.dumps(record), "dump 不该带路径")


if __name__ == "__main__":
    unittest.main(verbosity=2)
