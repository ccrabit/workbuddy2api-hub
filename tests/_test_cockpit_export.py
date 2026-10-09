"""Cockpit-compatible export (WP-E5): field-by-field alignment with the Go panel.

The point of this file is that the export is *not* "a JSON dump that looks
close". The far side is `panel.importCockpit` in
`internal/panel/import.go`, and it is strict in three places that a
hand-written exporter gets wrong:

* the payload must be a **bare array** of snake_case objects (the struct's json
  tags are the field names - no envelope, no camelCase);
* `expires_at` is read as **milliseconds** (`ExpiresAt / 1000`), while the
  sibling timestamps are wall-clock seconds and are never read back;
* the realm is derived from `domain` **alone** (`isGlobalDomain`), and anything
  that is not a `workbuddy.ai` host - including an empty domain - lands in CN.

Rows that miss `uid` / `access_token` / `refresh_token`, or whose uid is not
`[A-Za-z0-9_-]{1,64}`, are silently counted as `skipped`, so a credential-free
cockpit file imports nothing at all.

When the panel checkout is present this test reads the struct straight out of
import.go and compares the tags (and a real sample file the panel exported), so
an upstream field rename fails here rather than at import time on the NAS.
"""
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import wb_accounts
import wb_export

PANEL_IMPORT_GO = "/tmp/panel-latest/internal/panel/import.go"
SAMPLE = "/vol2/1000/AgentWork/2api/账号文件/workbuddy-accounts-20261006163005.cockpit.json"
PROXY = os.path.join(ROOT, "wb_proxy.py")
PANEL_PASSWORD = "test-panel-password"

# Everything this suite writes lands under here: CI runs
# scripts/check_clean_checkout.py right after the suites, so nothing may be
# written into the checkout, and "/tmp" does not exist on Windows.
TMP_ROOT = tempfile.mkdtemp(prefix="wb-cockpit-")

try:  # the labels below are Chinese; a cp1252 console must not abort the suite
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

RESULTS = []


def check(label, condition, detail=""):
    RESULTS.append((bool(condition), label, detail))
    print("  [%s] %s%s" % ("PASS" if condition else "FAIL", label,
                           (" -- " + str(detail)) if (detail and not condition) else ""))
    return bool(condition)


def go_struct_fields(path):
    """json tags of `cockpitAccount` in the panel's import.go, in order."""
    with open(path, encoding="utf-8") as fh:
        source = fh.read()
    match = re.search(r"type\s+cockpitAccount\s+struct\s*\{(.*?)\n\}", source, re.S)
    if not match:
        return None
    fields = []
    for line in match.group(1).splitlines():
        tag = re.search(r'json:"([^",]+)', line)
        if tag:
            fields.append(tag.group(1))
    return fields


def account(uid, realm, **kw):
    """A real `wb_accounts.Account`, so the attribute names under test are real."""
    data = {
        "uid": uid,
        "nickname": kw.pop("nickname", uid),
        "realm": realm,
        "domain": kw.pop("domain", ""),
        "accessToken": kw.pop("access_token", "access-%s" % uid),
        "refreshToken": kw.pop("refresh_token", "refresh-%s" % uid),
        "expiresAt": kw.pop("expires_at", int(time.time()) + 86400 * 30),
        "addedAt": kw.pop("added_at", 1791176070),
        "enabled": kw.pop("enabled", True),
    }
    data.update(kw)
    return wb_accounts.Account(data, os.path.join(TMP_ROOT, "workbuddy-%s.json" % uid))


