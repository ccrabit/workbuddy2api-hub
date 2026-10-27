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

  1. 400 里 code=11128 → 换一个账号重试，最多 WB_WAF_RETRY_ATTEMPTS（默认 2）次；
  2. 换号不记账：被拒的账号既不加 fails 也不进冷却（它没做错什么，是抽样）；
  3. 预算用完仍失败 → 把原始 400 交回去，且正文对 HTTP handler 仍可读；
  4. 其它 400（客户端自己的错）保持原样：一次出站、立即抛出；
  5. WB_WAF_RETRY_ATTEMPTS=0 关掉换号，恢复旧行为。

    python tests/_test_waf_channel_retry.py
"""
import io
import json
import os
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

    def tearDown(self):
        P.POOL = self.old_pool
        if self.old_budget is None:
            os.environ.pop("WB_WAF_RETRY_ATTEMPTS", None)
        else:
            os.environ["WB_WAF_RETRY_ATTEMPTS"] = self.old_budget

    def _run(self, accounts, script):
        P.POOL = StubPool(accounts)
        upstream = ScriptedUpstream(script)
        real_urlopen = wb_accounts.urlopen
        wb_accounts.urlopen = upstream
        try:
            result = P.open_upstream(dict(PAYLOAD), target_realm="intl")
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
        self.assertEqual(P.WAF_RETRY_ATTEMPTS_DEFAULT, 2)
        self.assertIn(11128, P.WAF_TRANSIENT_ERROR_CODES)
        detail = WAF_BODY.decode("utf-8")
        self.assertEqual(P.upstream_error_code(detail), 11128)
        os.environ["WB_WAF_RETRY_ATTEMPTS"] = ""
        self.assertEqual(P.waf_retry_attempts(), 2)
        os.environ["WB_WAF_RETRY_ATTEMPTS"] = "junk"
        self.assertEqual(P.waf_retry_attempts(), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
