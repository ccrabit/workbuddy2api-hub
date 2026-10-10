#!/bin/bash
#
# Local dry run of a built .fpk.
#
# trim-cli (the real appcenter) is not available on this machine, so this
# unpacks the package the way appcenter does, exports the TRIM_* variables it
# sets, and walks the package through its whole lifecycle: install, start, an
# account import over HTTP, upgrade, stop, uninstall - including both answers
# to the wizard's "delete the data?" question.
#
#   bash scripts/verify-fpk.sh [dist/xxx.fpk] [--keep]
#
# Only a real NAS can prove the app-store path; everything below the package
# (the server starting, the account import, the data surviving an upgrade) is
# exercised here for real.
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PYTHON="${PYTHON:-python3}"

die() { printf '\033[0;31merror:\033[0m %s\n' "$*" >&2; exit 1; }
step() { printf '\n\033[0;36m--\033[0m %s\n' "$*"; }
ok()   { printf '  \033[0;32mPASS\033[0m %s\n' "$*"; PASS=$((PASS + 1)); }
bad()  { printf '  \033[0;31mFAIL\033[0m %s\n' "$*"; FAIL=$((FAIL + 1)); FAILED_NAMES+=("$*"); }

PASS=0
FAIL=0
FAILED_NAMES=()
LAST_OUTPUT=""

FPK=""
KEEP=0
for arg in "$@"; do
    case "$arg" in
        --keep) KEEP=1 ;;
        -*) die "unknown option: $arg" ;;
        *) FPK="$arg" ;;
    esac
done
if [ -z "$FPK" ]; then
    FPK="$(ls -t "${REPO_ROOT}"/dist/*.fpk 2>/dev/null | head -1 || true)"
fi
[ -n "$FPK" ] && [ -f "$FPK" ] || die "no fpk to verify - build one with: bash scripts/build-fpk.sh"
FPK="$(cd "$(dirname "$FPK")" && pwd)/$(basename "$FPK")"
command -v "$PYTHON" >/dev/null 2>&1 || die "python3 is required to drive the checks"

# run <expected-exit-code> <description> <command...>
run() {
    local want="$1" desc="$2"
    shift 2
    local output rc
    set +e
    output="$("$@" 2>&1)"
    rc=$?
    set -e
    LAST_OUTPUT="$output"
    if [ "$rc" = "$want" ]; then
        ok "$desc"
    else
        bad "$desc (exit ${rc}, wanted ${want})"
        printf '%s\n' "$output" | tail -5 | sed 's/^/         /'
    fi
}

# assert <description> <test command...>
assert() {
    local desc="$1"
    shift
    if "$@" >/dev/null 2>&1; then
        ok "$desc"
    else
        bad "$desc"
    fi
}

WORK="$(mktemp -d "${TMPDIR:-/tmp}/wb2api-verify-XXXXXX")"
APP="${WORK}/var/apps/workbuddy2api"
mkdir -p "${APP}/target" "${APP}/var" "${APP}/etc" "${APP}/home"

printf '\033[0;32m==>\033[0m verifying %s\n' "$(basename "$FPK")"
printf '    sandbox: %s\n' "$WORK"
tar -xzf "$FPK" -C "$APP"
tar -xzf "${APP}/app.tgz" -C "${APP}/target"

# The product name is what the user sees (fpk file name, App Center entry,
# Release title); `appname` is the identifier the device keys the install, the
# data directory and the gateway prefix off. They are deliberately not the same
# string, and this block is what keeps a build from quietly renaming one of them.
PRODUCT="WorkBuddy2API-Hub"
FPK_BASE="$(basename "$FPK")"
MANIFEST_VERSION="$(awk -F'=' '/^version/ {gsub(/[[:space:]]/, "", $2); print $2; exit}' "${APP}/manifest")"
MANIFEST_PLATFORM="$(awk -F'=' '/^platform/ {gsub(/[[:space:]]/, "", $2); print $2; exit}' "${APP}/manifest")"

