#!/bin/bash
#
# Build the fnOS package: dist/WorkBuddy2API-Hub_<version>_<platform>.fpk
#
# The file name (and the manifest's display_name) is the product name users see;
# the manifest's appname stays workbuddy2api, because that identifier decides
# /vol1/@appcenter/workbuddy2api, /vol1/@appdata/workbuddy2api and the gateway
# prefix - renaming it would strand every account, usage record and setting the
# device already has.
#
#   VERSION=1.6.10        version to stamp into the manifest
#   PLATFORM=all          platform to stamp into the manifest
#   PACKAGER=<name>       distributor shown in the app store (your GitHub user)
#   PACKAGER_URL=<url>    distributor URL (your fork)
#   PYTHON=python3        interpreter for the payload pre-flight check
#
# Everything here runs on the packaging machine, never on the NAS: the fpk is
# assembled (and its payload checked) here, and only unpacked by appcenter on
# the device.
#
# Version: the newest upstream release tag this tree contains, plus a fourth
# component that counts releases, not commits (1.6.10 -> 1.6.10.1, then
# 1.6.10.2 ...). The fourth component exists because fnOS only offers an
# upgrade when the number grows, while upstream tags a release days after the
# commits that make it - so a build from plain master has to be able to say
# "newer than 1.6.10" without inventing an upstream tag of its own.
#
# A release tag sitting exactly on HEAD outranks all of that: "v1.6.17.1" on
# HEAD IS version 1.6.17.1, whatever else the checkout can or cannot see. The
# derivation below is a guess about intent; a tag is the intent. It also has to
# be environment-independent: a fresh clone of this fork sees only the fork's
# tags, so deriving v1.6.17.1 from them once produced 1.6.10.3 in CI while the
# maintainer's tree (which had fetched upstream's v1.6.17) said 1.6.17.1.
# sync-upstream.yml mirrors upstream's three-component tags to this fork so the
# guess stays right for untagged builds too.
#
# The next release is one more than the newest release tag of the same base
# (see release_tags below), so publishing v1.6.10.1 makes the next build
# 1.6.10.2 - there is no counter to keep in sync by hand.
#
# Work that is not a release yet is built with --alpha and carries an
# -alpha<k> suffix, k counting the commits made since the last release
# (1.6.10.2-alpha1, -alpha2, ...). Those packages are for trying things on the
# device; they are never tagged, and the released version drops the suffix.
#
#   --print-version       print the version this tree would be built as, and exit
#   --alpha               build the process version (1.6.10.2-alpha1) instead
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
FNOS_DIR="${REPO_ROOT}/fnos"
BUILD_DIR="${REPO_ROOT}/build"
DIST_DIR="${REPO_ROOT}/dist"
PAYLOAD_DIR="${BUILD_DIR}/payload"
PKG_DIR="${BUILD_DIR}/pkg"
PYTHON="${PYTHON:-python3}"

# The name users see (fpk file name, manifest display_name, Release title) and
# the identifier the device keys everything off. They are deliberately not the
# same string - see the header.
PRODUCT="WorkBuddy2API-Hub"
APPNAME="$(awk -F'=' '/^appname/ {gsub(/[[:space:]]/, "", $2); print $2; exit}' "${FNOS_DIR}/manifest" 2>/dev/null || true)"
APPNAME="${APPNAME:-workbuddy2api}"

# The pristine upstream project. It is not the distributor of this package -
# whoever builds the fpk is.
UPSTREAM_URL="https://github.com/ardeyouxipianyi/workbuddy2api-hub"

info()  { printf '\033[0;32m==>\033[0m %s\n' "$*"; }
warn()  { printf '\033[0;33mwarn:\033[0m %s\n' "$*" >&2; }
die()   { printf '\033[0;31merror:\033[0m %s\n' "$*" >&2; exit 1; }

human_size() {
    local bytes
    bytes="$(stat -c %s "$1" 2>/dev/null || echo 0)"
    awk -v b="$bytes" 'BEGIN {
        split("B KiB MiB GiB", unit, " ")
        i = 1
        while (b >= 1024 && i < 4) { b /= 1024; i++ }
        printf (i == 1 ? "%d %s" : "%.1f %s"), b, unit[i]
    }'
}

