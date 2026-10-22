#!/usr/bin/env bash
#
# wb-auto-sync — unattended upstream sync, release and on-box upgrade.
#
#   scripts/auto-sync-upstream.sh [--check] [--no-install] [--no-publish]
#
# What it does, in order:
#   1. git fetch upstream --tags
#   2. VERSION = the newest upstream release tag vX.Y.Z
#   3. bail out when fnos-$VERSION already exists (exit 2, nothing to do)
#   4. merge upstream/main into a throwaway branch — a conflict stops here
#      (exit 3) because resolving it needs judgement, not a script
#   5. mechanical fixups (scripts/auto_sync_fixups.py): README suite count,
#      payload guard lists for new modules, workflow policy, release metadata
#   6. build + verify-fpk + sha256 sidecar
#   7. install on this box (payload swap + restart + /health), with rollback
#   8. full test suite must be green — it runs *after* the install, because the
#      delivery-doc gate compares its device-version claims with the version
#      that is actually running
#   9. tag + push + GitHub release + FnDepot source, then a run report under
#      logs/auto-sync/
#
# Exit codes: 0 released, 2 up to date, 3 needs a human (conflict), 4 tests red,
#             5 build/verify failed, 6 publish failed, 7 install failed.
#
# The one thing to keep in mind: this box serves its own model traffic through
# the gateway we restart. The install window is a handful of seconds and the
# script always ends by starting the service again; keep the schedule at a
# quiet hour.
set -uo pipefail

REPO="${WB_REPO:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
LOG_DIR="${WB_LOG_DIR:-$REPO/logs/auto-sync}"
TOKEN_FILE="${WB_TOKEN_FILE:-/root/.gh-token}"
FNDEPOT_TOKEN_FILE="${WB_FNDEPOT_TOKEN_FILE:-/root/.gh-token-classic}"
FNDEPOT_SRC="${WB_FNDEPOT_SRC:-/tmp/fndepot-src}"
APPNAME="${WB_APP_NAME:-workbuddy2api}"
APPCENTER="${WB_APPCENTER:-/vol1/@appcenter/$APPNAME}"
APPDIR="${WB_APPDIR:-/var/apps/$APPNAME}"
HEALTH_URL="${WB_HEALTH_URL:-http://127.0.0.1:8788/health}"
INSTALL=1
PUBLISH=1
CHECK=0
for arg in "$@"; do
    case "$arg" in
        --no-install) INSTALL=0 ;;
        --no-publish) PUBLISH=0 ;;
        --check) CHECK=1; INSTALL=0; PUBLISH=0 ;;
        *) echo "unknown argument: $arg" >&2; exit 64 ;;
    esac
done
export WB_FNDEPOT_SRC="$FNDEPOT_SRC"

mkdir -p "$LOG_DIR"
RUN_ID="$(date +%Y%m%d-%H%M%S)"
LOG="$LOG_DIR/$RUN_ID.log"
REPORT="$LOG_DIR/$RUN_ID.md"
ln -sfn "$(basename "$LOG")" "$LOG_DIR/last.log"
exec > >(tee -a "$LOG") 2>&1

say()  { printf '%s %s\n' "$(date '+%H:%M:%S')" "$*"; }
fail() { say "FAIL: $*"; report "failed: $*"; exit "${2:-1}"; }
report() { printf '%s\n' "$*" >> "$REPORT"; }

cd "$REPO" || exit 1
# The suite gate is useless if the JS suites silently skip themselves.
command -v node >/dev/null || fail "node is not on PATH — the JS suites would be skipped" 5
command -v python3 >/dev/null || fail "python3 is not on PATH" 5
exec 9>"$LOG_DIR/.lock"
flock -n 9 || { say "another run holds the lock"; exit 0; }

say "== wb-auto-sync $RUN_ID (repo $REPO)"
report "# wb-auto-sync $RUN_ID"
report ""
report "- repo: \`$REPO\`"
report "- args: \`$*\`"

# 1-2 ---------------------------------------------------------------- upstream
git fetch --quiet upstream --tags || fail "git fetch upstream" 6
UPSTREAM_SHA="$(git rev-parse upstream/main)"
VERSION="$(git tag -l 'v[0-9]*' --sort=-v:refname | head -1 | sed 's/^v//')"
[ -n "$VERSION" ] || fail "no upstream release tag found" 6
say "upstream/main=$UPSTREAM_SHA  newest release tag=v$VERSION"
report "- upstream/main: \`$UPSTREAM_SHA\`"
report "- target version: \`$VERSION\`"