def test_field_alignment():
    print("== 字段与 import.go 的 cockpitAccount 对齐 ==")
    if os.path.exists(PANEL_IMPORT_GO):
        fields = go_struct_fields(PANEL_IMPORT_GO)
        check("从 import.go 读到 17 个 json tag", fields is not None and len(fields) == 17,
              fields)
        check("wb_export.COCKPIT_FIELDS == import.go 的字段顺序",
              tuple(fields or ()) == wb_export.COCKPIT_FIELDS,
              (fields, list(wb_export.COCKPIT_FIELDS)))
    else:
        print("  [skip] %s 不存在，跳过源码级对齐（仍比对参考样例）" % PANEL_IMPORT_GO)

    if not os.path.exists(SAMPLE):
        print("  [skip] 参考样例 %s 不存在" % SAMPLE)
        return
    with open(SAMPLE, encoding="utf-8") as fh:
        rows = json.load(fh)
    check("参考样例是裸数组且非空", isinstance(rows, list) and bool(rows), type(rows).__name__)
    check("参考样例每行 key 与 COCKPIT_FIELDS 完全一致（含顺序）",
          all(tuple(row.keys()) == wb_export.COCKPIT_FIELDS for row in rows),
          [list(row.keys())[:3] for row in rows[:1]])
    check("参考样例 expires_at 是毫秒（>= 10^12）",
          all(isinstance(r["expires_at"], int) and r["expires_at"] >= 10 ** 12 for r in rows),
          [r["expires_at"] for r in rows[:3]])
    check("参考样例 id == uid",
          all(r["id"] == r["uid"] for r in rows), [r.get("id") for r in rows[:2]])
    check("参考样例 token_type 是 Bearer",
          {r["token_type"] for r in rows} == {"Bearer"}, {r["token_type"] for r in rows})
    # The canonical hosts we fall back to must be the ones the panel itself
    # writes, and they must be bare hosts (no scheme) - the Go side uses this
    # field as a host.
    sample_hosts = {str(r["domain"]) for r in rows}
    check("回填用的 realm 主机正是参考样例里的裸主机",
          {wb_export.realm_domain("cn"), wb_export.realm_domain("intl")} <= sample_hosts,
          (sorted(sample_hosts), wb_export.realm_domain("cn"), wb_export.realm_domain("intl")))
    check("参考样例 domain 从不带 scheme",
          all("://" not in host for host in sample_hosts), sorted(sample_hosts))


def test_row_values():
    print("== cockpit_row 取值与单位 ==")
    exp = int(time.time()) + 86400 * 30
    cn = account("cn-acct", "cn", domain="", expires_at=exp)
    cn.credits = {"updated_at": 1791304109}
    cn.last_checkin = "2026-10-06 21:15:08"
    row = wb_export.cockpit_row(cn)
    check("key 顺序 = COCKPIT_FIELDS", tuple(row.keys()) == wb_export.COCKPIT_FIELDS,
          tuple(row.keys()))
    check("expires_at = 秒 * 1000（对面会 /1000）", row["expires_at"] == exp * 1000,
          (row["expires_at"], exp))
    check("id == uid", row["id"] == row["uid"] == "cn-acct", row["id"])
    check("token_type = Bearer", row["token_type"] == "Bearer", row["token_type"])
    check("status = active（enabled）", row["status"] == "active", row["status"])
    check("usage_updated_at 取 credits.updated_at（秒）", row["usage_updated_at"] == 1791304109,
          row["usage_updated_at"])
    check("created_at = addedAt（秒）", row["created_at"] == 1791176070, row["created_at"])
    check("last_checkin_time 由墙钟文本转秒",
          row["last_checkin_time"] == int(time.mktime(time.strptime(
              "2026-10-06 21:15:08", "%Y-%m-%d %H:%M:%S"))), row["last_checkin_time"])
    # wb_accounts.py:213-216 fills a blank stored domain from the realm config
    # (cn -> copilot.tencent.com), so a real cn Account never reaches the
    # fallback; the row keeps the host our own X-Domain header uses
    # (wb_accounts.py:475 `X-Domain: self.domain or cfg["domain"]`).
    check("cn 账号（存储 domain 为空 -> 自动填 copilot.tencent.com）原样导出",
          row["domain"] == "copilot.tencent.com", row["domain"])

    class Blank(object):
        uid = "blank-acct"
        realm = "cn"
        domain = ""

    check("存储 domain 真为空时回填本 realm 的裸主机（空 domain 会被对面当 cn）",
          wb_export.cockpit_row(Blank())["domain"]
          == wb_export.realm_domain("cn") == "www.codebuddy.cn",
          wb_export.cockpit_row(Blank())["domain"])
    check("last_used / checkin_streak / email / 两个 code 字段",
          row["last_used"] == 0 and row["checkin_streak"] == 0 and row["email"] == ""
          and row["dosage_notify_code"] == "" and row["payment_type"] == "",
          {k: row[k] for k in ("last_used", "checkin_streak", "email")})

    intl = account("intl-acct", "intl", domain="")
    intl_row = wb_export.cockpit_row(intl)
    check("intl 空 domain 回填 workbuddy.ai（决定对面归到哪个 realm）",
          intl_row["domain"] == wb_export.realm_domain("intl") == "www.workbuddy.ai",
          intl_row["domain"])
    check("自带 domain 与本 realm 一致时原样保留（不凭空改写）",
          wb_export.cockpit_row(account("x", "intl", domain="www.workbuddy.ai"))["domain"]
          == "www.workbuddy.ai"
          and wb_export.cockpit_row(account("y", "cn", domain="copilot.tencent.com"))["domain"]
          == "copilot.tencent.com")
    check("矛盾 domain 以 realm 为准（否则 cockpit 行会被对面放进另一个池）",
          wb_export.cockpit_row(account("x", "intl", domain="www.codebuddy.cn"))["domain"]
          == wb_export.realm_domain("intl")
          and wb_export.cockpit_row(account("x", "cn", domain="www.workbuddy.ai"))["domain"]
          == wb_export.realm_domain("cn"),
          (wb_export.cockpit_row(account("x", "intl", domain="www.codebuddy.cn"))["domain"],
           wb_export.cockpit_row(account("x", "cn", domain="www.workbuddy.ai"))["domain"]))
    off = account("off-acct", "cn", enabled=False)
    check("disabled -> status=disabled（对面不读，但文件要自洽）",
          wb_export.cockpit_row(off)["status"] == "disabled",
          wb_export.cockpit_row(off)["status"])
    check("expires_at 未知 -> 0（对面 <=0 时会自己补一年）",
          wb_export.cockpit_row(account("no-exp", "cn", expires_at=0))["expires_at"] == 0,
          wb_export.cockpit_row(account("no-exp", "cn", expires_at=0))["expires_at"])


