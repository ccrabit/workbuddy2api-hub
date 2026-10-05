"""Importing the server on a platform without AF_UNIX (Windows).

CI runs the suite on Windows as well, and the 1.6.10.2 push turned that red:
twenty suites died with "module 'socketserver' has no attribute
'UnixStreamServer'" because the gateway server class was declared
unconditionally. Every one of those failures was really one import error - the
gateway socket is a fnOS feature, and nothing on Windows needs it to exist,
only to not explode on the way past.

So this pins two things, the second one in a subprocess whose socketserver has
had the attribute removed (which is exactly what Windows looks like):

  * on a platform that has AF_UNIX the class is there and can be constructed;
  * on one that does not, `wb_proxy` still imports, the class is None, and
    asking for `--unix-socket` reports why instead of raising.

No network: temp directories only, and the socket is never actually served.
"""
import io
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

PASS = FAIL = 0


def check(label, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  [PASS] " + label)
    else:
        FAIL += 1
        print("  [FAIL] " + label + ("  " + str(extra) if extra else ""))


TMP = tempfile.mkdtemp(prefix="wb-platform-")

# What Windows looks like to us: socketserver without UnixStreamServer. The
# script runs in its own interpreter, so removing the attribute there cannot
# affect this one.
SIMULATED = textwrap.dedent('''
    import os, socket, socketserver, sys
    sys.path.insert(0, %r)
    if hasattr(socketserver, "UnixStreamServer"):
        del socketserver.UnixStreamServer
    if hasattr(socket, "AF_UNIX"):
        del socket.AF_UNIX
    import wb_proxy as P
    print("IMPORTED")
    print("CLASS", P.GatewayUnixHTTPServer)


    class Args(object):
        unix_socket = os.path.join(%r, "app.sock")
        base_path = "/app/workbuddy2api"


    print("OPEN", P._open_gateway_socket(Args(), P.Handler))
    print("SOCKET-CREATED", os.path.exists(Args.unix_socket))
''') % (ROOT, TMP)

script = os.path.join(TMP, "simulate_windows.py")
with io.open(script, "w", encoding="utf-8") as fh:
    fh.write(SIMULATED)

env = dict(os.environ)
env["ACCOUNTS_DIR"] = os.path.join(TMP, "accounts")
env["WB_PROXY_USAGE_DIR"] = os.path.join(TMP, "usage")
env["PYTHONPATH"] = os.pathsep.join(
    [ROOT] + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else []))

print("[1] a platform without AF_UNIX still imports, and says so")
proc = subprocess.run([sys.executable, script], env=env, cwd=ROOT,
                      stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
out = proc.stdout.decode("utf-8", "replace")
check("the import succeeds", proc.returncode == 0, out.strip()[-400:])
check("the gateway class is declared absent, not broken",
      "CLASS None" in out, out)
check("asking for --unix-socket returns None instead of raising",
      "OPEN None" in out, out)
check("and it does not silently create the socket file",
      "SOCKET-CREATED False" in out, out)
check("the reason is logged for the operator", "--unix-socket ignored" in out, out)
check("the message points at the port, which still works",
      "served on the port above" in out, out)

print()
print("[2] this platform is not the simulated one (the guards are conditional)")
import socket  # noqa: E402  (imported here so the skip reads clearly)
import socketserver  # noqa: E402
import wb_proxy as P  # noqa: E402

if hasattr(socket, "AF_UNIX") and hasattr(socketserver, "UnixStreamServer"):
    check("here the class exists", P.GatewayUnixHTTPServer is not None)
    check("and it is the Unix-server subclass",
          issubclass(P.GatewayUnixHTTPServer, socketserver.UnixStreamServer))
else:
    check("here the class is absent too", P.GatewayUnixHTTPServer is None)
    print("       (this run is on a platform without AF_UNIX; the simulated")
    print("        case above is then the same code path as the real one)")

shutil.rmtree(TMP, ignore_errors=True)
print()
print("PASS=%d FAIL=%d" % (PASS, FAIL))
sys.exit(1 if FAIL else 0)
