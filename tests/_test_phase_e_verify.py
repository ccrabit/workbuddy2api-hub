"""WP-E4 — independent, adversarial verification of Phase E.

This suite exists to *disprove* the Phase E work, not to re-run the owners'
own tests. It starts the real server on a temporary port + unix socket and
talks to it the way fnOS does, forges the headers a LAN client can forge,
unpacks the final fpk and compares it byte for byte with the checkout.

Design notes (kept from the Phase D suite, same idioms):

* Nothing here calls `tests/run_all.py` from inside a test — the section
  `e1_suites` runs it as a subprocess, and run_all picks this file up, so an
  in-process call would recurse forever.
* Raw sockets are used for HTTP so that 4xx/5xx status codes and bodies stay
  observable (urllib raises and hides them).
* Work that has not landed yet is reported as SKIP; `WB_PHASE_E_STRICT=1`
  turns a missing artefact into a hard FAIL for the final run.
* The CI matrix runs this file on windows-latest, where `socket.AF_UNIX` does
  not exist. Everything that needs the gateway socket skips there (never
  fails), digests go through hashlib instead of `sha256sum`/`md5sum`, and the
  `e10` section rehearses that shape on Linux by deleting `socket.AF_UNIX` in
  a subprocess and requiring the whole suite to stay green.

  Two CI facts also shape this file: `actions/checkout` is a shallow clone
  (depth 1), so the merge commit `9dff35f` and the annotated tag object are
  unreachable (`git merge-base --is-ancestor` answers 128) and the two history
  assertions in `e8` skip instead of going red; and the runner is not root, so
  the uid matrix in `e2b` skips there as well. `e11` rehearses both shapes
  locally (a real `--depth 1` clone, plus a non-root subprocess).

    python3 tests/_test_phase_e_verify.py                 # all sections
    python3 tests/_test_phase_e_verify.py e2_gateway       # substring filter
    WB_PHASE_E_STRICT=1 python3 tests/_test_phase_e_verify.py

Sections: e1_suites e2_gateway e2_peer_matrix e3_mount e4_credit e5_package
          e6_device e7_hardening e8_delivery e9_cockpit_export
          e10_platform_sim e11_ci_rehearsal e12_released_pkg
          e13_release_pipeline
"""
import json
import os
import pathlib
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

STRICT = os.environ.get("WB_PHASE_E_STRICT") == "1"

#: Windows has no AF_UNIX at all: `socket.AF_UNIX` simply does not exist there,
#: so every gateway-socket half of this suite must skip instead of crashing on
#: an AttributeError. `wb_proxy.py` carries the same guard (it sets
#: `GatewayUnixHTTPServer = None` and only logs that --unix-socket is ignored),
#: so the panel itself still starts on such a host - only that one transport
#: is missing. The e10 section rehearses exactly this shape on Linux by
#: deleting socket.AF_UNIX / socketserver.UnixStreamServer in a subprocess.
HAS_UNIX = hasattr(socket, "AF_UNIX")

#: The fpk helpers are not guaranteed either: a Windows runner has `tar`, but
#: `sha256sum`/`md5sum`/`bash` only when Git's usr/bin happens to be on PATH.
#: Digests therefore go through hashlib (no external tool), and the two
#: external steps are skipped when their tool is absent.
HAS_TAR = shutil.which("tar") is not None
HAS_BASH = shutil.which("bash") is not None


def sha256_file(path):
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def md5_file(path):
    import hashlib
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def needs_unix(label):
    """Skip (and answer True) when this host has no AF_UNIX transport.

    Recorded as SKIP, never as FAIL: the missing socket is the platform's
    shape, not a defect in the thing under test.
    """
    if HAS_UNIX:
        return False
    skip(label, "本平台没有 socket.AF_UNIX（Windows）：网关 socket 传输不存在")
    return True


def needs_root(label):
    """Skip (and answer True) when the process cannot switch uids.

    `setpriv --reuid` needs privileges: on a CI runner (and on Windows, which
    has no `geteuid` at all) the probe would fail with 127 instead of proving
    anything about the peer check.
    """
    if getattr(os, "geteuid", lambda: -1)() == 0:
        return False
    skip(label, "切 uid 需要 root（CI runner 非 root）：本段跳过")
    return True


def git_run(args, cwd=None, timeout=180):
    """Run git in `cwd` (default the tree); return the CompletedProcess."""
    return subprocess.run(["git"] + list(args), cwd=cwd or ROOT,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          timeout=timeout)


def git_text(args, cwd=None, timeout=180):
    """git, decoded; (returncode, stdout+stderr)."""
    done = git_run(args, cwd=cwd, timeout=timeout)
    return done.returncode, done.stdout.decode("utf-8", "replace").strip()


def is_shallow(cwd=None):
    """True when this checkout has no history (actions/checkout depth 1)."""
    rc, out = git_text(["rev-parse", "--is-shallow-repository"], cwd=cwd)
    lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
    return rc == 0 and bool(lines) and lines[0] == "true"

#: The final package WP-E3 produces; overridable so the suite can be pointed
#: at a candidate while the packager iterates.
PKG_PATH = os.environ.get("WB_PKG") or os.path.join(
    ROOT, "dist", "WorkBuddy2API-Hub_1.6.17.1_all.fpk")

BASE_PREFIX = "/app/workbuddy2api"
PANEL_PASSWORD = "phase-e-verify-pw"
#: Suites that are ours (gateway / platform / json import / model credit /
#: gateway ui) and the ones the merge left red. Both lists are asserted to
#: actually run: a suite that disappears (or is skipped) must not pass.
OUR_SUITES = ["_test_gateway.py", "_test_gateway_ui.js",
              "_test_json_account_import.py", "_test_model_credit.py",
              "_test_platform_import.py"]

PASS = 0
FAIL = 0
SKIP = 0
FAILED = []

SECTIONS = []
_CUR = [None, 0, 0, 0]