def test_domain_realm_consistency():
    """A cockpit row must never import into the other pool (no realm field)."""
    print("== domain 必须推出账号自己的 realm ==")
    check("isGlobalDomain 等价物：workbuddy.ai 家族 = intl",
          all(wb_export.realm_for_domain(d) == "intl" for d in
              ("workbuddy.ai", "WWW.WorkBuddy.AI", " www.workbuddy.ai ", "a.b.workbuddy.ai",
               "https://www.workbuddy.ai", "www.workbuddy.ai:443", "www.workbuddy.ai/x")),
          [wb_export.realm_for_domain(d) for d in ("a.b.workbuddy.ai", "www.workbuddy.ai:443")])
    check("isGlobalDomain 等价物：其它主机（含空）= cn",
          all(wb_export.realm_for_domain(d) == "cn" for d in
              ("", None, "www.codebuddy.cn", "copilot.tencent.com",
               "workbuddy.ai.evil.com", "notworkbuddy.ai", "workbuddy.example.com")),
          [wb_export.realm_for_domain(d) for d in ("workbuddy.ai.evil.com", "notworkbuddy.ai")])
    check("realm_domain 给裸主机（不带 scheme，Go 侧当 host 用）",
          wb_export.realm_domain("cn") == "www.codebuddy.cn"
          and wb_export.realm_domain("intl") == "www.workbuddy.ai",
          (wb_export.realm_domain("cn"), wb_export.realm_domain("intl")))
    check("domain_conflicts_realm 只对矛盾账号为真",
          wb_export.domain_conflicts_realm(account("c1", "cn", domain="www.workbuddy.ai")) is True
          and wb_export.domain_conflicts_realm(account("c2", "cn", domain="copilot.tencent.com"))
          is False
          and wb_export.domain_conflicts_realm(account("c3", "intl", domain="")) is False,
          (wb_export.domain_conflicts_realm(account("c1", "cn", domain="www.workbuddy.ai")),
           wb_export.domain_conflicts_realm(account("c3", "intl", domain=""))))

    combos = []
    for realm in ("cn", "intl"):
        for domain in ("", "www.workbuddy.ai", "www.codebuddy.cn", "copilot.tencent.com",
                       "sub.workbuddy.ai", "workbuddy.ai", "  ", None):
            combos.append(account("u-%s-%s" % (realm, domain), realm, domain=domain))
    rows = wb_export.build_cockpit_rows(combos)
    bad = [(r["uid"], r["domain"]) for r, a in zip(rows, combos)
           if wb_export.realm_for_domain(r["domain"]) != a.realm]
    check("任何 domain/realm 组合导出后推出的 realm 都等于账号 realm", not bad, bad)
    bad_host = [r["domain"] for r in rows if "://" in str(r["domain"]) or not str(r["domain"])]
    check("导出 domain 始终是非空裸主机", not bad_host, bad_host)