# 3 ------------------------------------------------------------- up to date?
if git rev-parse -q --verify "refs/tags/fnos-$VERSION" >/dev/null; then
    if git merge-base --is-ancestor "$UPSTREAM_SHA" "fnos-$VERSION^{commit}"; then
        say "fnos-$VERSION already contains upstream/main — nothing to do"
        report ""
        report "Already up to date: \`fnos-$VERSION\` contains \`$UPSTREAM_SHA\`."
        exit 2
    fi
fi

# 4 ------------------------------------------------------------------- merge
BASE="$(git merge-base HEAD upstream/main)"
say "merge base is ${BASE:0:8}"
BRANCH="auto/upstream-$VERSION"
if [ "$CHECK" = 1 ]; then
    say "[check] would merge $UPSTREAM_SHA into a new branch $BRANCH"
    git merge-tree --write-tree HEAD "$UPSTREAM_SHA" >/dev/null 2>&1 \
        && say "[check] merge is conflict-free" \
        || say "[check] merge has conflicts — a human is needed"
    rm -f "$LOG_DIR/.lock"
    exit 0
fi
git checkout --quiet -B "$BRANCH" || fail "git checkout -B $BRANCH" 6
if ! git merge --no-commit --no-ff --quiet upstream/main; then
    say "merge conflicts:"
    git diff --name-only --diff-filter=U | sed 's/^/    /'
    report ""
    report "## Needs a human: merge conflicts"
    git diff --name-only --diff-filter=U | sed 's/^/- `/;s/$/`/' >> "$REPORT"
    git merge --abort
    git checkout --quiet - 2>/dev/null || true
    say "aborted; resolve by hand: git checkout -b $BRANCH && git merge --no-commit --no-ff upstream/main"
    exit 3
fi
say "merged cleanly into $BRANCH"

fixups() { python3 scripts/auto_sync_fixups.py --version "$VERSION" --base "$BASE" \
              --upstream "$UPSTREAM_SHA" "$@"; }

fixups || fail "mechanical fixups" 6

# 6 ------------------------------------------------------------------- build
FPK="dist/WorkBuddy2API-Hub_${VERSION}_all.fpk"
say "== building $VERSION"
VERSION="$VERSION" PACKAGER=ccrabit PACKAGER_URL=https://github.com/ccrabit/workbuddy2api-hub \
    bash scripts/build-fpk.sh >"$LOG.build" 2>&1 \
    || { tail -20 "$LOG.build"; fail "build-fpk.sh (see $LOG.build)" 5; }
grep -E '^\s+(version|checksum|payload)' "$LOG.build" | sed 's/^/    /'
bash scripts/verify-fpk.sh "$FPK" >>"$LOG.verify" 2>&1 \
    || { tail -20 "$LOG.verify"; fail "verify-fpk.sh (see $LOG.verify)" 5; }
say "verify-fpk: $(grep -o '[0-9]* passed, [0-9]* failed' "$LOG.verify" | tail -1)"
python3 scripts/gh-release.py sha256 "$FPK" > "$FPK.sha256"
SIZE="$(stat -c %s "$FPK")"
SHA256="$(cut -d' ' -f1 "$FPK.sha256")"
say "package: $FPK  $SIZE B  $SHA256"
report "- package: \`$SIZE\` B, sha256 \`$SHA256\`"

# 7 ----------------------------------------------------------------- install
install_package() {
    local fpk="$1" version="$2" tmp backup sums
    tmp="$(mktemp -d)"; backup="$APPCENTER/../install-backup-$(date +%Y%m%d-%H%M%S)"
    mkdir -p "$tmp/payload" "$backup"
    say "backup → $backup"
    tar -C "$APPCENTER" -cf "$backup/payload.tar" . 2>/dev/null
    tar -C "$APPDIR" -cf "$backup/appdir.tar" cmd wizard manifest ICON.PNG ICON_256.PNG 2>/dev/null
    tar -xzf "$fpk" -C "$tmp" || { say "cannot unpack $fpk"; return 1; }
    tar -xzf "$tmp/app.tgz" -C "$tmp/payload" || { say "cannot unpack app.tgz"; return 1; }
    sums="$(md5sum "$tmp/app.tgz" | cut -d' ' -f1)"

    if [ "${WB_SKIP_LIFECYCLE:-0}" = 1 ]; then
        say "rehearsal: leaving the service alone"
    else
        say "stopping $APPNAME (the gateway serves its own model traffic — keep this short)"
        "$APPDIR/cmd/main" stop >/dev/null 2>&1
    fi
    local d
    for d in server config ui; do
        [ -d "$tmp/payload/$d" ] || continue
        rm -rf "$APPCENTER/$d.new"
        cp -a "$tmp/payload/$d" "$APPCENTER/$d.new" || { say "copy $d failed"; restore "$backup"; return 1; }
        rm -rf "$APPCENTER/$d"
        mv "$APPCENTER/$d.new" "$APPCENTER/$d"
    done
    [ -d "$tmp/cmd" ] && cp -a "$tmp/cmd/." "$APPDIR/cmd/" 2>/dev/null
    [ -d "$tmp/wizard" ] && cp -a "$tmp/wizard/." "$APPDIR/wizard/" 2>/dev/null
    cp -a "$tmp"/ICON*.PNG "$APPDIR/" 2>/dev/null
    chown -R "$APPNAME:$APPNAME" "$APPCENTER" 2>/dev/null
    sed -i -E "s/^version[[:space:]]*=.*/version         = $version/" "$APPDIR/manifest"
    sed -i -E "s/^checksum[[:space:]]*=.*/checksum        = $sums/" "$APPDIR/manifest"
    "$APPDIR/cmd/main" install >/dev/null 2>&1
    [ "${WB_SKIP_LIFECYCLE:-0}" = 1 ] && return 0
    "$APPDIR/cmd/main" start >/dev/null 2>&1
    wait_health "$version" && return 0
    say "health check failed for $version — rolling back"
    restore "$backup"
}