step "package identity"
assert "the file name carries the product name" bash -c '[[ "$0" == WorkBuddy2API-Hub_* ]]' "$FPK_BASE"
# The packaged version is upstream's own three components: a release of this
# fork is tagged fnos-1.6.19 and the package says 1.6.19. Phase E gave this fork
# a fourth "release ordinal" component; nothing carries one now, and the shape
# below is what keeps one - or a process version like 1.6.19-alpha3 - from
# reaching a device.
assert "the manifest version is upstream's three components" \
    bash -c '[[ "$0" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]' "$MANIFEST_VERSION"
assert "the file name and the manifest agree on it" \
    test "$FPK_BASE" = "${PRODUCT}_${MANIFEST_VERSION}_${MANIFEST_PLATFORM}.fpk"
run 0 "the tree still derives a version" bash "${REPO_ROOT}/scripts/build-fpk.sh" --print-version
# On a release tag the tree derives exactly the version the tag names, and then
# the package under test has to be that version. Without one - a local run, or a
# tree where nobody has tagged this state yet - the tree derives a process
# version (1.6.19-alpha3) which is deliberately not equal to a package, so there
# is nothing to compare; the shape check above still applies.
DERIVED_VERSION="${LAST_OUTPUT}"
if [[ "$DERIVED_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    assert "the package is what this tree builds" test "$DERIVED_VERSION" = "${MANIFEST_VERSION}"
else
    printf '  \033[0;33mSKIP\033[0m no fnos-<version> tag on HEAD (the tree derives %s);\n' "$DERIVED_VERSION"
    printf '       the package under test is %s, which no release tag here claims\n' "$MANIFEST_VERSION"
fi
assert "the manifest shows the product name" \
    grep -q '^display_name[[:space:]]*=[[:space:]]*WorkBuddy2API-Hub$' "${APP}/manifest"
assert "the desktop entry shows it too" grep -q '"title": "WorkBuddy2API-Hub"' "${APP}/target/ui/config"
assert "the appname identifier is unchanged" \
    grep -q '^appname[[:space:]]*=[[:space:]]*workbuddy2api$' "${APP}/manifest"

step "package contents"
# appcenter reads the desktop entry from inside the payload, not from the fpk
# root; a package without it installs but never gets an "open" entry.
assert "the payload carries the desktop entry" test -f "${APP}/target/ui/config"
assert "the payload carries the 64px icon" test -f "${APP}/target/ui/images/64.png"
assert "the payload carries the 256px icon" test -f "${APP}/target/ui/images/256.png"
assert "the payload carries config/privilege" test -f "${APP}/target/config/privilege"
assert "the payload carries config/resource" test -f "${APP}/target/config/resource"

# The App Center entry is an iframe over a unix socket inside the payload: an
# url/port entry would open the panel in a new tab and skip fnOS sign-on, which
# is the whole point of the entry.
ENTRY="${APP}/target/ui/config"
assert "the desktop entry is a gateway iframe" grep -q '"type": "iframe"' "$ENTRY"
assert "  ...reaching the payload socket" grep -q '"gatewaySocket": "app.sock"' "$ENTRY"
assert "  ...mounted at the app's own prefix" grep -q '"gatewayPrefix": "/app/workbuddy2api"' "$ENTRY"
assert "cmd/main listens on that socket" grep -q -- '--unix-socket' "${APP}/cmd/main"
assert "cmd/main serves that prefix" grep -q -- '--base-path' "${APP}/cmd/main"

step "payload matches the repository"
# Listing the tree instead of a hand-written module list: upstream adds modules
# between releases, and a package that starts on the NAS and dies on ImportError
# is exactly what this check exists to prevent.
MODULES_MISSING=""
while IFS= read -r module; do
    [ -f "${APP}/target/server/${module}" ] || MODULES_MISSING="${MODULES_MISSING} ${module}"
done < <(find "${REPO_ROOT}" -maxdepth 1 -type f \( -name 'wb_*.py' -o -name '*.html' \) -printf '%f\n' | sort)
assert "the payload carries every top-level module of the tree" test -z "$MODULES_MISSING"
assert "the payload carries the pricing store" test -f "${APP}/target/server/pricing/pricing.json"

# Credentials, machine state, the test suite and our own working docs stay in
# the checkout: the package ships code, not our bookkeeping. Each directory is
# asserted on its own so a failure names the one that leaked.
assert "the payload leaves accounts/ behind" test ! -e "${APP}/target/server/accounts"
assert "the payload leaves usage/ behind" test ! -e "${APP}/target/server/usage"
assert "the payload leaves tests/ behind" test ! -e "${APP}/target/server/tests"
assert "the payload leaves docs/ behind" test ! -e "${APP}/target/server/docs"

# Byte for byte, walked from the payload side: every file that ships has to be
# the file that is in the tree right now, so a package built before the last
# edit to a module cannot pass. This is the check that catches "the box was
# built while someone was still writing".
payload_matches_the_tree() {
    local file rel
    while IFS= read -r -d '' file; do
        rel="${file#"${APP}/target/server/"}"
        if ! cmp -s "$file" "${REPO_ROOT}/${rel}"; then
            printf 'not in the tree, or different: %s\n' "$rel"
        fi
    done < <(find "${APP}/target/server" -type f -print0)
}
DRIFT="$(payload_matches_the_tree || true)"
assert "every packaged file is byte-identical to the tree" test -z "$DRIFT"
[ -z "$DRIFT" ] || printf '%s\n' "$DRIFT" | head -5 | sed 's/^/         /'

PORT="$("$PYTHON" -c 'import socket; s = socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1]); s.close()')"

# What appcenter hands to the lifecycle scripts. TRIM_USERNAME is the package
# user on a NAS; this machine has none, so root stands in for it.
export TRIM_APPNAME=workbuddy2api
export TRIM_APPDEST="${APP}/target"
export TRIM_PKGVAR="${APP}/var"
export TRIM_PKGETC="${APP}/etc"
export TRIM_PKGHOME="${APP}/home"
export TRIM_SERVICE_PORT="$PORT"
export TRIM_TEMP_LOGFILE="${WORK}/dialog.log"
export TRIM_USERNAME=root
export TRIM_GROUPNAME=root
export TRIM_OLD_APPVER=1.6.10
export TRIM_APPVER=1.6.10.1
BASE_URL="http://127.0.0.1:${PORT}"

# ---------------------------------------------------------------- driver ----
cat > "${WORK}/driver.py" <<'PY'
"""The HTTP side of the verification run."""
import json
import sys
import time
import urllib.error
import urllib.request

base, action = sys.argv[1], sys.argv[2]


def call(path, payload=None, token=None):
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {"Content-Type": "application/json"} if data else {}
    if token:
        headers["X-Panel-Token"] = token
    req = urllib.request.Request(base + path, data=data, headers=headers,
                                 method="POST" if data else "GET")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.load(resp)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        try:
            return exc.code, json.loads(body)
        except ValueError:
            return exc.code, {"raw": body}


def must(status, body):
    if status != 200:
        print(json.dumps(body), file=sys.stderr)
        raise SystemExit("HTTP %s" % status)
    return body


if action == "wait":
    deadline = time.time() + float(sys.argv[3])
    while time.time() < deadline:
        try:
            status, body = call("/health")
            if status == 200 and body.get("ok"):
                print(json.dumps(body))
                raise SystemExit(0)
        except (urllib.error.URLError, OSError):
            pass
        time.sleep(0.5)
    raise SystemExit("the gateway never answered /health")
elif action == "health":
    print(json.dumps(must(*call("/health"))))
elif action == "accounts":
    print(must(*call("/health")).get("accounts"))
elif action == "login":
    print(must(*call("/panel/login", {"password": sys.argv[3]}))["token"])
elif action == "import":
    token, path = sys.argv[3], sys.argv[4]
    with open(path) as handle:
        document = json.load(handle)
    payload = {"data": document, "dryRun": sys.argv[5] == "dry"}
    print(json.dumps(must(*call("/accounts/import", payload, token=token))))
else:
    raise SystemExit("unknown action %r" % action)
PY
driver() { "$PYTHON" "${WORK}/driver.py" "$BASE_URL" "$@"; }

# Run the lifecycle from a neutral directory: the scripts have to work out
# where they are from TRIM_APPDEST, not from the caller's cwd.
cd "$WORK"

# ------------------------------------------------- real appcenter layout ----
# On a NAS the hooks never see TRIM_APPDEST=/var/apps/<app>/target: a real
# install runs with TRIM_APPDEST=<volume>/@appcenter/<appname>, the payload
# directory itself. A hook that assumes the .../target suffix looks for cmd/main
# one level too high, and appcenter (fnOS 1.2.0800) answers
#
#   Unable to install workbuddy2api
#   Incomplete package: /vol1/@appcenter/cmd/main is missing
#
# while the install is still in install_init. This phase is the guard for that
# exact failure, which is why it comes before the lifecycle below.
step "the layout appcenter really uses"
REAL_ROOT="${WORK}/real"
REAL_VOL="${REAL_ROOT}/vol1"
REAL_APPDIR="${REAL_ROOT}/var/apps/workbuddy2api"
REAL_PAYLOAD="${REAL_VOL}/@appcenter/workbuddy2api"
REAL_VAR="${REAL_VOL}/@appdata/workbuddy2api"
mkdir -p "$REAL_APPDIR" "$REAL_PAYLOAD" "$REAL_VAR" \
         "${REAL_VOL}/@appconf/workbuddy2api" "${REAL_VOL}/@apphome/workbuddy2api"
tar -xzf "$FPK" -C "$REAL_APPDIR"
tar -xzf "${REAL_APPDIR}/app.tgz" -C "$REAL_PAYLOAD"
PORT2="$("$PYTHON" -c 'import socket; s = socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1]); s.close()')"

# appcenter always exports TRIM_APPNAME; the sandbox has to do the same, or the
# hooks fall back to whatever app the *caller's* environment names (in the agent
# harness that is the harness itself, so this guard used to end up running
# somebody else's lifecycle script). WB_APPDIR pins the hooks' last candidate -
# the absolute /var/apps/<app> path, which a sandbox cannot otherwise own.
real_hook() {
    local script="$1"
    shift
    env TRIM_APPNAME="workbuddy2api" \
        TRIM_APPDEST="$REAL_PAYLOAD" \
        WB_APPDIR="$REAL_APPDIR" \
        TRIM_PKGVAR="$REAL_VAR" \
        TRIM_PKGETC="${REAL_VOL}/@appconf/workbuddy2api" \
        TRIM_PKGHOME="${REAL_VOL}/@apphome/workbuddy2api" \
        TRIM_SERVICE_PORT="$PORT2" \
        TRIM_TEMP_LOGFILE="${WORK}/dialog-real.log" \
        bash "${REAL_APPDIR}/cmd/${script}" "$@"
}

real_health() {
    "$PYTHON" - "$PORT2" <<'PY'
import json
import sys
import time
import urllib.request

url = "http://127.0.0.1:%s/health" % sys.argv[1]
deadline = time.time() + 20
while True:
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            print(json.dumps(json.load(resp)))
            break
    except Exception:
        if time.time() > deadline:
            raise SystemExit("the gateway never answered /health on %s" % url)
        time.sleep(0.5)
PY
}

# What the fnOS gateway does: connect to <payload>/app.sock, hand over the
# authenticated NAS user in a header, and expect the panel to let them in.
real_gateway_signon() {
    "$PYTHON" - "${REAL_PAYLOAD}/app.sock" <<'PY'
import json
import socket
import sys
import time

sock_path = sys.argv[1]
USER = "deepseek.harness"
deadline = time.time() + 20
problem = "no answer"
while True:
    try:
        conn = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        conn.settimeout(10)
        conn.connect(sock_path)
        conn.sendall(b"GET /panel/status HTTP/1.1\r\nHost: workbuddy2api\r\n"
                     b"X-Trim-Username: " + USER.encode() + b"\r\n"
                     b"Connection: close\r\n\r\n")
        chunks = []
        while True:
            data = conn.recv(65536)
            if not data:
                break
            chunks.append(data)
        conn.close()
        head, _, body = b"".join(chunks).partition(b"\r\n\r\n")
        status = int(head.split(b" ")[1])
        info = json.loads(body.decode("utf-8"))
        problem = ("status=%s via_gateway=%r gateway_user=%r authenticated=%r"
                   % (status, info.get("via_gateway"), info.get("gateway_user"),
                      info.get("authenticated")))
        if (status == 200 and info.get("via_gateway")
                and info.get("gateway_user") == USER and info.get("authenticated")):
            print(problem)
            raise SystemExit(0)
        break
    except Exception as exc:
        problem = str(exc)
        if time.time() > deadline:
            break
        time.sleep(0.5)
raise SystemExit("the gateway socket did not sign the NAS user in: %s" % problem)
PY
}

# The frozen Phase E 口径: on the gateway socket the peer check alone signs the
# NAS user in - X-Trim-Username only names them. A fnOS session that has aged
# out stops sending the header, and the panel used to answer with its own
# password prompt; this is the guard against that behaviour coming back.
real_gateway_signon_without_session_header() {
    "$PYTHON" - "${REAL_PAYLOAD}/app.sock" <<'PY'
import json
import socket
import sys
import time

sock_path = sys.argv[1]
deadline = time.time() + 20
problem = "no answer"
while True:
    try:
        conn = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        conn.settimeout(10)
        conn.connect(sock_path)
        conn.sendall(b"GET /panel/status HTTP/1.1\r\nHost: workbuddy2api\r\n"
                     b"Connection: close\r\n\r\n")
        chunks = []
        while True:
            data = conn.recv(65536)
            if not data:
                break
            chunks.append(data)
        conn.close()
        head, _, body = b"".join(chunks).partition(b"\r\n\r\n")
        status = int(head.split(b" ")[1])
        info = json.loads(body.decode("utf-8"))
        problem = ("status=%s via_gateway=%r authenticated=%r"
                   % (status, info.get("via_gateway"), info.get("authenticated")))
        if status == 200 and info.get("via_gateway") and info.get("authenticated"):
            print(problem)
            raise SystemExit(0)
        break
    except Exception as exc:
        problem = str(exc)
        if time.time() > deadline:
            break
        time.sleep(0.5)
raise SystemExit("the gateway socket asked for a password without a session header: %s"
                 % problem)
PY
}

run 0 "install_init accepts a payload-shaped TRIM_APPDEST" real_hook install_init
run 0 "install_callback accepts a payload-shaped TRIM_APPDEST" real_hook install_callback
assert "the data directories were created there too" test -d "${REAL_VAR}/accounts"
run 0 "start works from the payload shape" real_hook main start
run 0 "the gateway answers /health" real_health
assert "the gateway socket is world-writable" \
    test "$(stat -c %a "${REAL_PAYLOAD}/app.sock")" = "666"
run 0 "the gateway signs the NAS user in" real_gateway_signon
run 0 "  ...and still does when the session header is gone" real_gateway_signon_without_session_header
run 0 "status says 'running'" real_hook main status
run 0 "stop works from the payload shape" real_hook main stop
assert "stop removes the socket file" test ! -e "${REAL_PAYLOAD}/app.sock"
run 3 "status says 'not running' again" real_hook main status

step "install"
run 0 "install_init accepts the package" bash "${APP}/cmd/install_init"
run 0 "install_callback installs it" bash "${APP}/cmd/install_callback"
assert "the app file is executable" test -x "${APP}/cmd/main"
assert "the payload landed in target/server" test -f "${APP}/target/server/wb_proxy.py"
assert "the data directories were created" test -d "${APP}/var/accounts"
run 3 "status says 'not running' (exit 3)" bash "${APP}/cmd/main" status

step "start"
run 0 "start brings the gateway up" bash "${APP}/cmd/main" start
run 0 "status says 'running' (exit 0)" bash "${APP}/cmd/main" status
run 0 "the gateway answers /health" driver wait 20
assert "the log file was written" test -s "${APP}/var/workbuddy2api.log"
assert "no accounts yet" test "$(driver accounts)" = "0"

step "import a cockpit-tools export over HTTP"
"$PYTHON" - "${WORK}/cockpit.json" <<'PY'
import base64
import json
import sys
import time


def segment(obj):
    raw = json.dumps(obj, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


token = "%s.%s.%s" % (
    segment({"alg": "none", "typ": "JWT"}),
    segment({"sub": "verify-1", "exp": int(time.time()) + 3600,
             "iss": "https://api.workbuddy.ai"}),
    "signature",
)
row = {
    "uid": "verify-1",
    "nickname": "Verify One",
    "access_token": token,
    "refresh_token": "refresh-verify-1",
    "expires_at": int((time.time() + 7200) * 1000),
    "domain": "www.workbuddy.ai",
    "status": "active",
}
with open(sys.argv[1], "w") as handle:
    json.dump([row], handle)
PY

TOKEN=""
set +e
TOKEN="$(driver login admin 2>&1)"
LOGIN_RC=$?
set -e
if [ "$LOGIN_RC" = 0 ] && [ -n "$TOKEN" ]; then
    ok "the panel accepts the default password"
else
    bad "the panel accepts the default password"
    printf '%s\n' "$TOKEN" | tail -3 | sed 's/^/         /'
fi

run 0 "the dry run reads the file" driver import "$TOKEN" "${WORK}/cockpit.json" dry
assert "the dry run wrote nothing" test ! -e "${APP}/var/accounts/verify-1.json"
run 0 "the real import is accepted" driver import "$TOKEN" "${WORK}/cockpit.json" real
assert "the credential is in the data directory" test -f "${APP}/var/accounts/verify-1.json"
assert "the file uses camelCase" grep -q '"accessToken"' "${APP}/var/accounts/verify-1.json"
assert "nothing leaked the snake_case spelling" bash -c "! grep -q '\"access_token\"' '${APP}/var/accounts/verify-1.json'"
assert "nothing was written into the payload" test ! -e "${APP}/target/server/accounts"
assert "the gateway sees one account" test "$(driver accounts)" = "1"

step "upgrade keeps the accounts"
tar -xzf "${APP}/app.tgz" -C "${APP}/target"
run 0 "upgrade_init stops the running version" bash "${APP}/cmd/upgrade_init"
run 0 "upgrade_callback installs the new files" bash "${APP}/cmd/upgrade_callback"
run 3 "the service stays stopped until asked" bash "${APP}/cmd/main" status
run 0 "start after the upgrade" bash "${APP}/cmd/main" start
run 0 "the gateway answers again" driver wait 20
assert "the imported account survived" test "$(driver accounts)" = "1"

step "stop and uninstall"
run 0 "stop stops the gateway" bash "${APP}/cmd/main" stop
run 3 "status says 'not running' again" bash "${APP}/cmd/main" status
run 0 "uninstall_init stops (already stopped)" bash "${APP}/cmd/uninstall_init"
run 0 "uninstall_callback keeps the data by default" bash "${APP}/cmd/uninstall_callback"
assert "the account file is still there" test -f "${APP}/var/accounts/verify-1.json"
run 0 "uninstall_callback after 'delete the data'" env wizard_delete_data=true bash "${APP}/cmd/uninstall_callback"
assert "the data directory is empty" test -z "$(ls -A "${APP}/var")"
assert "the config directory is empty" test -z "$(ls -A "${APP}/etc")"

printf '\n\033[0;32m==>\033[0m %d passed, %d failed\n' "$PASS" "$FAIL"
if [ "$FAIL" -gt 0 ]; then
    printf '    failed: %s\n' "${FAILED_NAMES[*]}"
    printf '    sandbox kept for inspection: %s\n' "$WORK"
    exit 1
fi
if [ "$KEEP" = 1 ]; then
    printf '    sandbox kept: %s\n' "$WORK"
else
    rm -rf "$WORK"
fi
printf '    the package behaves; only a real NAS can test the app store itself.\n'