# The tree this runs in may have come from a clone with an unusual umask, and
# a package whose files are not readable cannot start the server on the NAS.
normalise_modes() {
    local dir="$1" file_mode="$2"
    find "$dir" -type d -exec chmod 755 {} +
    find "$dir" -type f -exec chmod "$file_mode" {} +
}

normalise_github_url() {
    local url="$1"
    case "$url" in
        git@github.com:*) url="https://github.com/${url#git@github.com:}" ;;
    esac
    printf '%s' "${url%.git}"
}

owner_of_github_url() {
    local url="$1" rest
    case "$url" in
        *github.com/*) rest="${url#*github.com/}"; printf '%s' "${rest%%/*}" ;;
        *) printf '' ;;
    esac
}

# ---------------------------------------------------------------- version ----

# A release tag of this fork sitting exactly on HEAD ("v1.6.17.1"). When there
# is one it is the answer: the tag is the release intent, and unlike
# upstream_tag() it does not care which remote tags this checkout happens to
# see. Four components, so the -alpha<k> process builds and upstream's own
# tags are both ignored.
head_release_tag() {
    git -C "$REPO_ROOT" tag --points-at HEAD 2>/dev/null \
        | grep -E '^v[0-9]+(\.[0-9]+){3}$' \
        | sort -V \
        | tail -1
}

# The newest upstream release tag this tree contains. Upstream tags a release
# with three components ("v1.6.10"); this fork's releases add a fourth
# ("v1.6.10.3"), and `git describe --abbrev=0` would happily hand one of those
# back as the base, so the list is filtered to exactly three components.
upstream_tag() {
    git -C "$REPO_ROOT" tag --merged HEAD --list 'v*' 2>/dev/null \
        | grep -E '^v[0-9]+(\.[0-9]+){2}$' \
        | sort -V \
        | tail -1
}

# Every release this fork has tagged off that base ("v1.6.10.3"), oldest
# first. The -alpha<k> process builds are not releases and are not listed, and
# neither is a release tag that points at HEAD: a workflow tags the state it
# just merged and then builds that tag, so `v1.6.10.1` sitting on HEAD has to
# stamp 1.6.10.1 - not the release after it.
release_tags() {
    local base="$1" tag head
    head="$(git -C "$REPO_ROOT" rev-parse HEAD 2>/dev/null)" || head=""
    while read -r tag; do
        [ -n "$tag" ] || continue
        if [ "$(git -C "$REPO_ROOT" rev-parse "${tag}^{commit}" 2>/dev/null)" != "$head" ]; then
            printf '%s\n' "$tag"
        fi
    done < <(git -C "$REPO_ROOT" tag --list "v${base}.[0-9]*" 2>/dev/null \
             | grep -E "^v${base}\.[0-9]+$" \
             | sort -V || true)
}

# The fourth component the next release gets: one more than the newest release
# tag of this base, or 1 when nothing has been released off this base yet.
next_release_ordinal() {
    local base="$1" tag newest=0
    for tag in $(release_tags "$base"); do
        [ "${tag##*.}" -gt "$newest" ] && newest="${tag##*.}"
    done
    printf '%s' "$((newest + 1))"
}

# release (the default): 1.6.10.2 - what a tag and a release get. A release tag
#                         on HEAD is taken as-is (v1.6.17.1 -> 1.6.17.1).
# alpha:                  1.6.10.2-alpha3 - a process build for the device,
#                         numbered by the commits made since the last release.
#                         A release tag on HEAD does not change this: an alpha
#                         build stays a guess by construction, and the released
#                         tag is not something to build "again, plus alpha".
derive_version() {
    local mode="${1:-release}" tag base ordinal last ahead head_tag
    head_tag="$(head_release_tag)" || head_tag=""
    if [ -n "$head_tag" ] && [ "$mode" != "alpha" ]; then
        printf '%s' "${head_tag#v}"
        return 0
    fi
    tag="$(upstream_tag)" || tag=""
    if [ -n "$tag" ]; then
        base="${tag#v}"
        ordinal="$(next_release_ordinal "$base")"
        if [ "$mode" = "alpha" ]; then
            last="$(release_tags "$base" | tail -1)"
            [ -n "$last" ] || last="$tag"
            ahead="$(git -C "$REPO_ROOT" rev-list --count "${last}..HEAD" 2>/dev/null)" || ahead=0
            case "$ahead" in ''|*[!0-9]*) ahead=0 ;; esac
            printf '%s.%s-alpha%s' "$base" "$ordinal" "$ahead"
        else
            printf '%s.%s' "$base" "$ordinal"
        fi
        return 0
    fi
    # No tags at all (a shallow or exported tree): fall back to the manifest.
    awk -F'=' '/^version/ {gsub(/[[:space:]]/, "", $2); print $2; exit}' "${FNOS_DIR}/manifest"
}

# ---------------------------------------------------------------- payload ----
# The payload is what appcenter unpacks into TRIM_APPDEST, so it holds the
# server and its licence and nothing else - no tests, no launchers for other
# operating systems, and above all no accounts/ or usage/ directory from
# whatever machine this ran on. The server sits in server/ so that the app
# directory keeps the same shape as the packages fnOS ships itself.
build_payload() {
    rm -rf "$PAYLOAD_DIR"
    mkdir -p "${PAYLOAD_DIR}/server"
    tar -C "$REPO_ROOT" -cf - \
        --exclude='./.git' \
        --exclude='./.github' \
        --exclude='./tests' \
        --exclude='./docs' \
        --exclude='./accounts' \
        --exclude='./usage' \
        --exclude='./dist' \
        --exclude='./build' \
        --exclude='./fnos' \
        --exclude='./scripts' \
        --exclude='./__pycache__' \
        --exclude='./*.md' \
        --exclude='./*.bat' \
        --exclude='./*.command' \
        --exclude='./*.sh' \
        --exclude='./Dockerfile' \
        --exclude='./docker-compose*' \
        --exclude='./.dockerignore' \
        --exclude='./.gitignore' \
        --exclude='./_fixbats.py' \
        . | tar -C "${PAYLOAD_DIR}/server" -xf -

    # The desktop entry appcenter lists for the app comes from ui/config *inside
    # the payload*; a ui/ directory at the fpk root is not read (an app packaged
    # with only the root copy installs fine but never gets an "open" entry - see
    # fnos/README.md). config/ travels along for the same reason fnpack puts it
    # there. ui/images/{64,256}.png is what ui/config's "images/{0}.png" resolves
    # against, so the names and the pattern have to stay in step.
    mkdir -p "${PAYLOAD_DIR}/ui/images" "${PAYLOAD_DIR}/config"
    cp "${FNOS_DIR}/ui/config" "${PAYLOAD_DIR}/ui/config"
    cp "${FNOS_DIR}/ICON.PNG" "${PAYLOAD_DIR}/ui/images/64.png"
    cp "${FNOS_DIR}/ICON_256.PNG" "${PAYLOAD_DIR}/ui/images/256.png"
    cp "${FNOS_DIR}"/config/* "${PAYLOAD_DIR}/config/"

    normalise_modes "$PAYLOAD_DIR" 644

    # Every module the server imports at runtime, plus the entry point, the
    # dashboard and the licence. A new upstream module that this list has not
    # caught up with is a package that starts and then dies on ImportError, so
    # the list is asserted rather than trusted to the root tar.
    local required
    for required in wb_proxy.py wb_export.py wb_accounts.py dashboard.html LICENSE \
                    wb_pricing.py wb_atrest.py wb_modelsdev.py wb_prompt.py \
                    wb_ipintel.py wb_probes.py wb_catalog.py wb_fingerprint.py \
                    wb_identity.py wb_webagent.py wb_webtools.py \
                    wb_scheduler.py wb_settings.py wb_tasks.py; do
        [ -f "${PAYLOAD_DIR}/server/${required}" ] \
            || die "payload is missing server/${required} - did upstream rename it?"
    done
    [ -f "${PAYLOAD_DIR}/server/pricing/pricing.json" ] \
        || die "payload is missing server/pricing/ - the pricing store ships with the server"
    local forbidden
    for forbidden in accounts usage tests docs; do
        if [ -e "${PAYLOAD_DIR}/server/${forbidden}" ]; then
            die "payload must not contain ${forbidden}/ (credentials, or machine-only material)"
        fi
    done
    return 0
}

check_payload_python() {
    command -v "$PYTHON" >/dev/null 2>&1 || { warn "no ${PYTHON}: skipping the payload syntax check"; return 0; }
    "$PYTHON" - "$PAYLOAD_DIR" <<'PY' || die "the payload does not parse - refusing to package it"
import ast
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
failures = []
files = sorted(root.rglob("*.py"))
for path in files:
    try:
        ast.parse(path.read_text(encoding="utf-8", errors="replace"), filename=str(path))
    except SyntaxError as exc:
        failures.append("%s: %s" % (path.relative_to(root), exc))
if failures:
    print("\n".join(failures), file=sys.stderr)
    raise SystemExit(1)
print("    %d python files parse" % len(files))
PY
}

# ------------------------------------------------------------------ stage ----
# Pack a directory so the members sit at the archive root without a "./" prefix.
# appcenter looks for exactly "cmd/main" inside the fpk; an archive whose members
# are "./cmd/main" is rejected as incomplete:
#
#   Unable to install workbuddy2api
#   Incomplete package: /vol1/@appcenter/cmd/main is missing
#
# `tar -C dir -czf out .` (and `tar -czf out ./*`) both produce the "./" form,
# and `find -printf '%P\0'` is the way to get the bare names - including any
# dotfiles, which a "./*" glob would drop.
pack_dir() {
    local src="$1" out="$2" list
    [ -d "$src" ] || die "cannot pack ${src}: not a directory"
    mkdir -p "$BUILD_DIR"
    list="$(mktemp "${BUILD_DIR}/members.XXXXXX")"
    ( cd "$src" && find . -mindepth 1 -maxdepth 1 -printf '%P\0' ) > "$list"
    [ -s "$list" ] || { rm -f "$list"; die "cannot pack ${src}: it is empty"; }
    ( cd "$src" && tar --null -T "$list" -czf "$out" )
    rm -f "$list"
}

build_app_tgz() {
    rm -f "${PKG_DIR}/app.tgz"
    # app.tgz unpacks into TRIM_APPDEST, so its contents sit at the top level.
    pack_dir "$PAYLOAD_DIR" "${PKG_DIR}/app.tgz"
}

stage_package() {
    rm -rf "$PKG_DIR"
    mkdir -p "$PKG_DIR/cmd"

    cp "${FNOS_DIR}"/cmd/* "$PKG_DIR/cmd/"
    cp -a "${FNOS_DIR}/config" "$PKG_DIR/"
    cp -a "${FNOS_DIR}/wizard" "$PKG_DIR/"
    cp "${FNOS_DIR}"/*.sc "$PKG_DIR/"
    cp "${FNOS_DIR}/ICON.PNG" "${FNOS_DIR}/ICON_256.PNG" "$PKG_DIR/"
    cp -a "${FNOS_DIR}/ui" "$PKG_DIR/"
    # The desktop icon is the same artwork at the other size; generating it
    # here keeps one copy of each bitmap in the repository. The directory has
    # to be made first: nothing in fnos/ui/images is tracked, so a fresh clone
    # has no such directory and the copies below would fail (which is exactly
    # what happened in CI the first time it ran).
    mkdir -p "${PKG_DIR}/ui/images"
    cp "${FNOS_DIR}/ICON.PNG" "${PKG_DIR}/ui/images/64.png"
    cp "${FNOS_DIR}/ICON_256.PNG" "${PKG_DIR}/ui/images/256.png"
    normalise_modes "$PKG_DIR" 644
    # appcenter runs these directly, so they keep the executable bit.
    chmod 755 "${PKG_DIR}"/cmd/*
}

write_manifest() {
    local version="$1" platform="$2" packager="$3" packager_url="$4" checksum="$5"
    sed -e "s|^version[[:space:]]*=.*|version         = ${version}|" \
        -e "s|^platform[[:space:]]*=.*|platform        = ${platform}|" \
        -e "s|^distributor[[:space:]]*=.*|distributor     = ${packager}|" \
        -e "s|^distributor_url[[:space:]]*=.*|distributor_url = ${packager_url}|" \
        -e "s|^checksum[[:space:]]*=.*|checksum        = ${checksum}|" \
        "${FNOS_DIR}/manifest" > "${PKG_DIR}/manifest"

    if grep -q '__[A-Z_]*__' "${PKG_DIR}/manifest"; then
        die "manifest still contains placeholders: $(grep -o '__[A-Z_]*__' "${PKG_DIR}/manifest" | sort -u | tr '\n' ' ')"
    fi
}

validate_package() {
    local f entry
    for entry in app.tgz manifest cmd/main cmd/install_init cmd/install_callback \
                 cmd/upgrade_init cmd/upgrade_callback cmd/uninstall_init cmd/uninstall_callback \
                 cmd/config_init cmd/config_callback config/privilege config/resource \
                 ui/config ui/images/64.png ui/images/256.png \
                 ICON.PNG ICON_256.PNG wizard/uninstall WorkBuddy2API.sc; do
        [ -e "${PKG_DIR}/${entry}" ] || die "package is incomplete: ${entry} is missing"
    done

    # cmd/main starts the server from <TRIM_APPDEST>/server, and the desktop
    # entry plus the privilege/resource pair are read from the payload too.
    # (The listing goes to a file: `grep -q` in a pipeline would trip
    # `set -o pipefail` by exiting before tar has finished writing.)
    tar -tzf "${PKG_DIR}/app.tgz" > "${BUILD_DIR}/app-contents.txt"
    for entry in server/wb_proxy.py ui/config ui/images/64.png ui/images/256.png \
                 config/privilege config/resource; do
        grep -Fxq "$entry" "${BUILD_DIR}/app-contents.txt" \
            || die "app.tgz does not contain ${entry}"
    done

    # The desktop entry has to reach the app one way or the other: either
    # through the port it names (an "url" entry) or through the gateway socket
    # (an "iframe" entry, which carries no port at all). A port that is named
    # must be the manifest's, or the entry opens something nobody listens on.
    local manifest_port ui_port sc_port
    manifest_port="$(awk -F'=' '/^service_port/ {gsub(/[[:space:]]/, "", $2); print $2}' "${PKG_DIR}/manifest")"
    ui_port="$(awk 'match($0, /"port"[[:space:]]*:[[:space:]]*"[0-9]+"/) {
        s = substr($0, RSTART, RLENGTH); gsub(/[^0-9]/, "", s); print s; exit
    }' "${PKG_DIR}/ui/config")"
    sc_port="$(sed -n 's/.*src\.ports="\([0-9][0-9]*\)\/tcp".*/\1/p' "${PKG_DIR}/WorkBuddy2API.sc")"
    [ -n "$manifest_port" ] || die "manifest has no service_port"
    if [ -n "$ui_port" ]; then
        [ "$manifest_port" = "$ui_port" ] || die "port mismatch: manifest ${manifest_port} vs ui/config ${ui_port}"
    else
        grep -q '"gatewaySocket"' "${PKG_DIR}/ui/config" \
            || die "ui/config is neither an url entry with a port nor an iframe entry with a gateway socket"
    fi
    [ "$manifest_port" = "$sc_port" ] || die "port mismatch: manifest ${manifest_port} vs WorkBuddy2API.sc ${sc_port}"

    local checksum_declared checksum_actual
    checksum_declared="$(awk -F'=' '/^checksum/ {gsub(/[[:space:]]/, "", $2); print $2}' "${PKG_DIR}/manifest")"
    checksum_actual="$(md5sum "${PKG_DIR}/app.tgz" | cut -d' ' -f1)"
    [ "$checksum_declared" = "$checksum_actual" ] || die "checksum mismatch in manifest"
    echo "    port ${manifest_port}, checksum ${checksum_actual}"

    # The name the app store shows has to be the product name, and the
    # identifier it installs under has to stay the appname - the package must
    # never be renamed into a different data directory by accident.
    local display appname_declared
    display="$(awk -F'=' '/^display_name/ {sub(/^[^=]*=[[:space:]]*/, ""); print; exit}' "${PKG_DIR}/manifest")"
    appname_declared="$(awk -F'=' '/^appname/ {gsub(/[[:space:]]/, "", $2); print $2; exit}' "${PKG_DIR}/manifest")"
    [ "$display" = "$PRODUCT" ] || die "manifest display_name is '${display}', expected '${PRODUCT}'"
    [ "$appname_declared" = "$APPNAME" ] || die "manifest appname is '${appname_declared}', expected '${APPNAME}'"
    grep -q "\"title\": \"${PRODUCT}\"" "${PKG_DIR}/ui/config" \
        || die "ui/config title is not '${PRODUCT}' - the App Center entry would show the old name"
}