def check(label, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        _CUR[1] += 1
        print("  [PASS] " + label)
    else:
        FAIL += 1
        _CUR[2] += 1
        FAILED.append(label)
        print("  [FAIL] " + label + (("  -> " + str(extra)) if extra != "" else ""))


def note(label, value):
    print("  [NOTE] %s = %r" % (label, value))


def skip(label, why):
    global SKIP
    SKIP += 1
    _CUR[3] += 1
    print("  [SKIP] %s  (%s)" % (label, why))


def gate(label, why):
    """A missing artefact: SKIP while owners still write, FAIL in strict mode."""
    if STRICT:
        check(label, False, why)
    else:
        skip(label, why)


def section(title):
    """Flush the counters of the previous section and start a new one."""
    if _CUR[0] is not None:
        SECTIONS.append((_CUR[0], _CUR[1], _CUR[2], _CUR[3]))
    _CUR[0] = title
    _CUR[1] = _CUR[2] = _CUR[3] = 0
    print("\n== %s ==" % title)


REGISTRY = []


def register(label, detail):
    """A known divergence worth telling the Lead about, not a PASS or a FAIL."""
    REGISTRY.append((label, detail))
    print("  [REG]  %s  (%s)" % (label, detail))


# ---------------------------------------------------------------------------
# HTTP over a real socket (TCP or AF_UNIX), raw so 4xx bodies stay visible
# ---------------------------------------------------------------------------
def _read_all(sock):
    chunks = []
    while True:
        try:
            part = sock.recv(65536)
        except socket.timeout:
            break
        if not part:
            break
        chunks.append(part)
    return b"".join(chunks)


def _split_response(raw):
    head, _, body = raw.partition(b"\r\n\r\n")
    lines = head.split(b"\r\n")
    status = 0
    if lines and lines[0].startswith(b"HTTP/"):
        try:
            status = int(lines[0].split(b" ")[1])
        except (IndexError, ValueError):
            status = 0
    headers = {}
    for line in lines[1:]:
        if b":" in line:
            k, _, v = line.partition(b":")
            headers[k.strip().lower().decode("latin-1")] = v.strip().decode("latin-1")
    return status, headers, body.decode("utf-8", "replace")


def _send(sock, method, path, headers=None, body=None):
    blob = b""
    if body is not None:
        blob = body.encode("utf-8") if isinstance(body, str) else body
    hdrs = [("Host", "localhost"), ("Connection", "close")]
    hdrs += list((headers or {}).items())
    if blob:
        hdrs.append(("Content-Length", str(len(blob))))
    req = "%s %s HTTP/1.1\r\n" % (method, path)
    req += "".join("%s: %s\r\n" % (k, v) for k, v in hdrs)
    req += "\r\n"
    sock.sendall(req.encode("utf-8") + blob)
    raw = _read_all(sock)
    return _split_response(raw)


def unix_request(sock_path, path, method="GET", headers=None, body=None, timeout=30):
    if not HAS_UNIX:
        # Callers guard with needs_unix() first; raising here keeps a future
        # unguarded caller loud instead of silently testing nothing.
        raise RuntimeError("socket.AF_UNIX is unavailable on this platform")
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect(sock_path)
        return _send(sock, method, path, headers, body)
    finally:
        sock.close()


def tcp_request(port, path, method="GET", headers=None, body=None, timeout=30):
    sock = socket.create_connection(("127.0.0.1", port), timeout=timeout)
    sock.settimeout(timeout)
    try:
        return _send(sock, method, path, headers, body)
    finally:
        sock.close()


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def as_json(text):
    try:
        return json.loads(text)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Panel under test: real wb_proxy.py on a temp port + temp unix socket
# ---------------------------------------------------------------------------
class Panel(object):
    """The gateway setup fnOS creates: a TCP port plus an AF_UNIX socket."""

    def __init__(self, base_path=BASE_PREFIX, as_uid=None, extra_args=(),
                 env_overrides=None):
        self.tmp = tempfile.mkdtemp(prefix="wb-phaseE-panel-")
        os.chmod(self.tmp, 0o777)
        self.accounts = os.path.join(self.tmp, "accounts")
        self.usage = os.path.join(self.tmp, "usage")
        for path in (self.accounts, self.usage):
            os.makedirs(path, exist_ok=True)
            os.chmod(path, 0o777)
        self.port = free_port()
        self.base_path = base_path
        # No AF_UNIX: the panel runs TCP-only (wb_proxy ignores --unix-socket on
        # such a host), so the harness must not wait for a socket that will
        # never appear.
        self.sock = os.path.join(self.tmp, "app.sock") if HAS_UNIX else None
        self.logpath = os.path.join(self.tmp, "server.log")
        self.as_uid = as_uid
        self.extra_args = list(extra_args)
        self.env_overrides = dict(env_overrides or {})
        self.proc = None
        self.token = None
        self.start()

    # -- lifecycle ---------------------------------------------------------
    def command(self):
        cmd = [sys.executable, os.path.join(ROOT, "wb_proxy.py"),
               "--host", "127.0.0.1", "--port", str(self.port),
               "--accounts-dir", self.accounts,
               "--usage-dir", self.usage,
               "--panel-password", PANEL_PASSWORD]
        if self.sock:
            cmd += ["--unix-socket", self.sock]
        if self.base_path:
            cmd += ["--base-path", self.base_path]
        cmd += self.extra_args
        if self.as_uid is not None:
            cmd = ["setpriv", "--reuid=%d" % self.as_uid,
                   "--regid=%d" % self.as_uid, "--clear-groups"] + cmd
        return cmd

    def start(self):
        env = dict(os.environ)
        for key in ("ACCOUNTS_DIR", "USAGE_DIR"):
            env.pop(key, None)
        for key, value in self.env_overrides.items():
            if value is None:
                env.pop(key, None)
            else:
                env[key] = value
        self.log = open(self.logpath, "wb")
        self.proc = subprocess.Popen(self.command(), cwd=ROOT, env=env,
                                     stdout=self.log, stderr=subprocess.STDOUT)

    def wait_ready(self, timeout=60):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.proc.poll() is not None:
                return False
            try:
                status, _, _ = tcp_request(self.port, "/health", timeout=5)
                if status == 200 and (self.sock is None
                                      or os.path.exists(self.sock)):
                    return True
            except (OSError, socket.error):
                pass
            time.sleep(0.3)
        return False

    def restart(self):
        self.stop()
        self.start()
        ok = self.wait_ready()
        self.token = None
        return ok

    def stop(self):
        if self.proc is None:
            return
        try:
            self.proc.terminate()
            self.proc.wait(timeout=10)
        except Exception:
            try:
                self.proc.kill()
            except Exception:
                pass
        try:
            self.log.close()
        except Exception:
            pass
        self.proc = None

    def output(self):
        try:
            with open(self.logpath, encoding="utf-8", errors="replace") as fh:
                return fh.read()
        except OSError:
            return ""

    # -- requests ----------------------------------------------------------
    def unix(self, path, method="GET", headers=None, body=None):
        if not HAS_UNIX:
            raise RuntimeError("socket.AF_UNIX is unavailable on this platform")
        return unix_request(self.sock, path, method, headers, body)

    def tcp(self, path, method="GET", headers=None, body=None):
        return tcp_request(self.port, path, method, headers, body)

    def login(self):
        status, _, text = self.tcp("/panel/login", "POST",
                                   {"Content-Type": "application/json"},
                                   json.dumps({"password": PANEL_PASSWORD}))
        js = as_json(text) or {}
        self.token = js.get("token")
        return status, self.token

    def panel_headers(self):
        if self.token is None:
            self.login()
        return {"X-Panel-Token": self.token or ""}


def seed_account(panel, uid, realm="cn", nickname=None):
    """Drop one account file straight into the temp accounts dir."""
    from wb_accounts import REALM_CONFIGS
    cfg = REALM_CONFIGS.get(realm) or {}
    row = {"uid": uid, "nickname": nickname or uid, "realm": realm,
           "domain": cfg.get("domain") or "www.codebuddy.cn",
           "accessToken": "a.b.c", "refreshToken": "r.r.r",
           "expiresAt": int(time.time() * 1000) + 7200000}
    path = os.path.join(panel.accounts, uid + ".json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(row, fh, ensure_ascii=False, indent=2)
    return path


def _read_account_file(directory, uid):
    """Read back what the pool wrote for one uid (uid is sanitised into a name)."""
    name = re.sub(r"[^A-Za-z0-9_-]", "_", str(uid)).strip("_ ") + ".json"
    with open(os.path.join(directory, name), encoding="utf-8") as fh:
        return json.load(fh)


def dashboard_source():
    path = os.environ.get("WB_DASHBOARD_PATH") or os.path.join(ROOT, "dashboard.html")
    with open(path, encoding="utf-8", errors="replace") as fh:
        return fh.read()


# ---------------------------------------------------------------------------
# e1 — the whole bundled suite set
# ---------------------------------------------------------------------------
def e1_suites():
    section("WP-E4 e1 — python3 tests/run_all.py --jobs 4 全量套件")
    logs = os.path.join(tempfile.gettempdir(), "wb-e-suites")
    if os.environ.get("WB_E1_NESTED") == "1":
        # run_all runs this very file, so a full run started from here would
        # recurse forever; the outer run already covers every suite.
        skip("全量套件", "嵌套于外层 run_all，避免递归")
        return
    cmd = [sys.executable, os.path.join(HERE, "run_all.py"), "--jobs", "4",
           "--logs", logs]
    # Smoke mode: narrow the run to one suite so the harness itself can be
    # exercised while the writers are still editing the tree.
    smoke = os.environ.get("WB_E1_PATTERN")
    if smoke:
        cmd.append(smoke)
    started = time.time()
    env = dict(os.environ, WB_E1_NESTED="1")
    done = subprocess.run(cmd, cwd=ROOT, env=env, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, timeout=1800)
    text = done.stdout.decode("utf-8", "replace")
    elapsed = time.time() - started
    tail = [ln for ln in text.splitlines() if ln.strip()][-4:]
    note("run_all 尾行", tail)
    note("耗时", "%.1fs" % elapsed)
    match = re.search(r"(\d+) passed, (\d+) failed, (\d+) skipped", text)
    if not match:
        check("run_all 打印了汇总行", False, text[-400:])
        return
    if smoke:
        note("smoke 模式（WB_E1_PATTERN=%s）" % smoke, tail)
        check("run_all 冒烟退出码 0", done.returncode == 0, text[-300:])
        return
    passed, failed, skipped = (int(g) for g in match.groups())
    tree_suites = sorted(n for n in os.listdir(HERE)
                         if n.startswith("_test_") and n.endswith((".py", ".js")))
    me = os.path.basename(__file__)
    note("树里的套件数", len(tree_suites))
    note("run_all 计数", "passed=%d failed=%d skipped=%d" % (passed, failed, skipped))
    check("run_all: 计数自洽（passed+failed+skipped == 套件数 %d）" % len(tree_suites),
          passed + failed + skipped == len(tree_suites),
          (passed, failed, skipped))
    # This gate must not demand that it is itself green: run_all counts this
    # very file, so "0 failed" would mean "I pass because I pass" - a red gate
    # could never report the truth about anything else. Everything except this
    # file has to be green, and this file has to be counted as passed.
    failed_lines = [ln.strip() for ln in text.splitlines()
                    if ln.strip().startswith("[FAIL]")]
    others = [ln for ln in failed_lines if me not in ln]
    note("run_all 失败的套件", failed_lines)
    check("run_all: 除本套件外没有失败的套件（排除自身，避免自指）",
          others == [], others)
    own_lines = [ln.strip() for ln in text.splitlines() if me in ln]
    check("run_all: 本套件在 run_all 内被算作 passed（没有被跳过或超时）",
          any("[PASS]" in ln for ln in own_lines)
          and not any("[FAIL]" in ln or "timed out" in ln for ln in own_lines),
          own_lines[:3])
    check("run_all: 0 skipped", skipped == 0)
    check("run_all 退出码 0（本套件红时只允许它自己是唯一红）",
          done.returncode == 0 or (others == [] and failed <= 1), done.returncode)
    for name in OUR_SUITES:
        line = next((ln for ln in text.splitlines() if name in ln), "")
        check("我们的套件真的跑了: %s" % name,
              "[PASS]" in line and "[skip]" not in line, line.strip())


# ---------------------------------------------------------------------------
# e2 — the passwordless gateway rule, and the forgeries it must survive
# ---------------------------------------------------------------------------
def e2_gateway():
    section("WP-E4 e2 — 网关免密口径（socket peer 即登录 / TCP 伪造仍被拒）")
    panel = Panel()
    if not panel.wait_ready():
        check("面板起来了", False, panel.output()[-800:])
        panel.stop()
        return
    try:
        # 1.-3. The App Center path: socket, no X-Trim-Username at all. This is
        # the AF_UNIX half; the TCP forgeries below run everywhere.
        if not needs_unix("e2 的 socket 免密用例（socket 无头即已登录）"):
            # 1. The App Center path: socket, no X-Trim-Username at all.
            status, _, text = panel.unix(BASE_PREFIX + "/panel/status")
            js = as_json(text) or {}
            check("socket 不带 X-Trim-Username -> 200", status == 200, status)
            check("socket -> authenticated: true", js.get("authenticated") is True, js)
            check("socket -> via_gateway: true", js.get("via_gateway") is True, js)
            check("socket 无头 -> gateway_user 是空串（没有用户名可显示）",
                  js.get("gateway_user") == "", js.get("gateway_user"))

            # 2. The header is still honoured for the display name.
            status, _, text = panel.unix(BASE_PREFIX + "/panel/status",
                                         headers={"X-Trim-Username": "ccrab"})
            js = as_json(text) or {}
            check("socket 带头 -> authenticated 仍为 true", js.get("authenticated") is True)
            check("socket 带头 -> gateway_user 显示该用户", js.get("gateway_user") == "ccrab",
                  js.get("gateway_user"))

            # 3. A management route must be reachable without any token over the socket.
            status, _, text = panel.unix(BASE_PREFIX + "/accounts")
            check("socket 无 token 也能进管理路由（200）", status == 200, status)

        # 4. Forgery: the same header over TCP must buy nothing.
        status, _, text = panel.tcp("/panel/status",
                                    headers={"X-Trim-Username": "root"})
        js = as_json(text) or {}
        check("TCP 伪造 X-Trim-Username -> authenticated: false",
              js.get("authenticated") is False, js)
        check("TCP 伪造头不被采纳为用户名", js.get("gateway_user") == "",
              js.get("gateway_user"))
        check("TCP 仍报 via_gateway: false", js.get("via_gateway") is False)
        status, _, _ = panel.tcp("/accounts", headers={"X-Trim-Username": "root"})
        check("TCP 带伪造头进管理路由 -> 401", status == 401, status)

        # 5. The escape hatch still works: panel password over TCP.
        status, token = panel.login()
        check("TCP /panel/login 拿到 token", status == 200 and bool(token), status)
        status, _, text = panel.tcp("/panel/status",
                                    headers={"X-Panel-Token": token or ""})
        js = as_json(text) or {}
        check("TCP 带面板 token -> authenticated: true", js.get("authenticated") is True)
        status, _, _ = panel.tcp("/accounts", headers={"X-Panel-Token": token or ""})
        check("TCP 带面板 token 进管理路由 -> 200", status == 200, status)
    finally:
        panel.stop()


PEER_CLIENT = """\
import json, socket, sys
s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
s.settimeout(20)
s.connect(sys.argv[1])
s.sendall(("GET %s/panel/status HTTP/1.1\\r\\nHost: h\\r\\nConnection: close\\r\\n\\r\\n"
           % sys.argv[2]).encode())
data = b""
while True:
    try:
        chunk = s.recv(65536)
    except socket.timeout:
        break
    if not chunk:
        break
    data += chunk
body = data.decode("utf-8", "replace").split("\\r\\n\\r\\n", 1)[-1]
print(body.strip())
"""


def _probe_as_uid(panel, client_path, uid):
    """Run the AF_UNIX probe process under `uid`; return (rc, status, payload)."""
    out = subprocess.run(
        ["setpriv", "--reuid=%d" % uid, "--regid=%d" % uid, "--clear-groups",
         sys.executable, client_path, panel.sock, BASE_PREFIX],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60)
    body = out.stdout.decode("utf-8", "replace").strip()
    js = as_json(body) or {}
    return out.returncode, js.get("authenticated"), js


def e2_peer_matrix():
    """The peer-uid rule itself, exercised with real foreign uids.

    The socket is mode 0666, so *any* local user can connect to it — the whole
    security of the passwordless rule rests on the peer check. A foreign local
    uid must therefore be refused even though it can reach the socket, and uid
    0 (the gateway) must be accepted without any header.
    """
    section("WP-E4 e2b — peer uid 矩阵（root=网关放行 / 陌生 uid 必须被拒）")
    if needs_unix("e2b peer uid 矩阵"):
        return
    if not shutil.which("setpriv"):
        gate("setpriv 可用（测试陌生 uid 的必要条件）", "setpriv 不存在")
        return
    if needs_root("e2b peer uid 矩阵（要 setpriv 切到陌生 uid 连 socket）"):
        return
    panel = Panel()
    if not panel.wait_ready():
        check("面板起来了", False, panel.output()[-600:])
        panel.stop()
        return
    try:
        client = os.path.join(panel.tmp, "client.py")
        with open(client, "w", encoding="utf-8") as fh:
            fh.write(PEER_CLIENT)
        os.chmod(client, 0o755)

        rc, authed, js = _probe_as_uid(panel, client, 0)
        check("uid 0（=网关）连 socket -> authenticated: true",
              rc == 0 and authed is True, (rc, js))
        rc, authed, js = _probe_as_uid(panel, client, 1000)
        note("陌生 uid 1000 的 /panel/status", js)
        check("陌生 uid 1000 连 socket -> authenticated: false",
              rc == 0 and authed is False, (rc, js))
        log = panel.output()
        note("服务端 peer 判定日志",
             [ln for ln in log.splitlines() if "peer uid" in ln])
        check("服务端记录了陌生 peer 被忽略",
              any("peer uid 1000" in ln and "ignored" in ln for ln in log.splitlines()),
              [ln for ln in log.splitlines() if "peer uid" in ln])
        # A foreign uid must also be refused on a management route.
        out = subprocess.run(
            ["setpriv", "--reuid=1000", "--regid=1000", "--clear-groups",
             sys.executable, client, panel.sock, BASE_PREFIX + "/accounts"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60)
        body = out.stdout.decode("utf-8", "replace")
        check("陌生 uid 进管理路由拿不到账号数据",
              "access_token" not in body and "accounts" not in body.lower(),
              body[:200])
    finally:
        panel.stop()

    # The "app's own uid" half of the rule needs the server itself to run as a
    # non-root user, which needs a traversable checkout. Report honestly.
    app_uid = 65534
    probe = Panel(as_uid=app_uid)
    if probe.wait_ready(15):
        try:
            client = os.path.join(probe.tmp, "client.py")
            with open(client, "w", encoding="utf-8") as fh:
                fh.write(PEER_CLIENT)
            os.chmod(client, 0o755)
            rc, authed, js = _probe_as_uid(probe, client, app_uid)
            check("应用自身 uid（%d）连 socket -> authenticated: true" % app_uid,
                  rc == 0 and authed is True, (rc, js))
            rc, authed, js = _probe_as_uid(probe, client, 1000)
            check("非 root 服务端下陌生 uid -> authenticated: false",
                  rc == 0 and authed is False, (rc, js))
        finally:
            probe.stop()
    else:
        probe.stop()
        gate("以 uid %d 起面板复现「应用自身 uid」分支" % app_uid,
             "父目录不可遍历（drwx------/d000）：" + probe.output().strip()[:120])


def _js_function(src, name):
    """Pull a top-level `function name(...) {...}` out of the dashboard."""
    m = re.search(r"\bfunction\s+%s\s*\(" % re.escape(name), src)
    if not m:
        return None
    start = src.index("{", m.end() - 1)
    depth = 0
    for i in range(start, len(src)):
        if src[i] == "{":
            depth += 1
        elif src[i] == "}":
            depth -= 1
            if depth == 0:
                return src[m.start():i + 1]
    return None


def node_call(body, fn, cases):
    """Evaluate `fn` over `cases` in node; returns (values, error)."""
    script = ("%s\nconst CASES = %s;\n"
              "process.stdout.write(JSON.stringify("
              "CASES.map(function(c){ return %s.apply(null, c); })));\n"
              % (body, json.dumps(cases), fn))
    try:
        done = subprocess.run(["node", "-e", script], stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, timeout=90)
    except (OSError, subprocess.SubprocessError) as exc:
        return None, str(exc)
    text = done.stdout.decode("utf-8", "replace")
    if done.returncode != 0:
        return None, text[-300:]
    try:
        return json.loads(text), ""
    except ValueError as exc:
        return None, "%s: %s" % (exc, text[-200:])


# ---------------------------------------------------------------------------
# e3 — the mount point contract
# ---------------------------------------------------------------------------
def e3_mount():
    section("WP-E4 e3 — 挂载前缀契约（<base href> / __WB_BASE__ / 直连不注）")
    panel = Panel()
    if not panel.wait_ready():
        check("面板起来了", False, panel.output()[-800:])
        panel.stop()
        return
    try:
        # Mounted: the socket + prefix the App Center iframe uses.
        if not needs_unix("e3 的挂载态 socket 用例（<base href> / __WB_BASE__）"):
            status, _, body = panel.unix(BASE_PREFIX + "/")
            check("socket GET %s/ -> 200" % BASE_PREFIX, status == 200, status)
            check('挂载时注入 <base href="%s/">' % BASE_PREFIX,
                  ('<base href="%s/">' % BASE_PREFIX) in body)
            check('挂载时 window.__WB_BASE__="%s"' % BASE_PREFIX,
                  ('window.__WB_BASE__="%s"' % BASE_PREFIX) in body, body[:0] or "")
            check("挂载时 window.__WB_VIA_GATEWAY__=true",
                  "window.__WB_VIA_GATEWAY__=true" in body)
            # The same document without the trailing slash must still work.
            status, _, body2 = panel.unix(BASE_PREFIX)
            check("socket GET %s（无斜杠）-> 200" % BASE_PREFIX, status == 200, status)
            # Routing under the prefix strips it: /panel/status answered above.
            status, _, text = panel.unix(BASE_PREFIX + "/health")
            check("前缀被剥掉后业务路由可达（/health 200）", status == 200, status)

            # POST under the prefix must be routed the same way: /panel/login is
            # the first call the App Center iframe makes.
            status, _, text = panel.unix(BASE_PREFIX + "/panel/login", method="POST",
                                         headers={"Content-Type": "application/json"},
                                         body=json.dumps({"password": PANEL_PASSWORD}))
            check("挂载态 POST <base>/panel/login -> 200 且发 token",
                  status == 200 and '"token"' in text, (status, text[:120]))
            # A forged prefix must not be mistaken for the mount point.
            status, _, text = panel.unix("/app/other/panel/status")
            check("伪造前缀 /app/other/panel/status 不被当成面板路由",
                  status != 200 or '"authenticated": true' not in text, (status, text[:80]))

        # Direct TCP: no <base href> (a plain port visit resolves at the root).
        status, _, body3 = panel.tcp("/")
        check("直连 TCP GET / -> 200", status == 200, status)
        check("直连时不注 <base href>（真标签；注释里的字样不算）",
              not re.search(r"""<base\s+href\s*=\s*["'][^"']*["']""", body3))
        check('直连时 window.__WB_BASE__=""', 'window.__WB_BASE__=""' in body3)
        check("直连时 window.__WB_VIA_GATEWAY__=false",
              "window.__WB_VIA_GATEWAY__=false" in body3)
    finally:
        panel.stop()

    # The prefix is configurable, not hard-wired: a trailing slash must be
    # normalised, another prefix must still work, and a socket caller that
    # leaves the prefix off (fnOS may forward either way) must not break.
    for label, base in (("尾斜杠", BASE_PREFIX + "/"), ("另一前缀", "/app/wb-alt")):
        if not HAS_UNIX:
            skip("base_path=%s 的 socket 用例" % base,
                 "本平台没有 socket.AF_UNIX（Windows）：前缀契约由直连 TCP 段覆盖")
            continue
        alt = Panel(base_path=base)
        if not alt.wait_ready():
            check("base_path=%s 的面板起来了" % base, False, alt.output()[-400:])
            alt.stop()
            continue
        try:
            clean = base.rstrip("/")
            st, _, body = alt.unix(clean + "/panel/status")
            js = as_json(body) or {}
            check("base_path=%s：该前缀下 socket 已登录" % label,
                  st == 200 and js.get("authenticated") is True, (st, body[:120]))
            st, _, body = alt.unix(clean + "/")
            check("base_path=%s：<base href> 用归一化后的前缀" % label,
                  st == 200 and ('<base href="%s/">' % clean) in body,
                  re.findall(r"<base[^>]*>", body)[:1])
            st, _, _ = alt.unix("/panel/status")
            check("base_path=%s：socket 上不带前缀直呼仍可用" % label, st == 200, st)
        finally:
            alt.stop()

    # Static: every absolute fetch in the dashboard has to follow the prefix.
    try:
        src = dashboard_source()
    except OSError as exc:
        gate("能读到 dashboard.html", str(exc))
        return
    note("dashboard.html 字节数", len(src.encode("utf-8")))
    literals = re.findall(r"""fetch\(\s*['"](/[^'"]*)['"]""", src)
    check("没有直接 fetch('绝对路径') 的调用点（必须走前缀包装）",
          literals == [], literals)
    check("dashboard 引用了 window.__WB_BASE__", "__WB_BASE__" in src)
    # Every fetch() must hand its URL to the prefix helper: one raw literal
    # anywhere re-introduces the App Center 404 on the NAS.
    calls = re.findall(r"""fetch\(\s*([^,)]*)""", src)
    naked = [x.strip() for x in calls if "wbUrl(" not in x]
    check("每个 fetch() 都经过 wbUrl() 前缀包装", naked == [], naked)
    note("fetch() 调用点数", len(calls))
    # The two panel request helpers are the choke point for every other call
    # site, so they have to route through the prefix helper themselves.
    for helper in ("getJSON", "postJSON"):
        body = _js_function(src, helper)
        check("%s() 经由 wbUrl() 打请求" % helper,
              bool(body) and "wbUrl(" in body, (body or "")[:120])
    check("没有 XMLHttpRequest / sendBeacon / location.assign 这类漏网调用",
          not re.search(r"new\s+XMLHttpRequest|sendBeacon\s*\(|location\.assign\s*\(", src))
    for pat, what in ((r"""new\s+EventSource\s*\($""", "EventSource"),
                      (r"""new\s+WebSocket\s*\($""", "WebSocket")):
        hits = re.findall(pat, src)
        check("没有裸用 %s（需自带前缀）" % what, hits == [], hits)
    # Stub-DOM: the helper itself, evaluated with and without the injected
    # global, so "follows the prefix" is a runtime fact, not a grep.
    base_block = re.search(r"const WB_BASE = \(function\(\)\{.*?\}\)\(\);", src, re.S)
    wburl = _js_function(src, "wbUrl")
    check("看板里有 WB_BASE 常量与 wbUrl()", base_block is not None and wburl is not None)
    if base_block and wburl:
        cases = [["/accounts"], ["accounts"], ["/panel/login"], ["/?tab=x"],
                 ["https://other.example/keep"], ["//cdn.example/keep"], [""]]
        mounted, err1 = node_call(
            "var window = {__WB_BASE__: '%s'};" % BASE_PREFIX
            + base_block.group(0) + "\n" + wburl, "wbUrl", cases)
        direct, err2 = node_call(
            "var window = {__WB_BASE__: ''};" + base_block.group(0) + "\n" + wburl,
            "wbUrl", cases)
        check("wbUrl() 能在 node 里求值", err1 == "" and err2 == "" and mounted, err1 or err2)
        if mounted and direct:
            want = [BASE_PREFIX + "/accounts", BASE_PREFIX + "/accounts",
                    BASE_PREFIX + "/panel/login", BASE_PREFIX + "/?tab=x",
                    "https://other.example/keep", "//cdn.example/keep",
                    BASE_PREFIX + "/"]
            check("挂载态所有站内路径都带前缀（外域/协议相对不动）",
                  mounted == want, mounted)
            check("直连态不加前缀（原样）",
                  direct == ["/accounts", "/accounts", "/panel/login", "/?tab=x",
                             "https://other.example/keep", "//cdn.example/keep", "/"],
                  direct)
    for needle in ('"/panel/login"', '"/panel/status"'):
        # They may appear inside the prefix helper, but never as a bare fetch().
        check("fetch(%s) 不再裸用" % needle,
              ('fetch(%s' % needle) not in src)


# ---------------------------------------------------------------------------
# e4 — per-million-token credit column
# ---------------------------------------------------------------------------
def e4_credit():
    section("WP-E4 e4 — 每 M tokens 积分（后端 credit 累加 / 严格 JSON / 界面除零）")
    import wb_proxy as P

    # --- in-process: fold a forged usage log ------------------------------
    tmp = tempfile.mkdtemp(prefix="wb-phaseE-usage-")
    log = os.path.join(tmp, "usage.jsonl")
    now = time.time()
    rows = [
        # 1) the reference row: 2M tokens for 42 credits
        {"at": now, "model": "glm-5.3", "total_tokens": 2_000_000,
         "prompt_tokens": 1_000_000, "completion_tokens": 1_000_000,
         "credit": 42.0, "outcome": "completed", "key": "k1", "account": "u1"},
        # 2) an all-zero row: the "per M tokens" denominator is zero here
        {"at": now, "model": "glm-5.3", "total_tokens": 0, "credit": 0.0,
         "outcome": "completed", "key": "k1", "account": "u1"},
        # 3) a second reference row to prove accumulation
        {"at": now, "model": "glm-5.3", "total_tokens": 2_000_000,
         "credit": 42.0, "outcome": "completed", "key": "k1", "account": "u1"},
        # 4) a failure the upstream had already billed for
        {"at": now, "model": "kimi-k3", "total_tokens": 10, "credit": 5.0,
         "outcome": "failed", "key": "k1", "account": "u1"},
        # 5) a pre-`outcome` row: the error marker is the only signal
        {"at": now, "model": "kimi-k3", "total_tokens": 20, "credit": 3.0,
         "error": "upstream 500", "key": "k1", "account": "u1"},
        # 6) a client cancellation: incomplete counts, must be skipped whole
        {"at": now, "model": "kimi-k3", "total_tokens": 30, "credit": 7.0,
         "outcome": "client_aborted", "key": "k1", "account": "u1"},
    ]
    with open(log, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")
    prev_log = getattr(P, "USAGE_LOG", None)
    try:
        P.USAGE_LOG = log
        all_summary = P._new_analytics_stat()
        window_summary = P._new_analytics_stat()
        acct_map, model_map = {}, {}
        P._scan_usage_log(all_summary, window_summary, acct_map, model_map)
        glm = model_map.get("glm-5.3") or {}
        glm_all = glm.get("all_time") or {}
        note("model_map 键", sorted(model_map))
        note("glm-5.3.all_time", {k: v for k, v in glm_all.items()
                                  if k in ("requests", "errors", "total_tokens", "credit")})
        check("逐模型统计带 credit（glm-5.3 all_time.credit == 84）",
              abs((glm_all.get("credit") or 0) - 84.0) < 1e-6, glm_all.get("credit"))
        check("逐模型统计带 credit（window.credit == 84）",
              abs(((glm.get("window") or {}).get("credit") or 0) - 84.0) < 1e-6,
              (glm.get("window") or {}).get("credit"))
        check("模型维度 tokens 正确（4,000,000）",
              glm_all.get("total_tokens") == 4_000_000, glm_all.get("total_tokens"))
        check("完成数 requests == 3", glm_all.get("requests") == 3,
              glm_all.get("requests"))
        # kimi-k3: one failed + one legacy-error row, both 0 x-errors; the
        # aborted row is dropped before any folding.
        kimi_all = (model_map.get("kimi-k3") or {}).get("all_time") or {}
        note("kimi-k3.all_time", {k: v for k, v in kimi_all.items()
                                  if k in ("requests", "errors", "total_tokens", "credit")})
        check("失败行计入 errors 而非 requests", kimi_all.get("errors") == 2
              and kimi_all.get("requests") == 0,
              (kimi_all.get("requests"), kimi_all.get("errors")))
        check("失败行已计费 tokens 仍保留（10+20）",
              kimi_all.get("total_tokens") == 30, kimi_all.get("total_tokens"))
        check("被客户端取消的行整行跳过（tokens/credit 都不计）",
              kimi_all.get("total_tokens") == 30
              and abs((kimi_all.get("credit") or 0) - 8.0) < 1e-6,
              (kimi_all.get("total_tokens"), kimi_all.get("credit")))
        check("总计 credit 累加（84 + 8）",
              abs((all_summary.get("credit") or 0) - 92.0) < 1e-6,
              all_summary.get("credit"))
        check("窗口总计 credit 也累加（92）",
              abs((window_summary.get("credit") or 0) - 92.0) < 1e-6,
              window_summary.get("credit"))
    except Exception as exc:  # noqa: BLE001 - report, do not crash the suite
        check("_scan_usage_log 可被调用并给出 credit", False, repr(exc))
    finally:
        P.USAGE_LOG = prev_log
        shutil.rmtree(tmp, ignore_errors=True)

    # --- end to end: the analytics route must emit strict JSON ------------
    panel = Panel()
    if not panel.wait_ready():
        check("面板起来了", False, panel.output()[-600:])
        panel.stop()
        return
    try:
        with open(os.path.join(panel.usage, "usage.jsonl"), "w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row) + "\n")
        headers = panel.panel_headers()
        status, _, text = panel.tcp("/usage/analytics", headers=headers)
        check("GET /usage/analytics -> 200", status == 200, (status, text[:200]))
        for literal in ("NaN", "Infinity", "-Infinity"):
            check("响应里没有非 JSON 字面量 %s" % literal, literal not in text)
        js = as_json(text)
        check("响应是合法 JSON", js is not None)
        if isinstance(js, dict):
            models = js.get("models") or []
            row = next((m for m in models if m.get("model") == "glm-5.3"), None)
            note("glm-5.3 行", {k: v for k, v in (row or {}).items()
                                if k in ("model", "window", "all_time")})
            check("/usage/analytics 的模型行带 credit",
                  isinstance(row, dict)
                  and abs(((row.get("all_time") or {}).get("credit") or 0) - 84.0) < 1e-6,
                  row)
            check("零 token 行不产生 NaN 比值（每 M tokens 可算）",
                  isinstance(row, dict)
                  and (row.get("all_time") or {}).get("total_tokens") == 4_000_000)
    finally:
        panel.stop()

    # --- dashboard: the column exists and guards the division -------------
    try:
        src = dashboard_source()
    except OSError as exc:
        gate("能读到 dashboard.html", str(exc))
        return
    check("看板出现每 M tokens 的积分列文案",
          re.search(r"每\s*M\s*tokens|每百万\s*tokens|/\s*M\s*tokens", src) is not None)
    check("每 M tokens 计算不是裸 credit/tokens（要除零保护）",
          re.findall(r"credit\s*/\s*tokens\b", src) == [],
          re.findall(r"credit\s*/\s*tokens\b", src))
    check("每 M tokens 列有表头 <th>",
          re.search(r"<th[^>]*>\s*每\s*M\s*tokens\s*积分", src) is not None)
    check("渲染点都走 fmtPerM()（不各自手算）", src.count("fmtPerM(") >= 2,
          src.count("fmtPerM("))
    body = _js_function(src, "creditPerM")
    fmt = _js_function(src, "fmtPerM")
    check("看板里有 creditPerM / fmtPerM 两个函数", body is not None and fmt is not None)
    if body and fmt:
        cases = [[42, 0], [42, None], [42, "abc"], [42, -5], [42, 1e9],
                 [0, 1000000], [None, 1000000], [42, 2000000], ["42", "2000000"],
                 [0.0, 0], [1e12, 1e12], [1, 3]]
        values, err = node_call(body + "\n" + fmt, "fmtPerM", cases)
        check("creditPerM/fmtPerM 能在 node 里求值", err == "" and values is not None, err)
        if values is not None:
            bad = [v for v in values if re.search(r"NaN|Infinity|undefined", str(v))]
            check("任何输入组合都不外泄 NaN/Infinity/undefined", bad == [], bad)
            check("tokens 为 0 / 非法 -> 显示「—」（没有比值，不是 0）",
                  values[0].endswith("—</span>") and values[1].endswith("—</span>")
                  and values[2].endswith("—</span>") and "—" not in str(values[4]),
                  values[:6])
            check("credit 为 0（真实 0）-> 显示 0 而不是「—」",
                  values[5].endswith(">0</span>") and values[6].endswith(">0</span>"),
                  values[5:7])
            check("正常比值可算：42 积分 / 2M tokens -> 21",
                  "21" in str(values[7]) and "21" in str(values[8]), values[7:9])


# ---------------------------------------------------------------------------
# e7 — what the passwordless rule must NOT open
# ---------------------------------------------------------------------------
def e7_hardening():
    section("WP-E4 e7 — 免密防线的加固面（socket 权限 / peer 不可读时的取向）")
    if not needs_unix("e7 的 socket 权限 / peer 判定用例"):
        panel = Panel()
        if not panel.wait_ready():
            check("面板起来了", False, panel.output()[-800:])
            panel.stop()
            return
        try:
            mode = os.stat(panel.sock).st_mode & 0o777
            check("gateway socket 是世界可写（0666）——peer 校验因此是唯一防线",
                  mode == 0o666, oct(mode))
            js = as_json(panel.unix(BASE_PREFIX + "/panel/status")[2]) or {}
            check("socket 上仍申报 panel_password_required=true（TCP 仍要密码）",
                  js.get("panel_password_required") is True, js)
            check("服务端日志记下了 peer 判定", "gateway: peer uid" in panel.output(),
                  panel.output()[-300:])
        finally:
            panel.stop()

    # In-process: the two transport-shape questions the socket cannot ask.
    import wb_proxy as P

    class _Sock(object):
        is_gateway = True
        base_path = BASE_PREFIX

    class _Tcp(object):
        is_gateway = False
        base_path = ""

    class _Handler(object):
        connection = None          # unix_peer_uid() cannot read a peer uid
        headers = {"X-Trim-Username": "root"}

    h = _Handler()
    h.server = _Sock()
    check("peer uid 读不到（connection=None）时不受信 —— fail closed",
          P.Handler._gateway_trusted(h) is False)
    h_nohdr = _Handler()
    h_nohdr.connection = None
    h_nohdr.headers = {}
    h_nohdr.server = _Sock()
    check("peer uid 读不到且没有 X-Trim-Username 头时也不受信",
          P.Handler._gateway_trusted(h_nohdr) is False)
    h.server = _Tcp()
    check("非 gateway 传输带伪造 X-Trim-Username 不受信",
          P.Handler._gateway_trusted(h) is False)
    # 端到端：网关 socket 通过 peer 校验后，连 /v1 的 api key 也一起免了
    # （_key_ok() -> _panel_ok() -> _gateway_trusted()）。TCP 上仍必须带 key。
    keyed = Panel(extra_args=("--api-key", "e2e-secret"))
    if not keyed.wait_ready():
        check("带 --api-key 的面板起来了", False, keyed.output()[-500:])
        keyed.stop()
    else:
        try:
            if HAS_UNIX:
                js = as_json(keyed.unix(BASE_PREFIX + "/panel/status")[2]) or {}
                check("带 key 的面板 api_key_set=true 且 socket 免密已登录",
                      js.get("api_key_set") is True and js.get("authenticated") is True, js)
                st, _, _ = keyed.unix(BASE_PREFIX + "/v1/models")
                check("socket 上 /v1 不带头也给 200（api key 一并被 peer 校验免掉）",
                      st == 200, st)
            else:
                skip("带 key 的面板 socket 免密用例",
                     "本平台没有 socket.AF_UNIX（Windows）")
            st, _, body = keyed.tcp("/v1/models")
            check("TCP 上 /v1 不带头仍 401（key 不可绕过）", st == 401, (st, body[:120]))
            st, _, _ = keyed.tcp("/v1/models",
                                 headers={"Authorization": "Bearer e2e-secret"})
            check("TCP 上 /v1 带正确 key 给 200", st == 200, st)
        finally:
            keyed.stop()

    register("网关 socket 上 /v1 的 api key 也被免掉",
             "WP-E1 把 _panel_ok() 从「socket 且带 X-Trim-Username 头」放宽为"
             "「socket 且 peer 校验通过」，而 _key_ok() 首行就是 _panel_ok()；"
             "于是 uid 0 或应用自身 uid 连 socket 打 /v1 不带头也 200（实测），"
             "TCP 仍 401。影响面＝本机 root 与应用自身用户，二者本来就能读配置；"
             "登记供裁决：若认为网关只该免面板密码而不该免 API key，"
             "应把 _key_ok() 的 _panel_ok() 前置改成只在直连时生效。")

    note("peer uid 不可读时的取向",
         "fail closed：uid is None 直接拒绝，日志 "
         "`sign-on ignored: peer credentials unavailable` —— "
         "WP-E1 采纳了 e7 提出的加固建议（响应里 gateway_user 仍为 \"\"）")


# e5 — the final package
# ---------------------------------------------------------------------------
PKG_MODULES = ["wb_pricing.py", "wb_atrest.py", "wb_modelsdev.py", "wb_prompt.py",
               "wb_ipintel.py", "wb_probes.py", "wb_catalog.py",
               "wb_fingerprint.py", "wb_identity.py", "wb_webagent.py",
               "wb_webtools.py", "wb_proxy.py", "wb_accounts.py",
               "dashboard.html", "wb_scheduler.py", "wb_settings.py",
               "wb_tasks.py", "wb_export.py"]


def e5_package():
    section("WP-E4 e5 — 最终 fpk：命名 / payload / 逐字节一致 / verify-fpk")
    if not os.path.exists(PKG_PATH):
        gate("最终包存在: %s" % PKG_PATH, "尚未构建")
        return
    note("包", os.path.basename(PKG_PATH))
    note("字节数", os.path.getsize(PKG_PATH))
    note("sha256", sha256_file(PKG_PATH))
    check("包名 = WorkBuddy2API-Hub_1.6.17.1_all.fpk",
          os.path.basename(PKG_PATH) == "WorkBuddy2API-Hub_1.6.17.1_all.fpk",
          os.path.basename(PKG_PATH))
    if not HAS_TAR:
        gate("tar 可用（解包 fpk 并与仓库逐字节比对的必要条件）", "本机没有 tar")
        return

    tmp = tempfile.mkdtemp(prefix="wb-phaseE-pkg-")
    try:
        done = subprocess.run(["tar", "-xf", PKG_PATH, "-C", tmp],
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        check("fpk 可解包", done.returncode == 0, done.stdout.decode()[-300:])
        listing_top = sorted(subprocess.run(["tar", "-tf", PKG_PATH],
                                            stdout=subprocess.PIPE).stdout
                             .decode("utf-8", "replace").splitlines())
        manifest = os.path.join(tmp, "manifest")
        if os.path.exists(manifest):
            text = open(manifest, encoding="utf-8", errors="replace").read()
            fields = dict(re.findall(r"^(\w+)\s*=\s*(.*)$", text, re.M))
            note("manifest", {k: fields.get(k) for k in
                              ("appname", "version", "platform", "display_name",
                               "service_port", "checksum")})
            check("manifest appname 仍是 workbuddy2api",
                  fields.get("appname") == "workbuddy2api", fields.get("appname"))
            check("manifest version = 1.6.17.1",
                  fields.get("version") == "1.6.17.1", fields.get("version"))
            shown = " ".join(str(fields.get(k, "")) for k in
                             ("display_name", "title", "name", "desc"))
            check("manifest/界面显示名含 WorkBuddy2API-Hub",
                  "WorkBuddy2API-Hub" in text, shown[:120])
            app = os.path.join(tmp, "app.tgz")
            if os.path.exists(app):
                check("manifest checksum == md5(app.tgz)",
                      fields.get("checksum") == md5_file(app),
                      fields.get("checksum"))
        app = os.path.join(tmp, "app.tgz")
        names = subprocess.run(["tar", "-tzf", app],
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        listing = names.stdout.decode("utf-8", "replace").splitlines()
        # server/** lives inside app.tgz; unpack it once to compare contents.
        payload_dir = os.path.join(tmp, "payload")
        os.makedirs(payload_dir, exist_ok=True)
        subprocess.run(["tar", "-xzf", app, "-C", payload_dir],
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        # The package carries the server tree at `server/`, the checkout keeps
        # it at the repo root: strip the prefix, and skip directory entries.
        server = [n for n in listing
                  if n.startswith("server/") and not n.endswith("/")]
        note("payload 条目数", len(listing))
        for module in PKG_MODULES:
            check("payload 含 server/%s" % module, ("server/" + module) in listing)
        check("payload 含 server/pricing/**",
              any(n.startswith("server/pricing/") and n != "server/pricing/" for n in listing))
        for bad in ("accounts/", "usage/", "docs/", "tests/", "dist/", "build/",
                    "scripts/", "fnos/", ".git/"):
            check("payload 不含 %s" % bad, not any(n.startswith(bad) for n in listing))
        # Every server file must equal the checkout byte for byte.
        mismatch = []
        for name in server:
            src = os.path.join(ROOT, name[len("server/"):])
            if not os.path.exists(src):
                mismatch.append(name + " (missing in repo)")
                continue
            with open(os.path.join(payload_dir, name), "rb") as fh:
                pack = fh.read()
            with open(src, "rb") as fh:
                repo = fh.read()
            if pack != repo:
                mismatch.append("%s (%d vs %d bytes)" % (name, len(pack), len(repo)))
        check("包内 server/** 与仓库逐字节一致", mismatch == [], mismatch)

        # The fnOS wrapper around the payload.
        top = [n for n in listing_top]
        for entry in ("manifest", "app.tgz"):
            check("fpk 顶层含 %s" % entry, entry in top)
        for prefix in ("ui/", "cmd/", "wizard/", "config/"):
            check("fpk 顶层含 %s**" % prefix,
                  any(n == prefix or n.startswith(prefix) for n in top))
        for script in ("cmd/main", "cmd/install_init", "cmd/upgrade_init",
                       "cmd/uninstall_init", "cmd/config_init",
                       "cmd/install_callback", "cmd/upgrade_callback"):
            check("fpk 含 %s" % script, script in top)
        # ui/config decides the mount point and the socket the App Center uses.
        mirror = os.path.join(tmp, "ui", "config")
        source = os.path.join(ROOT, "fnos", "ui", "config")
        if os.path.exists(mirror) and os.path.exists(source):
            same = open(mirror, "rb").read() == open(source, "rb").read()
            check("包内 ui/config 与 fnos/ui/config 一致", same)
            conf = open(mirror, encoding="utf-8", errors="replace").read()
            note("ui/config", conf.replace("\n", " ")[:200])
            check("ui/config 指向挂载前缀 %s" % BASE_PREFIX,
                  BASE_PREFIX in conf, conf[:200])
            check("ui/config 指向 app.sock", "app.sock" in conf, conf[:200])
        # The unpacked manifest is a copy of fnos/manifest (with checksum
        # rewritten by the builder, so only the identity fields must match).
        fmirror = os.path.join(ROOT, "fnos", "manifest")
        if os.path.exists(fmirror):
            ftext = open(fmirror, encoding="utf-8", errors="replace").read()
            ffields = dict(re.findall(r"^(\w+)\s*=\s*(.*)$", ftext, re.M))
            note("fnos/manifest", {k: ffields.get(k) for k in
                                   ("appname", "version", "display_name")})
            check("fnos/manifest 显示名含 WorkBuddy2API-Hub",
                  "WorkBuddy2API-Hub" in ftext)
            check("fnos/manifest appname 仍是 workbuddy2api",
                  ffields.get("appname") == "workbuddy2api", ffields.get("appname"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    if not HAS_BASH:
        gate("bash 可用（跑 scripts/verify-fpk.sh 的必要条件）", "本机没有 bash")
        return
    verify = subprocess.run(["bash", "scripts/verify-fpk.sh", PKG_PATH], cwd=ROOT,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            timeout=600)
    text = verify.stdout.decode("utf-8", "replace")
    note("verify-fpk 尾行", [ln for ln in text.splitlines() if ln.strip()][-2:])
    match = re.search(r"(\d+) passed, (\d+) failed", text)
    if match:
        check("verify-fpk: 0 failed", int(match.group(2)) == 0, match.group(0))
    else:
        gate("verify-fpk 打印了汇总行", text[-300:])
    check("verify-fpk 退出码 0", verify.returncode == 0, verify.returncode)


# ---------------------------------------------------------------------------
# e6 — read-only probe of the installed app (never writes to the device)
# ---------------------------------------------------------------------------
DEVICE_SOCK = "/vol1/@appcenter/workbuddy2api/app.sock"


def e6_device():
    section("WP-E4 e6 — 真机只读探针（安装了才有）")
    if not os.path.exists(DEVICE_SOCK):
        gate("真机 socket 存在: %s" % DEVICE_SOCK, "本机未安装 / 非飞牛环境")
        return
    if needs_unix("真机 socket 只读探针"):
        return
    note("真机 socket", DEVICE_SOCK)
    status, _, text = unix_request(DEVICE_SOCK, BASE_PREFIX + "/panel/status")
    js = as_json(text) or {}
    note("真机 /panel/status（无 X-Trim-Username）", js)
    status2, _, text2 = unix_request(DEVICE_SOCK, BASE_PREFIX + "/panel/status",
                                     headers={"X-Trim-Username": "ccrab"})
    js2 = as_json(text2) or {}
    note("真机 /panel/status（带 X-Trim-Username: ccrab）", js2)
    check("真机 socket 是网关传输（via_gateway: true）",
          js.get("via_gateway") is True, js)
    #: Judge the app that is actually installed: a box still running the older
    #: build cannot answer for this tree's rule, and its reply is the "before".
    installed_tree = os.path.join(os.path.dirname(DEVICE_SOCK), "server")
    new_code = False
    for dirpath, _dirs, files in os.walk(installed_tree):
        for fn in files:
            if not fn.endswith(".py"):
                continue
            try:
                with open(os.path.join(dirpath, fn), encoding="utf-8",
                          errors="ignore") as fh:
                    if "_gateway_trusted" in fh.read():
                        new_code = True
            except OSError:
                pass
    note("真机安装的 server/ 含新免密实现", new_code)
    if not new_code:
        skip("真机免密口径（无头即 authenticated: true）",
             "设备上跑的是旧版（server/ 无 _gateway_trusted）：实测无头 "
             "authenticated=%s、带 ccrab 头 authenticated=%s。新口径只能在本机"
             "临时进程上验（见 e2），真机需用户在应用中心装新版"
             % (js.get("authenticated"), js2.get("authenticated")))
        return
    check("真机 socket 不带 X-Trim-Username -> authenticated: true",
          js.get("authenticated") is True, js)
    check("真机 socket 带 X-Trim-Username -> 回显用户名且仍已登录",
          js2.get("gateway_user") == "ccrab" and js2.get("authenticated") is True, js2)


def e8_delivery():
    section("WP-E4 e8 — 交付纪律：提交前/提交后都成立 + 设备上跑的就是交付版")
    head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                          stdout=subprocess.PIPE).stdout.decode().strip()
    note("HEAD", head)
    # CI checks out with `fetch-depth: 1`, so the object of the merge commit and
    # the annotated tag object are simply not there: `merge-base --is-ancestor`
    # dies with 128 and `cat-file -t v1.6.17.1` answers "commit". Those two
    # questions are about history, so they are only askable in a full clone -
    # a shallow checkout skips them instead of going red (e11 rehearses this).
    shallow = is_shallow()
    note("checkout 是 shallow（depth 1）", shallow)
    # Cross-state: before the commit HEAD *is* the merge commit, after it the
    # merge commit is an ancestor. Both are the same fact - the merge is in
    # this history - so assert that instead of naming HEAD.
    have_object = subprocess.run(["git", "cat-file", "-e", "9dff35f^{commit}"],
                                 cwd=ROOT, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT).returncode == 0
    if shallow or not have_object:
        skip("合并提交 9dff35f 在 HEAD 的历史里（提交前相等，提交后是祖先）",
             "shallow checkout（depth 1）里 9dff35f 的对象不可达，"
             "git merge-base 会以 128 失败：这不是交付缺陷，只是没有历史可比")
    else:
        ancestor = subprocess.run(
            ["git", "merge-base", "--is-ancestor", "9dff35f", "HEAD"],
            cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        check("合并提交 9dff35f 在 HEAD 的历史里（提交前相等，提交后是祖先）",
              ancestor.returncode == 0, ancestor.returncode)
    tags = subprocess.run(["git", "tag", "--points-at", "HEAD"], cwd=ROOT,
                          stdout=subprocess.PIPE).stdout.decode().strip().split()
    if not tags:
        skip("HEAD 上的 tag（打了 tag 后必须是 annotated v1.6.17.1）",
             "HEAD 目前没有 tag：提交前/未打 tag 都走这条，不打分")
    else:
        for tag in tags:
            check("HEAD 上的 tag 是 v1.6.17.1", tag == "v1.6.17.1", tag)
            kind = subprocess.run(["git", "cat-file", "-t", tag], cwd=ROOT,
                                  stdout=subprocess.PIPE).stdout.decode().strip()
            if shallow:
                skip("tag %s 是 annotated（cat-file -t 应为 tag）" % tag,
                     "shallow checkout 只取 commit，annotated tag 对象不可达"
                     "（cat-file -t 报 %s）：要判 annotated 得用完整 clone，"
                     "CI 走这条" % (kind or "?"))
            else:
                check("tag %s 是 annotated（cat-file -t 应为 tag）" % tag,
                      kind == "tag", kind)
    tracked_dist = subprocess.run(["git", "ls-files", "dist"], cwd=ROOT,
                                  stdout=subprocess.PIPE).stdout.decode().strip()
    check("dist/ 不进版本库（产物未提交）", tracked_dist == "", tracked_dist)
    # Everything the package carries has to be committed: an uncommitted edit
    # to a packaged file is the one way the tree and the fpk silently diverge.
    pkg_paths = list(PKG_MODULES) + ["scripts", "fnos", ".github", "README.md"]
    dirty = subprocess.run(["git", "status", "--porcelain", "--"] + pkg_paths,
                           cwd=ROOT, stdout=subprocess.PIPE).stdout.decode("utf-8",
                                                                          "replace")
    dirty_lines = [ln for ln in dirty.splitlines() if ln.strip()]
    if dirty_lines:
        # Commit still pending (or a writer is mid-edit): reported, not judged
        # red here - e5's byte-for-byte comparison is the thing that would
        # actually catch a wrong package.
        gate("包内文件相对 HEAD 无未提交改动", "未提交改动: %s" % dirty_lines[:6])
    else:
        check("包内文件相对 HEAD 无未提交改动", True)

    doc = os.path.join(ROOT, "docs", "phase-e-delivery.md")
    if not os.path.exists(doc):
        check("docs/phase-e-delivery.md 存在", False, "missing")
    else:
        text = open(doc, encoding="utf-8", errors="replace").read()
        note("交付文档字节数", len(text.encode("utf-8")))
        for heading in ("包指纹", "安装与备份", "已知限制", "测试路线"):
            check("交付文档含「%s」小节" % heading, heading in text)
        leftovers = sorted(set(re.findall(r"PENDING_[A-Z0-9_]+", text)))
        check("交付文档没有遗留待填占位符", leftovers == [], leftovers)
        check("交付文档写明了安装状态", "设备" in text)

    sidecar = PKG_PATH + ".sha256"
    if os.path.exists(PKG_PATH):
        check("旁置 .sha256 校验文件存在", os.path.exists(sidecar), sidecar)
        if os.path.exists(sidecar):
            want = sha256_file(PKG_PATH)
            body = open(sidecar, encoding="utf-8", errors="replace").read()
            check(".sha256 内容与产物一致", want in body, body.strip()[:100])
        doc_text = open(doc, encoding="utf-8", errors="replace").read() if os.path.exists(doc) else ""
        note("交付文档里的指纹行",
             [ln.strip() for ln in doc_text.splitlines() if "sha256" in ln or "字节数" in ln][:4])

    # The device: /vol1/** only exists on the NAS. CI (ubuntu/windows) takes
    # the SKIP branch, and so does any host without the app installed.
    #
    # What is worth asserting when the app *is* installed is not "we did not
    # touch it" (the running service writes its data dir constantly, and the
    # user may install a build at any time) but "what the box runs is the tree
    # we are handing over" - that is the deployment claim, and it is readable.
    center = "/vol1/@appcenter/workbuddy2api"
    data_dir = "/vol1/@appdata/workbuddy2api"
    if not os.path.isdir(center):
        skip("设备上安装的是本树这一版（%s/server 逐字节）" % center,
             "本机看不到 %s（CI 与未安装的主机都走这条）" % center)
    else:
        installed = os.path.join(center, "server")
        pairs = []
        for dirpath, dirs, files in os.walk(installed):
            # The box compiles the modules it runs; the byte-code cache is a
            # product of running the app, not part of what was shipped.
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for name in files:
                if name.endswith((".pyc", ".pyo")):
                    continue
                full = os.path.join(dirpath, name)
                rel = os.path.relpath(full, installed).replace(os.sep, "/")
                pairs.append((rel, full))
        note("设备上 server/ 文件数", len(pairs))
        unknown, differ = [], []
        for rel, full in pairs:
            src = os.path.join(ROOT, rel)
            if not os.path.exists(src):
                unknown.append(rel)
                continue
            try:
                with open(full, "rb") as fh:
                    on_box = fh.read()
                with open(src, "rb") as fh:
                    in_tree = fh.read()
            except OSError as exc:
                differ.append("%s (%s)" % (rel, exc))
                continue
            if on_box != in_tree:
                differ.append("%s (%d vs %d bytes)" % (rel, len(on_box), len(in_tree)))
        check("设备上 server/** 与仓库工作树逐字节一致（设备跑的就是交付版）",
              differ == [] and unknown == [], {"differ": differ[:6],
                                               "not-in-tree": unknown[:6]})
        # The data dir is written by the running service, so judge only that it
        # is intact and readable - never by mtime (that would go red the moment
        # the box is in use, which proves nothing about this phase).
        if not os.path.isdir(data_dir):
            skip("设备数据目录仍完好可读（%s）" % data_dir, "本机看不到该目录")
        else:
            note("设备数据目录", data_dir)
            accounts = os.path.join(data_dir, "accounts")
            check("设备数据目录仍可读（没有被我们写坏）",
                  os.access(data_dir, os.R_OK), data_dir)
            check("设备账号目录仍在（安装没有清掉用户数据）",
                  os.path.isdir(accounts), accounts)
    note("本次交付没有对设备执行任何写操作",
         "由流程保证：本套件对设备只做只读探测（e6 socket 探针 + e8 逐字节读），"
         "构建/安装/重启全部由用户在应用中心完成")
    register("设备断言不用 mtime",
             "用户可能在任何时刻安装/升级，运行中的服务也在持续写数据目录，"
             "所以「设备目录 mtime 未变」这种断言在真机会假红。e8 改为"
             "「设备 server/** 与仓库逐字节一致」+「数据目录仍完好可读」。")


# ---------------------------------------------------------------------------
# e9 - cockpit-compatible export (independent段, not part of the E1..E8 gate)
# ---------------------------------------------------------------------------
GO_COCKPIT_FIELDS = ("id", "email", "uid", "nickname", "access_token", "refresh_token",
                     "token_type", "expires_at", "domain", "dosage_notify_code",
                     "payment_type", "status", "usage_updated_at", "last_checkin_time",
                     "checkin_streak", "created_at", "last_used")
#: The panel's Go source, when a checkout happens to be around: the contract is
#: re-read from it instead of trusted to the constant above. Built from
#: tempfile.gettempdir() (and overridable) so no POSIX-only literal is baked in.
GO_IMPORT_GO = os.environ.get("WB_GO_IMPORT_GO") or os.path.join(
    tempfile.gettempdir(), "panel-latest", "internal", "panel", "import.go")
#: A cockpit file the Go panel itself produced - an anchor nothing in this tree
#: wrote. Overridable; absent on a host that never had the panel.
COCKPIT_SAMPLE = os.environ.get("WB_COCKPIT_SAMPLE") or os.path.join(
    "/vol2/1000/AgentWork/2api", "账号文件",
    "workbuddy-accounts-20261006163005.cockpit.json")


def is_global_domain(domain):
    """The panel's own rule: only workbuddy.ai hosts are global (auth.go)."""
    d = str(domain or "").strip().lower()
    return d == "workbuddy.ai" or d.endswith(".workbuddy.ai")


def go_cockpit_fields():
    """json tags of `cockpitAccount` in the panel's import.go, in order."""
    try:
        with open(GO_IMPORT_GO, encoding="utf-8") as fh:
            source = fh.read()
    except OSError:
        return None
    match = re.search(r"type\s+cockpitAccount\s+struct\s*\{(.*?)\n\}", source, re.S)
    if not match:
        return None
    return [t.group(1) for t in re.finditer(r'json:"([^",]+)', match.group(1))]


def e9_cockpit_export():
    section("WP-E4 e9 - cockpit 兼容导出（独立段，不计入 E1..E8）")
    fields = go_cockpit_fields()
    if fields:
        check("从 import.go 读到 cockpitAccount 的 17 个 json tag",
              fields == list(GO_COCKPIT_FIELDS), fields)
    else:
        note("%s 不可读" % GO_IMPORT_GO, "改用内置 17 键作基准")
    want = set(fields or GO_COCKPIT_FIELDS)

    # The contract has to be anchored on something that was not written by us:
    # a cockpit file the Go panel itself produced (11 rows, 17 keys each).
    sample = COCKPIT_SAMPLE
    try:
        with open(sample, encoding="utf-8") as fh:
            sample_rows = json.load(fh)
        check("参考样例是裸数组、每行键集与本契约一致",
              isinstance(sample_rows, list) and bool(sample_rows)
              and all(set(r) == want for r in sample_rows),
              sorted(set(sample_rows[0]) ^ want) if sample_rows else "empty")
        check("参考样例 domain 全是裸主机（无 scheme）",
              all("://" not in str(r.get("domain") or "") for r in sample_rows),
              sorted({r.get("domain") for r in sample_rows})[:4])
        check("参考样例 expires_at 是毫秒",
              all(isinstance(r.get("expires_at"), int) and r["expires_at"] > 10 ** 12
                  for r in sample_rows))
    except OSError:
        note("参考样例 cockpit 文件不可读", sample)

    panel = Panel()
    if not panel.wait_ready():
        check("面板能起来", False, panel.output()[-300:])
        panel.stop()
        return
    fresh = None
    try:
        seed_account(panel, "e9-intl", realm="intl", nickname="E9 Intl")
        seed_account(panel, "e9-cn", realm="cn", nickname="大豆")
        panel.restart()
        panel.login()
        auth = dict(panel.panel_headers())
        auth["Content-Type"] = "application/json"

        st, _, text = panel.tcp("/accounts?realm=all", headers=panel.panel_headers())
        pooled = {a.get("uid") for a in ((as_json(text) or {}).get("accounts") or [])}
        check("两个种子账号进了池", {"e9-intl", "e9-cn"} <= pooled, sorted(pooled))

        body = json.dumps({"realm": "intl", "format": "cockpit"})
        st, _, text = panel.tcp("/accounts/export", "POST",
                                {"Content-Type": "application/json"}, body)
        check("未登录 POST /accounts/export 被拒", st == 401, (st, text[:80]))

        rows = {}
        for realm, uid in (("intl", "e9-intl"), ("cn", "e9-cn")):
            st, _, text = panel.tcp("/accounts/export", "POST", auth,
                                    json.dumps({"realm": realm, "format": "cockpit"}))
            js = as_json(text) or {}
            data = js.get("data")
            check("realm=%s：200 且 data 是裸数组（非信封）" % realm,
                  st == 200 and isinstance(data, list) and js.get("format") == "cockpit"
                  and "accounts" not in js, (st, sorted(js)[:8]))
            check("realm=%s：count 与数组长度一致且文件名是 .json" % realm,
                  isinstance(data, list) and js.get("count") == len(data)
                  and str(js.get("filename") or "").endswith(".json"),
                  (js.get("count"), len(data or []), js.get("filename")))
            check("realm=%s：只含本 realm 的账号" % realm,
                  bool(data) and [r.get("uid") for r in data] == [uid],
                  [r.get("uid") for r in (data or [])])
            rows[realm] = data or []

        for realm in ("intl", "cn"):
            for row in rows[realm]:
                label = "%s/%s" % (realm, row.get("uid"))
                check("%s：键集恰好是 Go 的 17 个字段" % label,
                      set(row) == want, sorted(set(row) ^ want))
                check("%s：expires_at 是毫秒整数（> 1e12）" % label,
                      isinstance(row.get("expires_at"), int) and row["expires_at"] > 10 ** 12,
                      row.get("expires_at"))
                check("%s：checkin_streak 是 int、token_type 是 Bearer、status 是 active/disabled" % label,
                      isinstance(row.get("checkin_streak"), int)
                      and row.get("token_type") == "Bearer"
                      and row.get("status") in ("active", "disabled"),
                      (row.get("checkin_streak"), row.get("token_type"), row.get("status")))
                check("%s：domain 是裸主机（不带 scheme）且能推出本 realm" % label,
                      "://" not in str(row.get("domain") or "")
                      and is_global_domain(row.get("domain")) == (realm == "intl"),
                      row.get("domain"))
                check("%s：带凭据且不含网关私有字段（paused/realm/驼峰）" % label,
                      bool(row.get("access_token")) and bool(row.get("refresh_token"))
                      and not ({"paused", "realm", "accessToken", "refreshToken"} & set(row)),
                      sorted({"paused", "realm", "accessToken", "refreshToken"} & set(row)))

        # module-level round trip: the panel's importer reads these rows back
        try:
            import wb_accounts as wb_accts
            kw = wb_accts.normalise_import_row(dict(rows["intl"][0]))
            src = rows["intl"][0]
            check("往返（模块）：accessToken / refreshToken / nickname 不丢",
                  kw.get("accessToken") == src["access_token"]
                  and kw.get("refreshToken") == src["refresh_token"]
                  and kw.get("nickname") == src["nickname"],
                  (kw.get("accessToken"), kw.get("nickname")))
            check("往返（模块）：expires_at 毫秒被读成秒",
                  abs(float(kw.get("expiresAt") or 0) - src["expires_at"] / 1000.0) <= 1,
                  (kw.get("expiresAt"), src["expires_at"]))
            check("往返（模块）：realm 由 domain 推出且 source=cockpit",
                  kw.get("realm") == "intl" and kw.get("source") == "cockpit",
                  (kw.get("realm"), kw.get("source")))
            kw_cn = wb_accts.normalise_import_row(dict(rows["cn"][0]))
            check("往返（模块）：cn 行仍归 cn", kw_cn.get("realm") == "cn", kw_cn.get("realm"))
        except Exception as exc:
            check("往返（模块）不抛异常", False, repr(exc))

        # HTTP round trip: a clean panel imports the exported document
        fresh = Panel(base_path="")
        if not fresh.wait_ready():
            check("第二台面板能起来", False, fresh.output()[-300:])
        else:
            fresh.login()
            fauth = dict(fresh.panel_headers())
            fauth["Content-Type"] = "application/json"
            document = rows["intl"] + rows["cn"]
            st, _, text = fresh.tcp("/accounts/import", "POST", fauth,
                                    json.dumps({"data": document}))
            js = as_json(text) or {}
            result = js.get("result") or {}
            check("往返（HTTP）：导入 200 且没有 invalid/skipped 行",
                  st == 200 and not (result.get("invalid") or [])
                  and not (result.get("skipped") or []) and len(result.get("added") or []) == len(document),
                  (st, {k: len(v or []) for k, v in result.items()}))
            st, _, text = fresh.tcp("/accounts?realm=all", headers=fresh.panel_headers())
            by_uid = {a.get("uid"): a for a in ((as_json(text) or {}).get("accounts") or [])}
            check("往返（HTTP）：intl 行仍归 intl（凭 domain 推断）",
                  (by_uid.get("e9-intl") or {}).get("realm") == "intl",
                  (by_uid.get("e9-intl") or {}).get("realm"))
            check("往返（HTTP）：cn 行仍归 cn（凭 domain 推断）",
                  (by_uid.get("e9-cn") or {}).get("realm") == "cn",
                  (by_uid.get("e9-cn") or {}).get("realm"))
            try:
                disk = _read_account_file(fresh.accounts, "e9-intl")
                check("往返（HTTP）：落盘凭据与导出逐字相同",
                      disk.get("accessToken") == rows["intl"][0]["access_token"]
                      and disk.get("refreshToken") == rows["intl"][0]["refresh_token"],
                      (disk.get("accessToken"), disk.get("refreshToken")))
            except Exception as exc:
                check("往返（HTTP）：读回落盘账号文件", False, repr(exc))

        # refusals
        def post(payload_obj, headers=None):
            return panel.tcp("/accounts/export", "POST", headers or auth,
                             json.dumps(payload_obj))

        st, _, text = post({"realm": "intl"})
        check("缺 format -> 400", st == 400 and "format" in text, (st, text[:120]))
        st, _, text = post({"realm": "intl", "format": "nope"})
        check("未知 format -> 400", st == 400, (st, text[:120]))
        st, _, text = post({"realm": "zzz", "format": "cockpit"})
        check("非法 realm -> 400", st == 400, (st, text[:120]))
        st, _, text = post({"realm": "intl", "format": "cockpit", "secrets": False})
        check("cockpit 要求带凭据：secrets=false -> 400", st == 400, (st, text[:120]))
        st, _, text = post({"realm": "intl", "format": "cockpit", "uids": ["nope"]})
        check("未知 uid -> 404", st == 404, (st, text[:120]))
        st, _, text = post({"realm": "intl", "format": "native"})
        js = as_json(text) or {}
        check("native 仍是信封（accounts 数组，不因 cockpit 而变）",
              st == 200 and isinstance(js.get("data"), dict)
              and isinstance((js.get("data") or {}).get("accounts"), list),
              (st, type(js.get("data")).__name__))
    finally:
        panel.stop()
        if fresh is not None:
            fresh.stop()


# ---------------------------------------------------------------------------
# e10 - the platform rehearsal: this suite has to survive a host without
# AF_UNIX, because the CI matrix runs it on windows-latest.
# ---------------------------------------------------------------------------
PLATFORM_SIM = '''\
"""Re-run the suite with the AF_UNIX pieces of this platform removed."""
import runpy
import socketserver
import sys
import socket

for _mod, _names in ((socket, ("AF_UNIX",)),
                     (socketserver, ("UnixStreamServer", "UnixDatagramServer"))):
    for _name in _names:
        if hasattr(_mod, _name):
            delattr(_mod, _name)

_target = sys.argv[1]
sys.argv = [_target]
runpy.run_path(_target, run_name="__main__")
'''


def e10_platform_sim():
    section("WP-E4 e10 — 平台预演：删掉 socket.AF_UNIX 后整套仍必须绿")
    # Two ways this could recurse: through the e1 nested run_all (which runs
    # this file again) or through this very section.
    if os.environ.get("WB_E1_NESTED") == "1" or os.environ.get("WB_E10_NESTED") == "1":
        skip("平台预演（删掉 socket.AF_UNIX）",
             "嵌套运行（run_all 或本段自身）：不再自我递归")
        return
    tmp = tempfile.mkdtemp(prefix="wb-phaseE-sim-")
    try:
        script = os.path.join(tmp, "no_af_unix.py")
        with open(script, "w", encoding="utf-8") as fh:
            fh.write(PLATFORM_SIM)
        env = dict(os.environ)
        env["WB_E1_NESTED"] = "1"          # e1 would launch run_all all over again
        env["WB_E10_NESTED"] = "1"
        env["PYTHONPATH"] = ROOT + os.pathsep + env.get("PYTHONPATH", "")
        done = subprocess.run([sys.executable, script, os.path.abspath(__file__)],
                              cwd=ROOT, env=env, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, timeout=280)
        text = done.stdout.decode("utf-8", "replace")
        tail = [ln for ln in text.splitlines() if ln.strip()][-6:]
        match = re.search(r"PASS=(\d+) FAIL=(\d+) SKIP=(\d+)", text)
        note("平台预演计数", match.group(0) if match else tail)
        note("平台预演里的 AF_UNIX 段", [ln.strip() for ln in text.splitlines()
                                        if "[SKIP]" in ln and "AF_UNIX" in ln][:3])
        check("平台预演：子进程退出码 0（无 AF_UNIX 时不崩）",
              done.returncode == 0, (done.returncode, tail))
        check("平台预演：打印了汇总行", match is not None, tail)
        if match:
            passed, failed, skipped = (int(g) for g in match.groups())
            check("平台预演：FAIL == 0（没有 AF_UNIX 也不允许红）", failed == 0, tail)
            check("平台预演：确实跳过了 AF_UNIX 段（SKIP > 0）", skipped > 0,
                  skipped)
            check("平台预演：其余段仍在真跑（PASS 数量够）", passed >= 60, passed)
        check("平台预演：没有 Traceback（没有未捕获的 AttributeError）",
              "Traceback (most recent call last)" not in text,
              [ln for ln in text.splitlines() if "Error" in ln][:3])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


CI_SIM = '''\
"""Re-run the suite as a non-root runner (CI has no `seteuid` rights)."""
import os
import runpy
import sys

# Windows has no geteuid at all, so the assignment also covers that platform.
os.geteuid = lambda: 1000

_target = sys.argv[1]
sys.argv = [_target] + sys.argv[2:]
runpy.run_path(_target, run_name="__main__")
'''


def e11_ci_rehearsal():
    section("WP-E4 e11 — CI 预演：shallow clone（depth 1）+ 非 root runner")
    if os.environ.get("WB_E1_NESTED") == "1" or os.environ.get("WB_E11_NESTED") == "1":
        skip("CI 预演（shallow clone / 非 root）",
             "嵌套运行（run_all 或本段自身）：不再自我递归")
        return
    if shutil.which("git") is None:
        gate("git 可用（CI 预演的必要条件）", "本机没有 git")
        return
    tmp = tempfile.mkdtemp(prefix="wb-phaseE-ci-")
    try:
        os.chmod(tmp, 0o755)   # the uid probe in the child has to traverse this
        clone = os.path.join(tmp, "shallow")
        # `file://` matters: a plain local-path clone ignores --depth and copies
        # the whole history (then the two history assertions would run instead of
        # skipping, and this rehearsal would prove nothing about CI).
        uri = pathlib.Path(ROOT).resolve().as_uri()
        rc, out = git_text(["clone", "--quiet", "--depth", "1", uri, clone],
                           cwd=tmp, timeout=300)
        check("shallow clone 成功（git clone --depth 1 file://<本地仓库>）", rc == 0,
              out[-300:])
        if rc == 0:
            check("clone 确实是 shallow（is-shallow-repository=true）",
                  is_shallow(clone),
                  git_text(["rev-parse", "--is-shallow-repository"], cwd=clone)[1])
            # The exact shape CI hit: the merge commit's object is absent, so
            # merge-base dies with 128. Prove the environment really is that.
            rc_anc, out_anc = git_text(
                ["merge-base", "--is-ancestor", "9dff35f", "HEAD"], cwd=clone)
            check("shallow clone 里 merge-base --is-ancestor 不可问（rc != 0，CI 报 128）",
                  rc_anc != 0, (rc_anc, out_anc[:120]))
            rel = os.path.relpath(os.path.abspath(__file__), ROOT)
            child_path = os.path.join(clone, rel)
            os.makedirs(os.path.dirname(child_path), exist_ok=True)
            if os.path.exists(child_path):
                note("clone 里的套件版本", "HEAD 那一版")
            else:
                note("clone 里的套件版本", "HEAD 里还没有这个文件（尚未提交）")
            # The clone only ever carries the committed tree, so it cannot hold
            # this fix while it is still uncommitted. Copying the working copy in
            # reproduces the CI shape we actually care about: the fixed suite
            # running inside a depth-1 checkout.
            shutil.copyfile(os.path.abspath(__file__), child_path)
            note("预演用的是哪一版套件", "工作树当前版（固定运行，未提交也能预演）")
            env = dict(os.environ)
            env["WB_E1_NESTED"] = "1"     # e1 would launch run_all all over again
            env["WB_E11_NESTED"] = "1"
            env["PYTHONPATH"] = clone + os.pathsep + env.get("PYTHONPATH", "")
            child = subprocess.run(
                [sys.executable, child_path, "e8_delivery", "e2_peer_matrix"],
                cwd=clone, env=env, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, timeout=600)
            text = child.stdout.decode("utf-8", "replace")
            fails = [ln.strip() for ln in text.splitlines()
                     if ln.strip().startswith("[FAIL]")]
            skips = [ln.strip() for ln in text.splitlines()
                     if ln.strip().startswith("[SKIP]")]
            match = re.search(r"PASS=(\d+) FAIL=(\d+) SKIP=(\d+)", text)
            note("shallow clone 里的子跑计数",
                 match.group(0) if match else text.splitlines()[-3:])
            note("shallow clone 里被跳过的项", [s[:110] for s in skips][:6])
            check("shallow clone 里 e8+e2b 整段绿（FAIL=0）",
                  match is not None and int(match.group(2)) == 0
                  and child.returncode == 0, (child.returncode, fails[:4]))
            check("shallow clone 里祖先关系记为 SKIP（不是 FAIL）",
                  any("9dff35f" in s for s in skips)
                  and not any("9dff35f" in f for f in fails), skips[:4])
            check("shallow clone 里 annotated 判定不报 FAIL",
                  not any("annotated" in f for f in fails),
                  [f for f in fails if "annotated" in f][:2])

        # Non-root runner: the uid matrix must skip, not fail with 127.
        script = os.path.join(tmp, "non_root.py")
        with open(script, "w", encoding="utf-8") as fh:
            fh.write(CI_SIM)
        env2 = dict(os.environ)
        env2["WB_E1_NESTED"] = "1"
        env2["WB_E11_NESTED"] = "1"
        env2["PYTHONPATH"] = ROOT + os.pathsep + env2.get("PYTHONPATH", "")
        child2 = subprocess.run(
            [sys.executable, script, os.path.abspath(__file__), "e2_peer_matrix"],
            cwd=ROOT, env=env2, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, timeout=300)
        text2 = child2.stdout.decode("utf-8", "replace")
        tail2 = [ln for ln in text2.splitlines() if ln.strip()][-5:]
        match2 = re.search(r"PASS=(\d+) FAIL=(\d+) SKIP=(\d+)", text2)
        note("非 root 模拟计数", match2.group(0) if match2 else tail2)
        skips2 = [ln.strip() for ln in text2.splitlines()
                  if ln.strip().startswith("[SKIP]")]
        check("非 root 模拟：退出码 0（uid 矩阵不再以 127 崩）",
              child2.returncode == 0, (child2.returncode, tail2))
        check("非 root 模拟：FAIL == 0", match2 is not None
              and int(match2.group(2)) == 0, tail2)
        check("非 root 模拟：uid 矩阵记为 SKIP（不是 FAIL）",
              any("切 uid 需要 root" in s for s in skips2), skips2[:4])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# --------------------------------------------------------------------------
# e12 — 已发布错包（Release 资产）反向取证（task-19）
#
# 背景：tag v1.6.17.1 的 CI 构建出的附件是 `WorkBuddy2API-Hub_1.6.10.3_all.fpk`
# （版本号由 `scripts/build-fpk.sh` 从「本仓库可见的上游三段 tag」推出，CI 的
# shallow clone 里可见范围与开发机不同 → 同一提交两环境两版本）。本段把「错包
# 只是版本号错、payload 与要发布的一致」这件事固化成常驻断言：只要把 Release
# 资产下载到 WB_WRONG_PKG 指向的路径（默认 /tmp/wb-wrongpkg/<资产名>，旁置
# `.sha256` 存在时一并校验），证据就可以一键复算；没有该副本时记 SKIP。
# --------------------------------------------------------------------------

WRONG_PKG = (os.environ.get("WB_WRONG_PKG")
             or "/tmp/wb-wrongpkg/WorkBuddy2API-Hub_1.6.10.3_all.fpk")


def _safe_extract(tar_path, dest):
    """解包（.fpk / app.tgz 都是 tar，前者 gzip），拒绝目录穿越。"""
    import tarfile
    os.makedirs(dest, exist_ok=True)
    root = os.path.realpath(dest)
    with tarfile.open(tar_path) as tf:
        for member in tf.getmembers():
            target = os.path.realpath(os.path.join(dest, member.name))
            if target != root and not target.startswith(root + os.sep):
                raise ValueError("tar member escapes destination: %s" % member.name)
        tf.extractall(dest)
    return dest


def _tree_digest(root):
    out = {}
    for base, _dirs, files in os.walk(root):
        for name in files:
            path = os.path.join(base, name)
            out[os.path.relpath(path, root).replace(os.sep, "/")] = md5_file(path)
    return out


def _manifest_fields(root):
    path = os.path.join(root, "manifest")
    if not os.path.exists(path):
        return {}
    text = open(path, encoding="utf-8", errors="replace").read()
    return dict(re.findall(r"^(\w+)\s*=\s*(.*)$", text, re.M))


def _release_parts(fp, dest):
    """fpk → (manifest 字段, {payload 相对路径: md5}, {外层成员: 尺寸})。"""
    import tarfile
    _safe_extract(fp, dest)
    outer = {}
    with tarfile.open(fp) as tf:
        for member in tf.getmembers():
            outer[member.name.rstrip("/")] = member.size
    payload = _safe_extract(os.path.join(dest, "app.tgz"),
                            os.path.join(dest, "payload"))
    return _manifest_fields(dest), _tree_digest(payload), outer


def _repo_path_for_payload(rel):
    """payload 布局 ↔ 仓库布局（e5 用的同一张映射表）。"""
    if rel.startswith("server/"):
        return os.path.join(ROOT, rel[len("server/"):])
    if rel == "ui/config":
        return os.path.join(ROOT, "fnos/ui/config")
    if rel == "ui/images/64.png":
        return os.path.join(ROOT, "fnos/ICON.PNG")
    if rel == "ui/images/256.png":
        return os.path.join(ROOT, "fnos/ICON_256.PNG")
    if rel.startswith("config/"):
        return os.path.join(ROOT, "fnos", rel)
    return None


def _version_tuple(text):
    try:
        return tuple(int(part) for part in str(text).split("."))
    except (TypeError, ValueError):
        return None


def e12_released_pkg():
    section("WP-E12 已发布错包反向取证（Release 资产 vs 本机最终包 vs 仓库）")
    wrong = WRONG_PKG
    if not os.path.exists(wrong):
        gate("已发布错包副本存在: %s" % wrong,
             "本机/CI 上没有下载过 Release 资产（用 WB_WRONG_PKG 指向下载物）")
        return
    if not os.path.exists(PKG_PATH):
        gate("本机最终包存在: %s" % PKG_PATH, "尚未构建")
        return
    note("错包", os.path.basename(wrong))
    note("错包字节数", os.path.getsize(wrong))
    note("错包 sha256", sha256_file(wrong))
    note("本机包 sha256", sha256_file(PKG_PATH))
    side = wrong + ".sha256"
    if os.path.exists(side):
        line = open(side, encoding="utf-8", errors="replace").read().split()
        check("下载物 sha256 与 GitHub 附件的 .sha256 一致",
              bool(line) and line[0].lower() == sha256_file(wrong),
              " ".join(line[:2])[:120])
    else:
        note(".sha256 旁置文件", "未下载（GitHub 资产的 .sha256 要经 API "
                                "assets/<id> 取；浏览器 URL 会以 curl(18) 断流）")

    tmp = tempfile.mkdtemp(prefix="wb-phaseE-rel-")
    try:
        wf, wp, wo = _release_parts(wrong, os.path.join(tmp, "wrong"))
        lf, lp, lo = _release_parts(PKG_PATH, os.path.join(tmp, "local"))
        note("错包 manifest", {k: wf.get(k) for k in
                               ("version", "checksum", "appname", "platform")})
        note("本机 manifest", {k: lf.get(k) for k in
                               ("version", "checksum", "appname", "platform")})
        diff = sorted(k for k in set(wf) | set(lf) if wf.get(k) != lf.get(k))
        check("两份 manifest 只有 version 与 checksum 两处不同",
              diff == ["checksum", "version"], diff)
        wv, lv = _version_tuple(wf.get("version")), _version_tuple(lf.get("version"))
        check("错包 version 是四段且与本机不同",
              wv is not None and lv is not None and wv != lv,
              (wf.get("version"), lf.get("version")))
        check("错包 version 低于本机（装上会被应用中心判为降级）",
              wv is not None and lv is not None and wv < lv,
              (wf.get("version"), lf.get("version")))
        check("外层成员名集合一致", sorted(wo) == sorted(lo), (len(wo), len(lo)))
        check("外层只有 app.tgz 的尺寸不同（payload 同内容、只是 mtime 不同）",
              sorted(k for k in set(wo) | set(lo) if wo.get(k) != lo.get(k)) == ["app.tgz"],
              {k: (wo.get(k), lo.get(k)) for k in sorted(set(wo) | set(lo))
               if wo.get(k) != lo.get(k)})
        check("payload 文件数一致且非空", len(wp) == len(lp) and len(wp) > 20,
              (len(wp), len(lp)))
        check("payload 逐文件 md5 完全一致（错包的代码内容 == 要发布的代码）",
              wp == lp,
              sorted(k for k in set(wp) | set(lp) if wp.get(k) != lp.get(k))[:6])
        for label, fm, root in (("错包", wf, os.path.join(tmp, "wrong")),
                                ("本机包", lf, os.path.join(tmp, "local"))):
            check("%s manifest checksum == md5(自身 app.tgz)（包内部自洽，"
                  "完整性门抓不到版本错）" % label,
                  fm.get("checksum") == md5_file(os.path.join(root, "app.tgz")),
                  fm.get("checksum"))
        for label, pm in (("错包", wp), ("本机包", lp)):
            bad = []
            for rel, digest in sorted(pm.items()):
                src = _repo_path_for_payload(rel)
                if not src or not os.path.exists(src) or md5_file(src) != digest:
                    bad.append(rel)
            check("%s payload 的每个文件与仓库工作树逐字节一致" % label, not bad, bad[:6])
        register("R8 已发布错包（version 1.6.10.3）",
                 "Release v1.6.17.1 的附件是 %s：payload 与本机最终包逐文件一致、"
                 "也与仓库逐字节一致，只有 manifest.version 与 checksum 不同（后者派生自 "
                 "app.tgz 的成员 mtime），且两份包各自 checksum == md5(自身 app.tgz) → "
                 "包内部自洽，完整性断言抓不到它；`scripts/verify-fpk.sh` 对错包实测 "
                 "70 passed / 1 failed，唯一红是 `the package is what this tree builds`"
                 % os.path.basename(wrong))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# e13 — the release pipeline: one commit, one version, everywhere
# ---------------------------------------------------------------------------
#: HEAD before the pipeline fix. Its `scripts/build-fpk.sh` derived the version
#: from the three-part tags the checkout happens to see, which is how the tag
#: v1.6.17.1 built a package called 1.6.10.3 (Release 407525712).
PRE_FIX_COMMIT = "55dfad2"
#: The tag set CI had when that happened: the fork's tags, upstream mirrored up
#: to v1.6.10 only, and the release tag sitting on HEAD.
OLD_CI_TAGS = ["v1.6.10", "v1.6.10.1", "v1.6.10.2"]
UPSTREAM_TAGS = ["v1.6.%d" % n for n in range(11, 18)]


def _pipeline_fixture(tmp, name, ancestors, head_tags=()):
    """A throwaway repo holding `fnos/manifest` + `scripts/build-fpk.sh`.

    The fixture is one commit per ancestor tag (oldest first) plus a final
    commit that carries the release tag(s), which is all `--print-version`
    needs and keeps the check independent of this checkout's own history.
    """
    work = os.path.join(tmp, name)
    os.makedirs(os.path.join(work, "scripts"))
    os.makedirs(os.path.join(work, "fnos"))
    shutil.copyfile(os.path.join(ROOT, "scripts", "build-fpk.sh"),
                    os.path.join(work, "scripts", "build-fpk.sh"))
    shutil.copyfile(os.path.join(ROOT, "fnos", "manifest"),
                    os.path.join(work, "fnos", "manifest"))

    def g(*args):
        return git_text(list(args), cwd=work)

    g("init", "--quiet")
    g("config", "user.email", "phase-e-verifier@example.invalid")
    g("config", "user.name", "phase E verifier")
    for tag in ancestors:
        g("commit", "--quiet", "--allow-empty", "-m", "upstream %s" % tag)
        g("tag", "-a", tag, "-m", tag)
    g("commit", "--quiet", "--allow-empty", "-m", "our release commit")
    for tag in head_tags:
        g("tag", "-a", tag, "-m", tag)
    return work


def _fixture_version(work, *extra):
    """Run `scripts/build-fpk.sh --print-version` in a fixture; (rc, text)."""
    done = subprocess.run([shutil.which("bash"), "scripts/build-fpk.sh",
                           "--print-version"] + list(extra),
                          cwd=work, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, timeout=180)
    return done.returncode, done.stdout.decode("utf-8", "replace").strip()


def _suite_run(script, cwd, env=None, timeout=900):
    """Run a unittest-style suite; (rc, combined output)."""
    done = subprocess.run([sys.executable, script], cwd=cwd, env=env,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          timeout=timeout)
    return done.returncode, done.stdout.decode("utf-8", "replace")


def e13_release_pipeline():
    section("WP-E8 e13 — 发布流水线修复（tag 可见性 / 版本推导）独立复核")
    build_yml = os.path.join(ROOT, ".github", "workflows", "build-fpk.yml")
    sync_yml = os.path.join(ROOT, ".github", "workflows", "sync-upstream.yml")
    build_text = ""
    sync_text = ""
    for path, holder in ((build_yml, "build"), (sync_yml, "sync")):
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as handle:
                text = handle.read()
            if holder == "build":
                build_text = text
            else:
                sync_text = text
    check("build-fpk.yml 与 sync-upstream.yml 都在", bool(build_text) and bool(sync_text))
    check("构建工作流把 tag 交给脚本，而不是让它猜（TAG_REF / ${TAG_REF#v} / export VERSION）",
          "TAG_REF: ${{" in build_text and "${TAG_REF#v}" in build_text
          and re.search(r"(?m)^\s*export VERSION=", build_text) is not None)
    check("构建工作流读回派生版本再比对（--print-version）",
          "--print-version" in build_text)
    check("版本不一致时报 ::error:: 并 exit 1（拒绝发布 tag 没点名的包）",
          "::error::" in build_text
          and re.search(r"(?m)^\s*exit 1\s*$", build_text) is not None)
    check("branch/dispatch 构建不会发 Release（附加步骤被 ref/tag 门住）",
          "if: inputs.ref != '' || startsWith(github.ref, 'refs/tags/v')" in build_text)
    check("同步工作流镜像**每一个**上游三段 tag（不是只有最新的那个）",
          re.search(r"for upstream_tag in ", sync_text) is not None
          and 'git push origin "refs/tags/${upstream_tag}"' in sync_text)
    check("同步工作流没有整体推 tag（无 `git push --tags`，本地临时 tag 泄不出去）",
          re.search(r"git push[^\n]*--tags", sync_text) is None)
    check("同步工作流只推它自己那一个 release tag 的 ref",
          'git push origin "refs/tags/${ours}"' in sync_text)
    check("同步工作流用 --print-version 定 tag，且已存在的 tag 不再切",
          "--print-version" in sync_text
          and 'ls-remote --exit-code --tags origin "refs/tags/${ours}"' in sync_text)
    check("同步工作流推 tag 前先确认 origin 上没有（幂等，不重复推）",
          'ls-remote --exit-code --tags origin "refs/tags/${upstream_tag}"' in sync_text)
    if not HAS_BASH:
        skip("发布流水线行为验证（fixture 里跑 build-fpk.sh）", "本平台没有 bash")
        return
    tmp = tempfile.mkdtemp(prefix="wb-e13-")
    try:
        # -- the tag set CI actually had, before and after the fix -----------
        ci = _pipeline_fixture(tmp, "old-ci", OLD_CI_TAGS, ["v1.6.17.1"])
        rc, out = _fixture_version(ci)
        check("CI 当时的 tag 集合下，修复后 --print-version 就是 HEAD 上的 tag",
              rc == 0 and out == "1.6.17.1", "rc=%d out=%r" % (rc, out))
        rc_old, _ = git_text(["cat-file", "-e", PRE_FIX_COMMIT + "^{commit}"])
        if rc_old == 0:
            rc, old_script = git_text(["show", "%s:scripts/build-fpk.sh" % PRE_FIX_COMMIT])
            if rc == 0 and old_script:
                with open(os.path.join(ci, "scripts", "build-fpk.sh"), "w",
                          encoding="utf-8", newline="\n") as handle:
                    handle.write(old_script.rstrip("\n") + "\n")
                rc, out = _fixture_version(ci)
                check("修复前的脚本在同一 fixture 里报 1.6.10.3（= 错包版本，红已独立复现）",
                      rc == 0 and out == "1.6.10.3", "rc=%d out=%r" % (rc, out))
                shutil.copyfile(os.path.join(ROOT, "scripts", "build-fpk.sh"),
                                os.path.join(ci, "scripts", "build-fpk.sh"))
        else:
            gate("修复前脚本的红复现（要 %s 可达）" % PRE_FIX_COMMIT,
                 "shallow clone 里修复前提交不可达")
        rc, out = _fixture_version(ci, "--alpha")
        check("alpha 构建在同样 tag 下仍是一个带 -alpha<k> 的推导值（有意：alpha 按构造就是猜）",
              rc == 0 and re.match(r"^1\.6\.10\.\d+-alpha\d+$", out) is not None,
              "rc=%d out=%r" % (rc, out))

        # -- dispatch: an untagged HEAD, the shape "Run workflow" builds -----
        dispatch = _pipeline_fixture(
            tmp, "dispatch", OLD_CI_TAGS + UPSTREAM_TAGS + ["v1.6.17.1"])
        rc, out = _fixture_version(dispatch)
        check("dispatch（HEAD 无 tag、上游 tag 都可见）派生 1.6.17.2，而不是 1.6.10.x",
              rc == 0 and out == "1.6.17.2", "rc=%d out=%r" % (rc, out))
        starved = _pipeline_fixture(
            tmp, "starved", OLD_CI_TAGS + ["v1.6.17.1"])
        for tag in UPSTREAM_TAGS:
            git_text(["tag", "-d", tag], cwd=starved)
        rc, out = _fixture_version(starved)
        check("镜像 tag 缺失的克隆里 dispatch 仍会派生低版本（1.6.10.3）——残留风险已量化",
              rc == 0 and out == "1.6.10.3", "rc=%d out=%r" % (rc, out))
        with open(os.path.join(starved, "fnos", "manifest"), "r", encoding="utf-8") as handle:
            manifest_text = handle.read()
        manifest_version = ""
        for line in manifest_text.splitlines():
            if line.startswith("version"):
                manifest_version = line.split("=", 1)[1].strip()
        check("fnos/manifest 里的 version 是构建时被 write_manifest 覆写的占位值（1.6.10）",
              manifest_version == "1.6.10", "manifest version=%r" % manifest_version)
        register("R11 dispatch 的版本下限只由「看得见的 tag」保证",
                 "在只看得见 v1.6.10/.1/.2 + v1.6.17.1 的克隆里 dispatch 会派生 1.6.10.3；"
                 "`fnos/manifest` 的 version 是 1.6.10（构建时被 write_manifest 覆写），"
                 "所以「派生值低于 manifest.version 就拒绝」这条规则抓不到它"
                 "（1.6.10.3 > 1.6.10）；真正能抓的下限是「本克隆可见的最新四段 release tag」"
                 "（v1.6.17.1）。判定：可接受——dispatch 构建不发 Release（附加步骤被 tag/ref 门住，"
                 "只出 artifact），且 origin 现在已镜像全部 54 个 tag，tag 饥饿的克隆只可能是还没跑过 "
                 "sync 的 fork；若要加强，用四段 tag 作下限而不是 manifest。")

        # -- tag objects on HEAD --------------------------------------------
        multi = _pipeline_fixture(tmp, "multi", ["v1.6.17", "v1.6.17.1"],
                                  ["v1.6.17.2", "v9.9.9.9"])
        rc, kind = git_text(["cat-file", "-t", "v9.9.9.9"], cwd=multi)
        rc2, at_head = git_text(["tag", "--points-at", "HEAD"], cwd=multi)
        check("annotated tag 也出现在 `tag --points-at HEAD` 里（cat-file -t = tag）",
              rc == 0 and kind == "tag"
              and set(at_head.split()) == {"v1.6.17.2", "v9.9.9.9"},
              "type=%r points-at=%r" % (kind, at_head))
        rc, out = _fixture_version(multi)
        check("HEAD 上有多个四段 tag 时取最高那个（sort -V 取尾，确定性的）",
              rc == 0 and out == "9.9.9.9", "rc=%d out=%r" % (rc, out))
        check("推 v1.6.17.2 而 HEAD 还带着 v9.9.9.9 时，工作流的比对会拒绝（不是静默出错版本）",
              out != "1.6.17.2")
        # old release tags of an older base still count towards the ordinal
        tri = _pipeline_fixture(tmp, "tri", ["v1.6.10", "v1.6.10.1", "v1.6.10.2"])
        rc, out = _fixture_version(tri)
        check("旧提交上的 v1.6.10.1/.2 仍顶高 ordinal（无 tag 的 HEAD 报 1.6.10.3）",
              rc == 0 and out == "1.6.10.3", "rc=%d out=%r" % (rc, out))
        tagged_ci = _pipeline_fixture(tmp, "tagged-ci", OLD_CI_TAGS + ["v1.6.17"],
                                    ["v1.6.17.1"])
        rc, out = _fixture_version(tagged_ci)
        check("HEAD 上有 release tag 时，旧 base 的 ordinal 不再参与（报 tag 本身）",
              rc == 0 and out == "1.6.17.1", "rc=%d out=%r" % (rc, out))
        # `upstream_tag()` greps for exactly three parts, so a four-part release
        # tag can never be the base: with v1.6.17 visible an untagged HEAD lands
        # on 1.6.17.1, not on 1.6.10.3.
        four_part = _pipeline_fixture(tmp, "four-part", OLD_CI_TAGS + ["v1.6.17"])
        rc, out = _fixture_version(four_part)
        check("四段 release tag 不当 base（upstream_tag 只认三段）：旧 tag 也在时无 tag 的 HEAD 报 1.6.17.1 而非 1.6.10.3",
              rc == 0 and out == "1.6.17.1", "rc=%d out=%r" % (rc, out))

        # -- the packager's own suite, run by me ----------------------------
        suite = os.path.join(ROOT, "tests", "_test_release_pipeline.py")
        if not os.path.isfile(suite):
            gate("packager 的 tests/_test_release_pipeline.py 存在", "文件不在")
            return
        rc, out = _suite_run(os.path.join("tests", "_test_release_pipeline.py"), ROOT)
        check("packager 的套件在本树独立跑绿（Ran 8 tests / OK）",
              rc == 0 and "Ran 8 tests" in out and "OK" in out,
              "rc=%d tail=%r" % (rc, out.strip().splitlines()[-1] if out.strip() else ""))
        env = dict(os.environ)
        env["PATH"] = ""
        env.pop("PYTHONPATH", None)
        rc, out = _suite_run(os.path.join("tests", "_test_release_pipeline.py"), ROOT, env=env)
        check("bash/git 都不在 PATH 上时该套件 5 条 SKIP 而不是崩（Windows 形状）",
              rc == 0 and "skipped=5" in out, "rc=%d tail=%r" % (rc, out.strip().splitlines()[-1] if out.strip() else ""))
        clone = os.path.join(tmp, "depth1")
        uri = pathlib.Path(ROOT).resolve().as_uri()
        rc, out = git_text(["clone", "--quiet", "--depth", "1", uri, clone])
        if rc != 0:
            gate("depth-1 clone 里跑 packager 套件", "clone 失败：%s" % out.splitlines()[:1])
        else:
            # the clone carries HEAD, and the fix is still uncommitted: hand it
            # the working tree's files so this checks the tree as it will be
            for rel in ("scripts/build-fpk.sh",
                        os.path.join(".github", "workflows", "build-fpk.yml"),
                        os.path.join(".github", "workflows", "sync-upstream.yml"),
                        os.path.join("tests", "_test_release_pipeline.py")):
                src = os.path.join(ROOT, rel)
                dst = os.path.join(clone, rel)
                if os.path.isfile(src) and os.path.isdir(os.path.dirname(dst)):
                    shutil.copyfile(src, dst)
            check("clone 确实是 depth 1（CI 的 tests job 就是这种 checkout）",
                  is_shallow(clone))
            rc, out = _suite_run(os.path.join("tests", "_test_release_pipeline.py"), clone)
            check("depth-1 clone 里 packager 套件也绿（CI 形状）",
                  rc == 0 and "Ran 8 tests" in out and "OK" in out,
                  "rc=%d tail=%r" % (rc, out.strip().splitlines()[-1] if out.strip() else ""))
        with open(suite, "r", encoding="utf-8") as handle:
            suite_text = handle.read()
        # R10, fixed by the Lead: the clone source has to be a real URL built by
        # pathlib. `"file://" + path` is not a URL on Windows (git answers
        # `fatal: no path specified` for `file://C:\...`), and the fix's own
        # comment still quotes that shape, so comment lines are stripped first.
        code_lines = [line for line in suite_text.splitlines()
                      if not line.lstrip().startswith("#")]
        suite_code = "\n".join(code_lines)
        check("packager 套件不再在代码里裸拼 file:// URL（R10 已修）",
              re.search(r'file://["\']\s*\+', suite_code) is None)
        check("浅克隆的 clone 源用 pathlib 造 URL（import pathlib + as_uri）",
              "import pathlib" in suite_code and "as_uri()" in suite_code)
        check("packager 套件里每个 subprocess.run 都用 cwd= 传路径（不把路径拼进命令行/URL）",
              suite_code.count("subprocess.run(") > 0
              and suite_code.count("subprocess.run(") == suite_code.count("cwd="),
              "subprocess.run=%d cwd==%d"
              % (suite_code.count("subprocess.run("), suite_code.count("cwd=")))
        win_shape = ("file://"
                     + "C:\\Users\\runneradmin\\AppData\\Local\\Temp\\wb-release-pipeline-x\\work")
        rc, url_out = git_text(["ls-remote", win_shape])
        # Only the refusal is asserted: the wording is the platform's, and
        # Windows words it "does not appear to be a git repository" where Linux
        # says "no path specified". The control below is what proves the call
        # itself is sound, so this stays a counter-assertion either way.
        check("反证：裸拼出来的形状在 git 眼里不是可用的 URL（rc≠0）",
              rc != 0,
              "rc=%d out=%r" % (rc, (url_out.splitlines() or [""])[0]))
        rc_control, _ = git_text(["ls-remote", pathlib.Path(ROOT).resolve().as_uri()])
        check("对照：同一次调用配上 pathlib 造出的 URL 能读到仓库（rc=0）",
              rc_control == 0, "rc=%d" % rc_control)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


SECTIONS_FNS = (e1_suites, e2_gateway, e2_peer_matrix, e3_mount, e4_credit,
                e5_package, e6_device, e7_hardening, e8_delivery,
                e9_cockpit_export, e10_platform_sim, e11_ci_rehearsal,
                e12_released_pkg, e13_release_pipeline)


def main(argv):
    wanted = [a for a in argv if not a.startswith("-")]
    for fn in SECTIONS_FNS:
        if wanted and not any(w in fn.__name__ for w in wanted):
            continue
        try:
            fn()
        except Exception as exc:  # noqa: BLE001 - a crashed section is a failure
            import traceback
            traceback.print_exc()
            check("段 %s 自身没有崩溃" % fn.__name__, False, repr(exc))
    if _CUR[0] is not None:
        SECTIONS.append((_CUR[0], _CUR[1], _CUR[2], _CUR[3]))
    print("\n-- 分段统计 --")
    for name, ok, bad, skipped in SECTIONS:
        print("  %-52s PASS=%-4d FAIL=%-3d SKIP=%d" % (name, ok, bad, skipped))
    if REGISTRY:
        print("\n-- 登记项（有意口径差异 / 加固建议，不计 PASS/FAIL）--")
        for label, detail in REGISTRY:
            print("  * %s\n      %s" % (label, detail))
    print("\nPASS=%d FAIL=%d SKIP=%d" % (PASS, FAIL, SKIP))
    if FAILED:
        print("失败项：")
        for label in FAILED:
            print("  - " + label)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
