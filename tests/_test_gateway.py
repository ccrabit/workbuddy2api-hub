"""The fnOS gateway socket: single sign-on, and the panel behind it.

fnOS does not open a third-party app by pointing a browser at its port. The
App Center redirects to `/app/<appname>/`, nginx forwards that to a unix socket
inside the payload, and the gateway forwards the request for a NAS user it has
already authenticated. Two properties have to hold for that to be both useful
and safe:

  * a request that arrived on the socket from the gateway itself is a signed-in
    session, so the panel opens without a password - the whole point of the
    entry. `X-Trim-Username` only names the user for display: fnOS stops
    sending it once its own session ages out, and prompting for the panel
    password at that moment is the duplicate login this entry exists to avoid;
  * the same header on the TCP port buys nothing, because it is trivially
    forged by anyone who can reach the port.

The payload also has to survive being mounted under the gateway prefix, so the
dashboard is served with the prefix baked in and the server strips it if it
arrives anyway. These tests drive a real process over both transports.
"""
import json
import os
import socket
import stat
import subprocess
import sys
import tempfile
import time
import unittest
import socketserver
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# The socket this whole file drives does not exist on Windows: socketserver
# only defines UnixStreamServer where the platform has AF_UNIX. Skip instead of
# failing - the gateway entry is a fnOS feature, and CI runs Windows to prove
# the *port* path still works there (see _test_platform_import.py).
if not (hasattr(socket, "AF_UNIX") and hasattr(socketserver, "UnixStreamServer")):
    print("SKIP: this platform has no AF_UNIX sockets; the gateway entry is fnOS only")
    sys.exit(0)

PREFIX = "/app/workbuddy2api"
GATEWAY_USER = "deepseek.harness"
PANEL_PASSWORD = "test-panel-password"


def free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def parse_response(raw):
    head, _, body = raw.partition(b"\r\n\r\n")
    lines = head.decode("utf-8", "replace").split("\r\n")
    status = int(lines[0].split(" ")[1]) if len(lines[0].split(" ")) > 1 else 0
    headers = {}
    for line in lines[1:]:
        if ":" in line:
            key, _, value = line.partition(":")
            headers[key.strip().lower()] = value.strip()
    return status, headers, body.decode("utf-8", "replace")


def request(connect, method, path, headers=None, payload=None):
    """One HTTP/1.1 request/response over an already-connected socket."""
    head = "%s %s HTTP/1.1\r\nHost: workbuddy2api\r\nConnection: close\r\n" % (method, path)
    for key, value in (headers or {}).items():
        head += "%s: %s\r\n" % (key, value)
    body = b""
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        head += "Content-Type: application/json\r\nContent-Length: %d\r\n" % len(body)
    connect.sendall(head.encode("ascii") + b"\r\n" + body)
    chunks = []
    while True:
        try:
            data = connect.recv(65536)
        except socket.timeout:
            break
        if not data:
            break
        chunks.append(data)
    return parse_response(b"".join(chunks))


def unix_request(sock_path, method, path, headers=None, payload=None):
    conn = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    conn.settimeout(15)
    conn.connect(sock_path)
    try:
        return request(conn, method, path, headers, payload)
    finally:
        conn.close()


def tcp_request(port, method, path, headers=None, payload=None):
    conn = socket.create_connection(("127.0.0.1", port), timeout=15)
    conn.settimeout(15)
    try:
        return request(conn, method, path, headers, payload)
    finally:
        conn.close()