# The member names inside the finished archive are what appcenter resolves
# against, so they are checked there and not only on the staging directory.
validate_fpk_archive() {
    local fpk="$1" listing="${BUILD_DIR}/fpk-contents.txt" entry
    tar -tzf "$fpk" > "$listing"
    for entry in app.tgz manifest cmd/main cmd/install_callback config/privilege; do
        grep -Fxq "$entry" "$listing" || die "the fpk has no ${entry} entry"
    done
    if grep -q '^\./' "$listing"; then
        die "the fpk carries './'-prefixed members (first: $(grep -m1 '^\./' "$listing")) - appcenter looks for cmd/main and would call the package incomplete"
    fi
}

# -------------------------------------------------------------------- main ---
MODE="release"
PRINT_VERSION=""
while [ $# -gt 0 ]; do
    case "$1" in
        --print-version) PRINT_VERSION=1 ;;
        --alpha) MODE="alpha" ;;
        *) die "unknown argument: $1 (try --print-version or --alpha)" ;;
    esac
    shift
done

# Asked for the version only? Answer that and touch nothing else - the sync
# workflow tags a release with exactly this number.
if [ -n "$PRINT_VERSION" ]; then
    derive_version "$MODE"; echo; exit 0
fi

[ -f "${FNOS_DIR}/manifest" ] || die "fnos/manifest not found - run this from the repository"
[ -d "${FNOS_DIR}/cmd" ] || die "fnos/cmd not found"