def test_panel_import_simulation():
    """Replay the Go importer's rules against one of our rows."""
    print("== 用对面 importer 的规则回放 ==")
    cn = account("cn-acct", "cn", domain="")
    intl = account("intl-acct", "intl", domain="")
    rows = wb_export.build_cockpit_rows([cn, intl])
    check("两行都在", len(rows) == 2, len(rows))
    uid_re = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
    for row in rows:
        check("uid %s 通过 validImportUID" % row["uid"], bool(uid_re.match(row["uid"])),
              row["uid"])
        check("uid %s 三个必填字段非空（否则 imported 会少一行）" % row["uid"],
              all(str(row[key] or "").strip() for key in
                  ("uid", "access_token", "refresh_token")),
              {k: row[k] for k in ("uid", "access_token", "refresh_token")})

    def resolve_realm(domain):
        # isGlobalDomain(): only a workbuddy.ai host counts as international.
        value = str(domain or "").strip().lower()
        return "global" if (value == "workbuddy.ai" or value.endswith(".workbuddy.ai")) else "cn"

    realms = {row["uid"]: resolve_realm(row["domain"]) for row in rows}
    check("对面 ResolveRealm 判 cn 账号 -> cn", realms["cn-acct"] == "cn", realms)
    check("对面 ResolveRealm 判 intl 账号 -> global（不是 cn）",
          realms["intl-acct"] == "global", realms)
    expired = {row["uid"]: int(row["expires_at"] / 1000) for row in rows}
    check("对面 expires_at/1000 == 我们的 Account.expires_at",
          expired["cn-acct"] == int(cn.expires_at) and expired["intl-acct"] == int(intl.expires_at),
          (expired, cn.expires_at, intl.expires_at))