class GatewayProcess(object):
    """`wb_proxy.py` on a private port plus a gateway socket, both temporary."""

    def __init__(self):
        self.tmp = tempfile.mkdtemp(prefix="wb-gateway-")
        self.port = free_port()
        self.sock_path = os.path.join(self.tmp, "app.sock")
        accounts = os.path.join(self.tmp, "accounts")
        usage = os.path.join(self.tmp, "usage")
        os.makedirs(accounts)
        os.makedirs(usage)
        env = dict(os.environ)
        env.pop("ACCOUNTS_DIR", None)
        env.pop("USAGE_DIR", None)
        self.proc = subprocess.Popen(
            [sys.executable, os.path.join(ROOT, "wb_proxy.py"),
             "--host", "127.0.0.1", "--port", str(self.port),
             "--unix-socket", self.sock_path, "--base-path", PREFIX,
             "--accounts-dir", accounts, "--usage-dir", usage,
             "--panel-password", PANEL_PASSWORD],
            cwd=ROOT, env=env,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    def wait_ready(self, timeout=60):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.proc.poll() is not None:
                raise AssertionError("gateway exited early:\n" + self.output())
            try:
                with urllib.request.urlopen(
                        "http://127.0.0.1:%d/health" % self.port, timeout=2) as resp:
                    if resp.status == 200:
                        break
            except Exception:
                time.sleep(0.2)
        else:
            raise AssertionError("gateway never became ready:\n" + self.output())
        # The socket is bound before serve_forever starts, so give the accept
        # loop a moment rather than failing on the first connection refused.
        deadline = time.time() + 20
        while time.time() < deadline:
            try:
                status, _, body = unix_request(self.sock_path, "GET", "/health")
                if status == 200 and json.loads(body).get("ok"):
                    return
            except Exception:
                pass
            time.sleep(0.2)
        raise AssertionError("gateway socket never answered:\n" + self.output())

    def output(self):
        try:
            self.proc.terminate()
            return (self.proc.communicate(timeout=10)[0] or b"").decode("utf-8", "replace")
        except Exception:
            return ""

    def stop(self):
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=10)


class GatewaySocketTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gw = GatewayProcess()
        cls.gw.wait_ready()

    @classmethod
    def tearDownClass(cls):
        cls.gw.stop()

    def sso_headers(self):
        return {"X-Trim-Username": GATEWAY_USER}

    # -- the socket itself -------------------------------------------------

    def test_socket_is_world_writable(self):
        # The gateway is not this app's user, so a 0600 socket would leave the
        # App Center entry showing a connection error while everything else
        # looked fine.
        mode = stat.S_IMODE(os.stat(self.gw.sock_path).st_mode)
        self.assertEqual(0o666, mode, "gateway socket mode is %o" % mode)

    def test_requests_on_the_socket_are_served(self):
        status, _, body = unix_request(self.gw.sock_path, "GET", "/health")
        self.assertEqual(200, status)
        self.assertTrue(json.loads(body)["ok"])

    # -- single sign-on ---------------------------------------------------

    def test_gateway_identity_opens_the_panel(self):
        status, headers, _ = unix_request(self.gw.sock_path, "GET", "/accounts",
                                          self.sso_headers())
        self.assertEqual(200, status)
        self.assertIn("application/json", headers.get("content-type", ""))

    def test_gateway_identity_is_reported_to_the_page(self):
        # fnOS ages out its own session and stops sending X-Trim-Username while
        # the gateway keeps forwarding. The peer check - not the header - is
        # what makes the session signed in, so a socket request without it must
        # still be authenticated; only the displayed name goes missing.
        status, _, body = unix_request(self.gw.sock_path, "GET", "/panel/status")
        info = json.loads(body)
        self.assertEqual(200, status)
        self.assertTrue(info["via_gateway"])
        self.assertTrue(info["authenticated"],
                        "a gateway peer is a signed-in session even without the header")
        self.assertEqual("", info["gateway_user"], "no header means no name to show")

        status, _, body = unix_request(self.gw.sock_path, "GET", "/panel/status",
                                       self.sso_headers())
        info = json.loads(body)
        self.assertEqual(200, status)
        self.assertTrue(info["via_gateway"])
        self.assertEqual(GATEWAY_USER, info["gateway_user"])
        self.assertTrue(info["authenticated"], "sign-on replaces the panel password")
        # The settings page prints the client-facing addresses; the port is
        # configurable, so it has to come from here rather than from a
        # number someone typed into the page.
        self.assertEqual(self.gw.port, info["direct_port"])

    def test_panel_routes_open_on_the_socket_without_the_header(self):
        # The failure seen on the device: the panel fell back to its own
        # password page because the header was gone. Every management route
        # must answer on the socket.
        for path in ("/accounts", "/settings", "/logs", "/tasks", "/usage"):
            status, _, _ = unix_request(self.gw.sock_path, "GET", path)
            self.assertEqual(200, status, "%s needs the panel password again" % path)

    def test_panel_status_reports_the_direct_port(self):
        status, _, body = tcp_request(self.gw.port, "GET", "/panel/status")
        info = json.loads(body)
        self.assertEqual(200, status)
        self.assertEqual(self.gw.port, info["direct_port"])
        self.assertFalse(info["via_gateway"], "a port visit is not a gateway visit")

    def test_dashboard_carries_the_gateway_prefix(self):
        status, _, body = unix_request(self.gw.sock_path, "GET", "/", self.sso_headers())
        self.assertEqual(200, status)
        self.assertIn('<base href="%s/">' % PREFIX, body)
        self.assertIn('window.__WB_BASE__="%s"' % PREFIX, body)
        self.assertIn("window.__WB_VIA_GATEWAY__=true", body)
        self.assertIn('window.__WB_GATEWAY_USER__="%s"' % GATEWAY_USER, body)

    def test_prefix_arriving_at_the_server_is_stripped(self):
        # nginx is supposed to strip it. When it does not, the payload still
        # has to answer instead of 404-ing every asset and API call.
        status, _, body = unix_request(self.gw.sock_path, "GET", PREFIX + "/health")
        self.assertEqual(200, status)
        self.assertTrue(json.loads(body)["ok"])

        status, _, body = unix_request(self.gw.sock_path, "GET", PREFIX)
        self.assertEqual(200, status)
        self.assertIn("WorkBuddy", body)

    @unittest.skipUnless(hasattr(os, "setuid") and hasattr(os, "getuid")
                         and os.getuid() == 0,
                         "needs root to connect to the socket as another uid")
    def test_a_foreign_uid_on_the_socket_is_not_signed_in(self):
        # The socket is world-writable so the gateway can reach it whatever user
        # it runs as, which means the peer credentials are the only thing
        # keeping every other local user out of the panel. Drop to nobody in a
        # child process and prove that request is not treated as the gateway.
        os.chmod(self.gw.tmp, 0o755)          # let the child walk to the socket
        read_fd, write_fd = os.pipe()
        pid = os.fork()
        if pid == 0:                           # pragma: no cover - runs as nobody
            try:
                os.close(read_fd)
                os.setgroups([])
                os.setgid(65534)
                os.setuid(65534)
                accounts = unix_request(self.gw.sock_path, "GET", "/accounts")[0]
                panel = json.loads(unix_request(self.gw.sock_path, "GET",
                                                "/panel/status")[2])
                answer = {"accounts": accounts,
                          "authenticated": panel["authenticated"],
                          "gateway_user": panel["gateway_user"]}
            except Exception as exc:
                answer = {"error": repr(exc)}
            os.write(write_fd, json.dumps(answer).encode() + b"\n")
            os._exit(0)
        os.close(write_fd)
        with os.fdopen(read_fd, "rb") as pipe:
            raw = pipe.read()
        os.waitpid(pid, 0)
        result = json.loads((raw or b"{}").decode("utf-8", "replace").strip() or "{}")
        self.assertNotIn("error", result, "child could not make its request")
        self.assertEqual(401, result.get("accounts"),
                         "a foreign uid must not reach the panel")
        self.assertFalse(result.get("authenticated"),
                         "a foreign uid is not a signed-in NAS session")
        self.assertEqual("", result.get("gateway_user"))

    def test_panel_password_still_works_on_the_gateway(self):
        # The password is not required on the socket any more, but the route
        # itself must keep working there: a browser that reaches the payload
        # through the NAS proxy is on the socket, and logging in that way still
        # has to hand out a usable session token.
        status, _, _ = unix_request(self.gw.sock_path, "GET", "/accounts")
        self.assertEqual(200, status)

        status, _, body = unix_request(self.gw.sock_path, "POST", "/panel/login",
                                      payload={"password": PANEL_PASSWORD})
        self.assertEqual(200, status)
        token = json.loads(body)["token"]
        self.assertTrue(token)

        status, _, _ = unix_request(self.gw.sock_path, "GET", "/accounts",
                                    {"X-Panel-Token": token})
        self.assertEqual(200, status)

    # -- the port is not a way around the password ------------------------

    def test_forged_identity_header_is_ignored_on_tcp(self):
        status, _, _ = tcp_request(self.gw.port, "GET", "/accounts",
                                   {"X-Trim-Username": GATEWAY_USER})
        self.assertEqual(401, status, "the header must not authenticate over TCP")

    def test_health_stays_open_but_the_panel_does_not(self):
        # /health is the one thing a monitoring script is allowed to see; the
        # panel routes behind it are not.
        status, _, body = tcp_request(self.gw.port, "GET", "/health")
        self.assertEqual(200, status)
        self.assertTrue(json.loads(body)["ok"])

        status, _, _ = tcp_request(self.gw.port, "GET", "/panel/status")
        self.assertEqual(200, status)
        status, _, _ = tcp_request(self.gw.port, "GET", "/logs")
        self.assertEqual(401, status)

    def test_panel_password_works_on_the_port(self):
        status, _, body = tcp_request(self.gw.port, "POST", "/panel/login",
                                     payload={"password": PANEL_PASSWORD})
        self.assertEqual(200, status)
        token = json.loads(body)["token"]
        status, _, _ = tcp_request(self.gw.port, "GET", "/accounts",
                                   {"X-Panel-Token": token})
        self.assertEqual(200, status)

    def test_wrong_password_is_rejected_on_the_port(self):
        status, _, body = tcp_request(self.gw.port, "POST", "/panel/login",
                                     payload={"password": "not-the-password"})
        self.assertEqual(401, status)

    # -- the dashboard is the same file on both transports ----------------

    def test_direct_visits_get_no_prefix(self):
        status, _, body = tcp_request(self.gw.port, "GET", "/")
        self.assertEqual(200, status)
        # Phase F 合并口径（lead 裁决 A，2026-10-10）：缺省直连**不注入**上下文脚本。
        # 上游 tests/_test_dashboard_cache_headers.py 要求 GET / 的响应体逐字节等于
        # 「dashboard.html + 语言替换」，而我们原来的两条 assertIn 把「注入 ""」写成了
        # 硬期望。dashboard.html 自己按 `raw == null ? '' : String(raw)` 读全局量，
        # 所以「不注入」与「注入 ""」在页面上等价，这里改成负向断言。
        # 挂载态/网关态仍然注入（见上面 test_mounted_* 的四条 assertIn）。
        # 断言钉的是**注入形态**（`<script>window.__WB_BASE__=…`，见 wb_proxy.py 的
        # inject_dashboard_context），不是裸名字——页面自己的代码里本来就要读这两个
        # 全局量（`const raw = window.__WB_BASE__`、`window.__WB_VIA_GATEWAY__ === true`），
        # 裸名字的 assertNotIn 分不清「没注入」和「页面在代码里读它」，在上游版页面上
        # 会假绿（本层 _test_gateway_ui.js 反而要求页面必须读这两个全局量）。
        self.assertNotIn("<script>window.__WB_BASE__=", body,
                         "a default direct visit injects no context script")
        self.assertNotIn("<script>window.__WB_VIA_GATEWAY__=", body,
                         "a default direct visit injects no context script")
        self.assertNotIn("<base href=", body, "a direct visit is not under the prefix")


if __name__ == "__main__":
    unittest.main(verbosity=2)