VERSION="${VERSION:-$(derive_version "$MODE")}"
[ -n "$VERSION" ] || die "cannot determine a version; pass VERSION=x.y.z"
PLATFORM="${PLATFORM:-$(awk -F'=' '/^platform/ {gsub(/[[:space:]]/, "", $2); print $2; exit}' "${FNOS_DIR}/manifest")}"
PLATFORM="${PLATFORM:-all}"

ORIGIN_URL=""
if ORIGIN_URL="$(git -C "$REPO_ROOT" config --get remote.origin.url 2>/dev/null)"; then
    [ -n "$ORIGIN_URL" ] && ORIGIN_URL="$(normalise_github_url "$ORIGIN_URL")"
fi
PACKAGER="${PACKAGER:-$(owner_of_github_url "${ORIGIN_URL}")}"
PACKAGER_URL="${PACKAGER_URL:-${ORIGIN_URL}}"

if [ -z "$PACKAGER" ] || [ -z "$PACKAGER_URL" ]; then
    die "cannot tell who is distributing this package. Pass PACKAGER=<github user> and PACKAGER_URL=<fork url> (or point 'origin' at your fork)."
fi
if [ "$PACKAGER_URL" = "$UPSTREAM_URL" ]; then
    die "origin is still the upstream repository, so 'distributor' would name the wrong person. Pass PACKAGER=<github user> PACKAGER_URL=<your fork> - the release workflow does this for you."