def test_documents():
    print("== build_document / 文件名 / 过滤 ==")
    cn = account("cn-acct", "cn")
    intl = account("intl-acct", "intl")
    rows, name, count = wb_export.build_document(
        wb_export.COCKPIT_FORMAT, [cn, intl], realm="cn")
    check("cockpit payload 是裸数组", isinstance(rows, list) and len(rows) == 1, rows)
    check("cockpit 文件名带 .cockpit.json 且含 realm 前缀",
          name.startswith("workbuddy-accounts-cn-") and name.endswith(".cockpit.json"), name)
    check("count = 行数", count == 1, count)

    name = wb_export.export_filename(wb_export.COCKPIT_FORMAT, uids=["cn-acct"],
                                     stamp="20261007-013000")
    check("单 uid 导出用 uid 前 8 位做前缀（与历史 native 命名一致，无分隔符）",
          name == "workbuddy-accounts-cn-acct20261007-013000.cockpit.json", name)

    doc, name, count = wb_export.build_document(
        wb_export.NATIVE_FORMAT, [cn, intl], realm="cn")
    check("native 仍是信封", isinstance(doc, dict)
          and doc.get("format") == "workbuddy-accounts" and doc.get("count") == 1, doc)
    check("native 文件名没有 .cockpit", ".cockpit." not in name
          and name.startswith("workbuddy-accounts-cn-"), name)
    check("native 缺省文件名（无 realm/uid）仍是历史形状",
          wb_export.export_filename(wb_export.NATIVE_FORMAT, stamp="20261007-013000")
          == "workbuddy-accounts-20261007-013000.json",
          wb_export.export_filename(wb_export.NATIVE_FORMAT, stamp="20261007-013000"))
    check("native 丢字段名后不带 ok/data 包装", "ok" not in doc and "data" not in doc, list(doc))
    check("native 行是 camelCase", "accessToken" in (doc.get("accounts") or [{}])[0],
          (doc.get("accounts") or [{}])[0])
    check("secrets=False 时 native 不带走 token",
          "accessToken" not in (wb_export.build_document(
              wb_export.NATIVE_FORMAT, [cn], include_secrets=False)[0]["accounts"][0]),
          wb_export.build_document(wb_export.NATIVE_FORMAT, [cn], include_secrets=False)[0])

    check("normalize_format 缺省 = native",
          wb_export.normalize_format(None) == ("native", None))
    check("normalize_format 大小写无关",
          wb_export.normalize_format(" COCKPIT ") == ("cockpit", None))
    fmt, error = wb_export.normalize_format("yaml")
    check("normalize_format 未知值 -> error", fmt is None and "native, cockpit" in error, error)
    check("select_accounts 先筛 realm 再筛 uid",
          [a.uid for a in wb_export.select_accounts([cn, intl], realm="intl",
                                                    uids=["cn-acct", "intl-acct"])]
          == ["intl-acct"])
    check("timestamp_seconds 容忍 0 / None",
          wb_export.timestamp_seconds(0) == 0 and wb_export.timestamp_seconds(None) == 0
          and wb_export.timestamp_seconds("") == 0)
    check("timestamp_seconds 容忍垃圾文本",
          wb_export.timestamp_seconds("not a date") == 0)
    check("to_epoch_ms 已是毫秒时不再乘",
          wb_export.to_epoch_ms(1794405600000) == 1794405600000)
    check("to_epoch_ms 秒 -> 毫秒", wb_export.to_epoch_ms(1794405600) == 1794405600000)