restore() {
    local backup="$1"
    "$APPDIR/cmd/main" stop >/dev/null 2>&1
    rm -rf "$APPCENTER/server.new" "$APPCENTER/config.new" "$APPCENTER/ui.new"
    tar -C "$APPCENTER" -xf "$backup/payload.tar" 2>/dev/null
    tar -C "$APPDIR" -xf "$backup/appdir.tar" 2>/dev/null
    "$APPDIR/cmd/main" start >/dev/null 2>&1
    if wait_health ""; then say "rolled back and serving again"; else say "ROLLBACK FAILED — service is down"; fi
}

wait_health() {
    local want="$1" i stamp
    for i in $(seq 1 45); do
        stamp="$(curl -s -m 3 -D - -o /dev/null "$HEALTH_URL" 2>/dev/null \
                 | tr -d '\r' | awk -F': ' 'tolower($1)=="server"{print $2}')"
        if [ -n "$stamp" ]; then
            if [ -z "$want" ] || [ "$stamp" = "wb-proxy/$want Python/3.12.4" ] \
               || printf '%s' "$stamp" | grep -q "wb-proxy/$want"; then
                say "health ok after ${i}s: Server: $stamp"
                return 0
            fi
        fi
        sleep 1
    done
    say "health check timed out (last Server: ${stamp:-none})"
    return 1
}

if [ "$INSTALL" = 1 ]; then
    say "== installing $VERSION on this box"
    install_package "$FPK" "$VERSION" || fail "install/rollback (service state must be checked by hand)" 7
    DEVICE_VERSION="$(curl -s -m 5 -D - -o /dev/null "$HEALTH_URL" | tr -d '\r' \
                      | sed -n 's/^[Ss]erver: wb-proxy\/\([0-9.]*\).*/\1/p')"
    report "- installed on box: \`$DEVICE_VERSION\`"
else
    DEVICE_VERSION="$(curl -s -m 5 -D - -o /dev/null "$HEALTH_URL" | tr -d '\r' \
                      | sed -n 's/^[Ss]erver: wb-proxy\/\([0-9.]*\).*/\1/p')"
    say "skipping install (--no-install); box runs ${DEVICE_VERSION:-unknown}"
fi

# 8 --------------------------------------------------------- metadata + tests
fixups --fpk "$FPK" --device-version "${DEVICE_VERSION:-$VERSION}" \
    || fail "release-metadata fixups" 6
python3 tests/run_all.py --jobs 4 >"$LOG.suite" 2>&1
SUITE="$(tail -3 "$LOG.suite" | grep -o '[0-9]* passed, [0-9]* failed, [0-9]* skipped' | tail -1)"
say "run_all: ${SUITE:-unknown}"
report "- run_all: \`${SUITE:-unknown}\`"
if ! printf '%s' "$SUITE" | grep -q ' 0 failed, 0 skipped'; then
    tail -12 "$LOG.suite"
    say "suite is red — leaving the branch $BRANCH in place for inspection"
    report ""
    report "## Needs a human: red suites"
    sed -n '/failed:/,$p' "$LOG.suite" | head -8 | sed 's/^/- /' >> "$REPORT"
    exit 4
fi

# 9 ----------------------------------------------------------------- publish
if [ "$PUBLISH" != 1 ]; then
    say "skipping publish (--no-publish); tree is committed below"
    git add -A && git commit --quiet -m "release: $VERSION (dry run, not published)" || true
    exit 0
fi

TOKEN="$(cat "$TOKEN_FILE" 2>/dev/null)"
[ -n "$TOKEN" ] || fail "no token in $TOKEN_FILE" 6
REMOTE="https://x-access-token:$TOKEN@github.com/ccrabit/workbuddy2api-hub.git"