fi

info "building ${PRODUCT} (appname ${APPNAME}) ${VERSION} (${PLATFORM}) for ${PACKAGER}"
mkdir -p "$BUILD_DIR" "$DIST_DIR"

info "collecting the payload"
build_payload
info "checking the payload"
check_payload_python

info "staging the package"
stage_package
build_app_tgz
CHECKSUM="$(md5sum "${PKG_DIR}/app.tgz" | cut -d' ' -f1)"
write_manifest "$VERSION" "$PLATFORM" "$PACKAGER" "$PACKAGER_URL" "$CHECKSUM"
info "validating the package"
validate_package

FPK_NAME="${PRODUCT}_${VERSION}_${PLATFORM}.fpk"
FPK_PATH="${DIST_DIR}/${FPK_NAME}"
rm -f "$FPK_PATH"
# Same shape as the packages appcenter ships: the fpk is a tar.gz whose root
# holds manifest, app.tgz, cmd/, config/, ui/ and the icons.
pack_dir "$PKG_DIR" "$FPK_PATH"
validate_fpk_archive "$FPK_PATH"
( cd "$DIST_DIR" && sha256sum "$FPK_NAME" > "${FPK_NAME}.sha256" )

info "built dist/${FPK_NAME} ($(human_size "$FPK_PATH"))"
echo
echo "  product    : ${PRODUCT}"
echo "  appname    : ${APPNAME}   (unchanged: owns the data directory and gateway prefix)"
echo "  version    : ${VERSION}"
echo "  platform   : ${PLATFORM}"
echo "  distributor: ${PACKAGER} <${PACKAGER_URL}>"
echo "  payload    : $(human_size "${PKG_DIR}/app.tgz") in app.tgz"
echo "  next       : bash scripts/verify-fpk.sh dist/${FPK_NAME}"