class Instance(object):
    """A real server process on a free port with its own empty data dirs."""

    def __init__(self):
        self.tmp = tempfile.mkdtemp(prefix="wb-cockpit-")
        self.port = free_port()
        self.accounts_dir = os.path.join(self.tmp, "accounts")
        self.usage_dir = os.path.join(self.tmp, "usage")
        os.makedirs(self.accounts_dir)
        self.token = ""
        # Log to a file, not a pipe: an undrained PIPE can block the child
        # once it fills, and Windows has no patience for that.
        self.log_path = os.path.join(self.tmp, "server.log")
        self.log = open(self.log_path, "wb")
        self.proc = subprocess.Popen(
            [sys.executable, PROXY, "--host", "127.0.0.1", "--port", str(self.port),
             "--accounts-dir", self.accounts_dir, "--usage-dir", self.usage_dir,
             "--panel-password", PANEL_PASSWORD],
            cwd=ROOT, stdout=self.log, stderr=subprocess.STDOUT)

    def wait_ready(self):
        deadline = time.time() + 60
        while time.time() < deadline:
            if self.proc.poll() is not None:
                return False
            try:
                if self.raw("GET", "/health")[0] == 200:
                    return True
            except Exception:
                pass
            time.sleep(0.2)
        return False

    def raw(self, method, path, payload=None, token=None):
        headers = {}
        data = None
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if token:
            headers["X-Panel-Token"] = token
        request = urllib.request.Request(
            "http://127.0.0.1:%d%s" % (self.port, path), data=data,
            headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.status, response.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read().decode("utf-8", "replace")

    def api(self, method, path, payload=None):
        return self.raw(method, path, payload, token=self.token)

    def login(self):
        status, body = self.raw("POST", "/panel/login", {"password": PANEL_PASSWORD})
        try:
            self.token = json.loads(body).get("token") or ""
        except ValueError:
            self.token = ""
        return status == 200 and bool(self.token)

    def stop(self):
        try:
            self.proc.terminate()
            self.proc.wait(timeout=15)
        except Exception:
            try:
                self.proc.kill()
            except Exception:
                pass
        try:
            self.log.close()
        except Exception:
            pass


def free_port():
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def test_http_round_trip():
    """The export is only a contract if the server itself can read it back."""
    print("== 真 HTTP：POST /accounts/export -> 服务端自己的导入路径 ==")
    inst = Instance()
    try:
        check("实例起来并通过 /health", inst.wait_ready())
        check("面板登录拿到 token", inst.login())
        if not inst.token:
            return
        now = int(time.time())
        expires = now + 86400 * 30
        cn = {"uid": "round-cn", "nickname": "国内账号", "realm": "cn",
              "domain": "www.codebuddy.cn", "accessToken": "cn.access.token",
              "refreshToken": "cn.refresh.token", "expiresAt": expires, "enabled": True}
        intl = {"uid": "round-intl", "nickname": "国际账号", "realm": "intl",
                "domain": "www.workbuddy.ai", "accessToken": "intl.access.token",
                "refreshToken": "intl.refresh.token", "expiresAt": expires, "enabled": True}
        status, body = inst.api("POST", "/accounts/import", {"data": [cn, intl]})
        check("POST /accounts/import 装进两个账号", status == 200, (status, body[:160]))

        status, body = inst.api("GET", "/accounts/export")
        native = json.loads(body)
        check("GET /accounts/export 仍是上游 native 信封（无 ok/data 包装）",
              status == 200 and native.get("format") == "workbuddy-accounts"
              and "ok" not in native and "data" not in native
              and native.get("count") == 2, (status, list(native)[:8]))
        status, body = inst.api("GET", "/accounts/export?format=cockpit")
        check("GET 不接受 format（历史行为逐字节不变，仍出 native）",
              status == 200 and json.loads(body).get("format") == "workbuddy-accounts",
              (status, body[:80]))

        status, body = inst.api("GET", "/accounts/export?realm=cn")
        one_realm = json.loads(body)
        status2, body2 = inst.api("POST", "/accounts/export", {"format": "native", "realm": "cn"})
        env = json.loads(body2)
        left = {k: v for k, v in one_realm.items() if k != "exportedAt"}
        right = {k: v for k, v in (env.get("data") or {}).items() if k != "exportedAt"}
        check("POST native（同 realm）与 GET 输出同体",
              status2 == 200 and left == right, (status2, str(env)[:120]))

        status, body = inst.api("POST", "/accounts/export", {"format": "cockpit", "realm": "cn"})
        env = json.loads(body)
        check("POST cockpit 是 {ok,format,filename,count,data} 信封", status == 200
              and env.get("ok") is True and env.get("format") == "cockpit"
              and str(env.get("filename")).endswith(".cockpit.json")
              and env.get("count") == 1 and isinstance(env.get("data"), list),
              (status, str(env)[:160]))
        rows = env.get("data") or []
        row = rows[0] if rows else {}
        check("cockpit 行 key 顺序 == COCKPIT_FIELDS",
              tuple(row.keys()) == wb_export.COCKPIT_FIELDS, tuple(row.keys()))
        check("cockpit 行不带网关私有字段",
              not (set(row) - set(wb_export.COCKPIT_FIELDS)),
              sorted(set(row) - set(wb_export.COCKPIT_FIELDS)))
        check("cockpit 行 domain 推出的 realm == 账号 realm（cn）",
              wb_export.realm_for_domain(row.get("domain")) == "cn", row.get("domain"))
        check("cockpit 行 expires_at = 账号 expires_at x 1000",
              row.get("expires_at") == expires * 1000,
              (row.get("expires_at"), expires * 1000))
        status, body = inst.api("POST", "/accounts/export", {"format": "cockpit", "realm": "intl"})
        intl_row = (json.loads(body).get("data") or [{}])[0]
        check("intl 行 domain 仍推出 intl（cockpit 行没有 realm 字段）",
              wb_export.realm_for_domain(intl_row.get("domain")) == "intl",
              intl_row.get("domain"))

        # The acceptance test: the file this route just wrote must survive the
        # server's own cockpit import branch without losing a field.
        kwargs = wb_accounts.normalise_import_row(row)
        check("上游 importer 读回 uid / 两个 token / expiresAt",
              kwargs.get("uid") == "round-cn"
              and kwargs.get("accessToken") == "cn.access.token"
              and kwargs.get("refreshToken") == "cn.refresh.token"
              and int(kwargs.get("expiresAt") or 0) == expires,
              {k: kwargs.get(k) for k in ("uid", "accessToken", "refreshToken", "expiresAt")})
        check("上游 importer 由 domain 判回 cn", kwargs.get("realm") == "cn",
              (kwargs.get("realm"), row.get("domain")))
        status, body = inst.api("POST", "/accounts/import", {"data": rows, "overwrite": True})
        report = json.loads(body).get("result") or {}
        check("导出文件被服务端自己的导入路径读回（更新而非新增，无 invalid）",
              status == 200 and "round-cn" in (report.get("updated") or [])
              and not report.get("invalid"), str(report)[:200])
        status, body = inst.api("GET", "/accounts?realm=all")
        back = {a["uid"]: a for a in json.loads(body).get("accounts") or []}
        check("回读后 /accounts 里的 realm / expiresAt 都没丢（public 行不外泄 token）",
              back.get("round-cn", {}).get("realm") == "cn"
              and int(back.get("round-cn", {}).get("expiresAt") or 0) == expires
              and "accessToken" not in back.get("round-cn", {})
              and back.get("round-cn", {}).get("hasRefreshToken") is True,
              {k: back.get("round-cn", {}).get(k)
               for k in ("realm", "expiresAt", "hasRefreshToken")})
        status, body = inst.api("GET", "/accounts/export?realm=cn")
        doc = json.loads(body)
        kept = {r.get("uid"): r for r in doc.get("accounts") or []}
        check("回读后 native 导出里两个 token 与过期时间原地保留",
              status == 200
              and kept.get("round-cn", {}).get("accessToken") == "cn.access.token"
              and kept.get("round-cn", {}).get("refreshToken") == "cn.refresh.token"
              and int(kept.get("round-cn", {}).get("expiresAt") or 0) == expires,
              {k: kept.get("round-cn", {}).get(k)
               for k in ("uid", "accessToken", "refreshToken", "expiresAt")})
        check("intl 账号经同一条路径仍是 intl",
              back.get("round-intl", {}).get("realm") == "intl",
              back.get("round-intl", {}).get("realm"))

        status, _ = inst.raw("POST", "/accounts/export",
                             {"format": "cockpit", "realm": "cn"})
        check("未登录 POST /accounts/export -> 401", status == 401, status)

        for label, payload, want in (
                ("缺 format -> 400", {"realm": "cn"}, 400),
                ("未知 format -> 400", {"realm": "cn", "format": "yaml"}, 400),
                ("缺 realm -> 400", {"format": "cockpit"}, 400),
                ("realm 非 cn/intl -> 400", {"format": "cockpit", "realm": "zzz"}, 400),
                ("cockpit + secrets:false -> 400",
                 {"format": "cockpit", "realm": "cn", "secrets": False}, 400),
                ("uids 不是数组 -> 400",
                 {"format": "native", "realm": "cn", "uids": "round-cn"}, 400),
                ("未知 uid -> 404", {"format": "native", "realm": "cn", "uid": "ghost"}, 404)):
            status, body = inst.api("POST", "/accounts/export", payload)
            try:
                error = json.loads(body).get("error")
            except ValueError:
                error = None
            check(label, status == want and isinstance(error, dict)
                  and bool(error.get("message")), (status, body[:120]))

        status, body = inst.api("POST", "/accounts/export", {"format": "cockpit", "realm": "cn"})
        check("连报错之后仍能正常导出（服务没被打坏）",
              status == 200 and bool(json.loads(body).get("data")), (status, body[:120]))
    finally:
        inst.stop()


def main():
    test_field_alignment()
    test_row_values()
    test_domain_realm_consistency()
    test_panel_import_simulation()
    test_documents()
    test_http_round_trip()
    passed = sum(1 for ok, _, _ in RESULTS if ok)
    failed = [(label, detail) for ok, label, detail in RESULTS if not ok]
    print("")
    print("PASS=%d FAIL=%d" % (passed, len(failed)))
    for label, detail in failed:
        print("  FAIL: %s -- %s" % (label, str(detail)[:300]))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