git add -A
git commit --quiet -m "release: sync upstream v$VERSION

合并 upstream/main（$UPSTREAM_SHA）并回填 $VERSION 的资产指纹。
Merge upstream v$VERSION ($UPSTREAM_SHA) and backfill the asset fingerprint." \
    || say "nothing to commit (tree already at $VERSION)"

BODY="docs/phase-auto-release-body-$VERSION.md"
{
    printf '# WorkBuddy2API-Hub fnos-%s（飞牛原生 fpk）\n\n' "$VERSION"
    printf '本次发布由自动任务构建：合并 `upstream/main` = `%s`，包版本 `%s`。\n\n' "$UPSTREAM_SHA" "$VERSION"
    printf '| 文件 | 字节数 | sha256 |\n| --- | --- | --- |\n'
    printf '| `WorkBuddy2API-Hub_%s_all.fpk` | `%s` | `%s` |\n\n' "$VERSION" "$SIZE" "$SHA256"
    printf '校验：`sha256sum -c WorkBuddy2API-Hub_%s_all.fpk.sha256`\n\n' "$VERSION"
    printf '## 安装 / 升级\n\n应用中心 → 手动安装 → 选择本 Release 的 `.fpk`（覆盖安装即可，端口仍是 8788）。\n'
    printf '升级前建议备份 `/vol1/@appdata/workbuddy2api/`（至少 `accounts/` 与 `usage/`）。\n\n'
    printf '## 这一版\n\n%s\n\n' "$(git log --oneline "$BASE..$UPSTREAM_SHA" | head -12 | sed 's/^/- /')"
    printf '## 验证\n\n- `run_all --jobs 4`：%s\n- 载荷校验：`verify-fpk.sh` 通过\n- 装机：本机已升级到 `%s`（`/health` 的 `Server` 头已确认）\n- 附件的 sha256 与仓库根 `fnpack.json`、`ccrabit/FnDepot` 源一致\n' "$SUITE" "${DEVICE_VERSION:-$VERSION}"
} > "$BODY"

git add -A && git commit --quiet -m "docs(release): add the fnos-$VERSION release body" || true
git tag -a "fnos-$VERSION" -m "WorkBuddy2API-Hub $VERSION (upstream v$VERSION)" \
    || fail "git tag fnos-$VERSION" 6
git push --quiet "$REMOTE" HEAD:refs/heads/main "refs/tags/fnos-$VERSION" \
    || fail "git push (main + tag)" 6
say "pushed main and fnos-$VERSION"

python3 scripts/gh-release.py release-create "fnos-$VERSION" "$BODY" \
    --name "WorkBuddy2API-Hub fnos-$VERSION" >/dev/null \
    || say "release-create said no (already there?)"
python3 scripts/gh-release.py release-upload "fnos-$VERSION" "$FPK" "$FPK.sha256" >/dev/null \
    || fail "release-upload" 6
python3 scripts/gh-release.py release-get "fnos-$VERSION" > "$LOG_DIR/$RUN_ID.release.json" 2>/dev/null
ASSET_ID="$(python3 - "$LOG_DIR/$RUN_ID.release.json" <<'PY'
import json,sys
try:
    doc = json.load(open(sys.argv[1]))
except Exception:
    raise SystemExit(0)
for a in doc.get("assets", []):
    if a["name"].endswith(".fpk"):
        print(a["id"])
PY
)"
if [ -n "$ASSET_ID" ]; then
    curl -sSL -H "Authorization: Bearer $TOKEN" -H "Accept: application/octet-stream" \
        "https://api.github.com/repos/ccrabit/workbuddy2api-hub/releases/assets/$ASSET_ID" \
        -o "$LOG_DIR/$RUN_ID.asset.fpk" 2>/dev/null
    if cmp -s "$LOG_DIR/$RUN_ID.asset.fpk" "$FPK"; then
        say "release asset is byte-identical to $FPK"
        report "- release asset: byte-identical"
    else
        report "- release asset: **differs** from the local file"
    fi
fi

if [ -d "$FNDEPOT_SRC/.git" ]; then
    ( cd "$FNDEPOT_SRC" && git add -A \
        && git commit --quiet -m "WorkBuddy2API-Hub $VERSION 应用源" \
        && git push --quiet "https://x-access-token:$(cat "$FNDEPOT_TOKEN_FILE")@github.com/ccrabit/FnDepot.git" HEAD:main ) \
        && say "FnDepot source pushed" || say "FnDepot source push failed"
fi

report ""
report "## Result"
report ""
report "Released \`fnos-$VERSION\`: https://github.com/ccrabit/workbuddy2api-hub/releases/tag/fnos-$VERSION"
say "== done: fnos-$VERSION"
exit 0
