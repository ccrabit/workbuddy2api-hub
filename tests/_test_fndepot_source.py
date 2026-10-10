#!/usr/bin/env python3
"""Assert the FnDepot source file (repo-root `fnpack.json`) is publishable.

The authority is the FnDepot centre repo's own spec ("外部应用源 V2 编写说明")
and its filter script `scripts/generate_sources.py` (`validate_v2_app` /
`parse_and_fingerprint` / `is_forbidden_identity`). A local copy of that script
is imported by path when it is available, so the strongest check here is not our
reading of the spec but the centre repo's own validator.

Offline and stdlib only: no network, no writes. Nothing here needs the FPK to
exist — `sha256`/`size` are known to be placeholders until the release is cut, so
a zero hash or a zero size is reported as a NOTE, never a failure.

    python3 tests/_test_fndepot_source.py

Point FNDEPOT_GENERATOR at the centre repo's script to validate against a copy
that lives somewhere else.
"""
import importlib.util
import json
import os
import re
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FNPACK = os.path.join(ROOT, "fnpack.json")
MANIFEST = os.path.join(ROOT, "fnos", "manifest")
PRIVILEGE = os.path.join(ROOT, "fnos", "config", "privilege")
ICON = os.path.join(ROOT, "fndepot", "ICON.PNG")

# The centre repo's filter, in the shipped order of preference.
GENERATOR_CANDIDATES = [
    os.environ.get("FNDEPOT_GENERATOR", ""),
    "/tmp/fndepot/generate_sources.py",
    "/tmp/fndepot/scripts/generate_sources.py",
]

EXPECTED_APP = "workbuddy2api"          # == fnos/manifest appname
EXPECTED_DISPLAY = "WorkBuddy2API-Hub"
EXPECTED_VERSION = "1.6.19"             # phase-f-plan §2.1
EXPECTED_URL = ("https://github.com/ccrabit/workbuddy2api-hub/releases/download/"
                "fnos-1.6.19/WorkBuddy2API-Hub_1.6.19_all.fpk")

# The nine fixed categories (spec §4.2) and the allowed platform/arch values.
CATEGORIES = ("影音娱乐", "系统工具", "编程开发", "AI赋能", "生活服务",
              "智能智控", "教育学习", "游戏地带", "硬件驱动")
PLATFORMS = ("all", "x86", "arm")
ARCHS = ("all", "x86", "arm")
SEMVER = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")

PASS = 0
FAIL = 0
SKIP = 0
NOTES = []


def check(label, ok, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
    else:
        FAIL += 1
        print("FAIL %s%s" % (label, ("  <- %s" % (detail,)) if detail else ""))
    return bool(ok)


def eq(label, got, want):
    return check(label, got == want, "got %r, want %r" % (got, want))


def skip(label, reason):
    global SKIP
    SKIP += 1
    print("SKIP %s (%s)" % (label, reason))


def note(label, detail=""):
    NOTES.append(label)
    print("NOTE %s%s" % (label, ("  <- %s" % (detail,)) if detail else ""))


def read_text(path):
    with open(path, "rb") as fh:
        raw = fh.read()
    return raw, raw.decode("utf-8")


def parse_manifest(path):
    """`fnos/manifest` is key = value lines, not JSON."""
    out = {}
    for line in read_text(path)[1].splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        out[key.strip()] = val.strip()
    return out


def is_http_url(value):
    return isinstance(value, str) and value.split("://", 1)[0].lower() in ("http", "https") \
        and "://" in value


def local_path(url):
    """Map a source-relative URL ("./fndepot/ICON.PNG") to a repo path."""
    if not isinstance(url, str) or is_http_url(url):
        return None
    rel = url[2:] if url.startswith("./") else url
    return os.path.join(ROOT, rel)


def png_size(path):
    """(width, height) for a PNG, or None when it is not a PNG."""
    with open(path, "rb") as fh:
        head = fh.read(24)
    if len(head) < 24 or head[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    return struct.unpack(">II", head[16:24])


def load_generator():
    """Import the centre repo's filter script. Returns (module, path) or (None, reason)."""
    for path in GENERATOR_CANDIDATES:
        if not path:
            continue
        if not os.path.isfile(path):
            continue
        # The script exits(1) at import time without a token; it never uses one
        # for the pure validators, so hand it a dummy before importing.
        os.environ.setdefault("GITHUB_TOKEN", "offline-validator")
        spec = importlib.util.spec_from_file_location("fndepot_generate_sources", path)
        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
        except SystemExit as exc:
            return None, "%s raised SystemExit(%s) on import" % (path, exc.code)
        except Exception as exc:  # noqa: BLE001 - report, never crash the suite
            return None, "%s failed to import: %s" % (path, exc)
        for attr in ("validate_v2_app", "parse_and_fingerprint", "is_forbidden_identity"):
            if not callable(getattr(module, attr, None)):
                return None, "%s has no %s()" % (path, attr)
        return module, path
    return None, "no local copy of the centre repo generator"


def main():
    # --- [1] strict JSON and the V2 top level ------------------------------
    if not check("fnpack.json exists at the repo root", os.path.isfile(FNPACK), FNPACK):
        return 1
    raw, text = read_text(FNPACK)
    check("fnpack.json is UTF-8 without BOM", not raw.startswith(b"\xef\xbb\xbf"))
    try:
        data = json.loads(text)
    except ValueError as exc:
        check("fnpack.json parses as strict JSON", False, str(exc))
        return 1
    check("fnpack.json parses as strict JSON", True)
    check("fnpack.json is a JSON object", isinstance(data, dict))

    check("top level has schema_version/source_info/apps",
          all(k in data for k in ("schema_version", "source_info", "apps")),
          "keys=%r" % (sorted(data),))
    extra = sorted(set(data) - {"schema_version", "source_info", "apps"})
    if extra:
        note("top level has non-standard keys (spec ignores them)", "keys=%r" % (extra,))
    check("schema_version is the string \"2\"",
          isinstance(data.get("schema_version"), str) and data["schema_version"] == "2",
          "got %r (%s)" % (data.get("schema_version"), type(data.get("schema_version")).__name__))
    check("source_info is an object", isinstance(data.get("source_info"), dict))
    check("apps is a non-empty object", isinstance(data.get("apps"), dict) and bool(data["apps"]))

    source_info = data.get("source_info") or {}
    apps = data.get("apps") or {}

    # --- [2] source identity ------------------------------------------------
    for key in ("name", "author"):
        value = source_info.get(key)
        check("source_info.%s is a non-empty string" % key,
              isinstance(value, str) and value.strip() != "", "got %r" % (value,))
    for key in ("homepage", "description"):
        if key in source_info:
            check("source_info.%s is a string" % key, isinstance(source_info[key], str))
    if "homepage" in source_info:
        check("source_info.homepage is http(s)", is_http_url(source_info["homepage"]))
    check("source_info.author is not the FnDepot project name",
          str(source_info.get("author", "")).strip().lower() != "fndepot",
          "author=%r" % (source_info.get("author"),))

    # --- [3] the app key must be the FPK appname, character for character ---
    if os.path.isfile(MANIFEST):
        manifest = parse_manifest(MANIFEST)
        manifest_app = manifest.get("appname", "")
        eq("apps key == fnos/manifest appname", sorted(apps), [manifest_app])
        eq("apps key is the expected appname", sorted(apps), [EXPECTED_APP])
        eq("display_name == manifest display_name", apps.get(EXPECTED_APP, {}).get("display_name"),
           manifest.get("display_name", ""))
        eq("service_port == manifest service_port", str(apps.get(EXPECTED_APP, {}).get("service_port", "")),
           manifest.get("service_port", ""))
        check("maintainer == manifest maintainer", apps.get(EXPECTED_APP, {}).get("maintainer") == manifest.get("maintainer"),
              "got %r, want %r" % (apps.get(EXPECTED_APP, {}).get("maintainer"), manifest.get("maintainer")))
        man_ver = manifest.get("version", "")
        if man_ver != EXPECTED_VERSION:
            note("fnos/manifest version != the FnDepot release key (build injects it; not fatal)",
                 "manifest=%r release=%r" % (man_ver, EXPECTED_VERSION))
    else:
        skip("apps key == fnos/manifest appname", "fnos/manifest is missing")
        eq("apps key is the expected appname", sorted(apps), [EXPECTED_APP])

    app = apps.get(EXPECTED_APP)
    if not check("apps.workbuddy2api is an object", isinstance(app, dict)):
        return 1

    # --- [4] merged-required app fields (spec §4.1) -------------------------
    eq("display_name", app.get("display_name"), EXPECTED_DISPLAY)
    desc = app.get("desc")
    check("desc is a non-empty string", isinstance(desc, str) and desc.strip() != "")
    if isinstance(desc, str):
        for word in ("账号池", "网关", "看板"):
            check("desc mentions %s" % word, word in desc)
    platform = app.get("platform")
    check("platform is a list of all/x86/arm", isinstance(platform, list) and platform
          and all(p in PLATFORMS for p in platform), "got %r" % (platform,))
    check("platform contains all (packages.all is the only branch)", "all" in (platform or []))
    categories = app.get("categories")
    check("categories is a list of 1..2 fixed names",
          isinstance(categories, list) and 1 <= len(categories) <= 2
          and all(c in CATEGORIES for c in categories), "got %r" % (categories,))
    eq("primary category first", (categories or [None])[0], "AI赋能")
    eq("run_as is package", app.get("run_as"), "package")
    eq("install_type is '' (storage space)", app.get("install_type"), "")
    check("is_docker is the boolean false", app.get("is_docker") is False,
          "got %r (%s)" % (app.get("is_docker"), type(app.get("is_docker")).__name__))
    eq("service_port is the string \"8788\"", str(app.get("service_port", "")), "8788")
    if os.path.isfile(PRIVILEGE):
        try:
            privilege = json.loads(read_text(PRIVILEGE)[1])
            run_as = (privilege.get("defaults") or {}).get("run-as")
        except ValueError:
            run_as = None
        if run_as is None:
            skip("run_as == fnos/config/privilege defaults.run-as", "privilege unreadable")
        else:
            eq("run_as == fnos/config/privilege defaults.run-as", app.get("run_as"), run_as)
    else:
        skip("run_as == fnos/config/privilege defaults.run-as", "fnos/config/privilege is missing")
    for key in ("maintainer", "distributor"):
        check("%s is a non-empty string" % key,
              isinstance(app.get(key), str) and app[key].strip() != "", "got %r" % (app.get(key),))
        check("%s is not the FnDepot project name" % key,
              str(app.get(key, "")).strip().lower() != "fndepot")
    check("maintainer credits the upstream author", app.get("maintainer") == "ardeyouxipianyi",
          "got %r" % (app.get("maintainer"),))
    check("distributor is us", app.get("distributor") == "ccrabit", "got %r" % (app.get("distributor"),))
    for key in ("maintainer_url", "distributor_url", "bug_report_url"):
        check("%s is an http(s) URL" % key, is_http_url(app.get(key)), "got %r" % (app.get(key),))
    check("bug_report_url points at our issues",
          str(app.get("bug_report_url", "")).endswith("/ccrabit/workbuddy2api-hub/issues"))

    # --- [5] in-repo resources ---------------------------------------------
    icon_url = app.get("icon_url")
    check("icon_url is a URL string", isinstance(icon_url, str) and icon_url.strip() != "",
          "got %r" % (icon_url,))
    check("icon_url is http(s) or ./ relative", is_http_url(icon_url)
          or (isinstance(icon_url, str) and icon_url.startswith("./")))
    icon_rel = local_path(icon_url)
    if icon_rel is None:
        skip("icon_url resolves to a repo file", "absolute icon URL: %r" % (icon_url,))
    else:
        if check("icon_url resolves to a repo file", os.path.isfile(icon_rel), icon_rel):
            size = os.path.getsize(icon_rel)
            check("icon is a real PNG (%d bytes)" % size, png_size(icon_rel) is not None, icon_rel)
            check("icon is under 500KB", size < 500 * 1024, "%d bytes" % size)
            check("fndepot/ICON.PNG is the file icon_url points at",
                  os.path.realpath(icon_rel) == os.path.realpath(ICON))
    readme_url = app.get("readme_url")
    if "readme_url" in app:
        check("readme_url is http(s) or ./ relative", is_http_url(readme_url)
              or (isinstance(readme_url, str) and readme_url.startswith("./")),
              "got %r" % (readme_url,))
        rel = local_path(readme_url)
        if rel is not None:
            check("readme_url resolves to a repo file", os.path.isfile(rel), rel)
    previews = app.get("preview_urls")
    if previews is None:
        note("preview_urls omitted (no real screenshots yet)")
    else:
        check("preview_urls is a list of at most 8 entries",
              isinstance(previews, list) and len(previews) <= 8, "got %r" % (previews,))
        for i, url in enumerate(previews if isinstance(previews, list) else []):
            check("preview_urls[%d] is http(s) or ./ relative" % i,
                  is_http_url(url) or (isinstance(url, str) and url.startswith("./")),
                  "got %r" % (url,))
            rel = local_path(url)
            if rel is not None:
                check("preview_urls[%d] resolves to a repo file" % i, os.path.isfile(rel), rel)

    # --- [6] releases -------------------------------------------------------
    releases = app.get("releases")
    if not check("releases is a non-empty object", isinstance(releases, dict) and bool(releases)):
        return 1
    for version in releases:
        check("release key %r is a comparable SemVer" % version, bool(SEMVER.match(str(version))))
    check("releases has the frozen phase F version key", EXPECTED_VERSION in releases,
          "keys=%r" % (sorted(releases),))
    check("release keys sort like versions", sorted(releases) == sorted(releases, key=lambda v: [int(x) for x in re.findall(r"\d+", v)[:3]]))
    for version, node in releases.items():
        if not check("releases[%r] is an object" % version, isinstance(node, dict)):
            continue
        packages = node.get("packages")
        if not check("releases[%r].packages is an object" % version,
                     isinstance(packages, dict) and bool(packages)):
            continue
        check("releases[%r] uses only all/x86/arm branches" % version,
              all(a in ARCHS for a in packages), "got %r" % (sorted(packages),))
        for arch, pkg in packages.items():
            label = "releases[%r].packages.%s" % (version, arch)
            if not check("%s is an object" % label, isinstance(pkg, dict)):
                continue
            url = pkg.get("download_url")
            check("%s.download_url is an http(s) URL" % label, is_http_url(url), "got %r" % (url,))
            digest = pkg.get("sha256")
            check("%s.sha256 is 64 lowercase hex chars" % label,
                  isinstance(digest, str) and bool(HEX64.match(digest)), "got %r" % (digest,))
            size = pkg.get("size")
            check("%s.size is a non-negative int" % label,
                  isinstance(size, int) and not isinstance(size, bool) and size >= 0,
                  "got %r (%s)" % (size, type(size).__name__))
            if isinstance(digest, str) and set(digest) == {"0"}:
                note("%s.sha256 is still the all-zero placeholder" % label)
            if size == 0:
                note("%s.size is still the 0 placeholder" % label)
            if version == EXPECTED_VERSION and arch == "all":
                eq("%s.download_url is the frozen release asset URL" % label, url, EXPECTED_URL)
        if "updated_at" in node:
            check("releases[%r].updated_at is an ISO 8601 string with offset" % version,
                  isinstance(node.get("updated_at"), str)
                  and bool(re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:[+-]\d{2}:\d{2}|Z)$",
                                    node["updated_at"])))
        if "changelog" in node:
            check("releases[%r].changelog is a non-empty string" % version,
                  isinstance(node.get("changelog"), str) and node["changelog"].strip() != "")

    # --- [7] the centre repo's own validator -------------------------------
    module, where = load_generator()
    if module is None:
        skip("centre repo validate_v2_app()/parse_and_fingerprint()", where)
    else:
        print("using centre repo validator: %s" % where)
        ok, reason = module.validate_v2_app(EXPECTED_APP, app)
        check("centre repo validate_v2_app() accepts the app", ok, reason)
        is_valid, names, sigs, source_ver = module.parse_and_fingerprint(data)
        check("centre repo parse_and_fingerprint() accepts the source", is_valid,
              "names=%r sigs=%r ver=%r" % (names, sigs, source_ver))
        eq("fingerprint source version", source_ver, "v2")
        eq("fingerprint app names", names, {EXPECTED_APP})
        eq("fingerprint app signatures", sigs, {"%s|%s" % (EXPECTED_APP, EXPECTED_VERSION)})
        check("centre repo is_forbidden_identity('fndepot') is True",
              module.is_forbidden_identity("fndepot") is True)
        check("centre repo is_forbidden_identity(' FnDepot ') is True",
              module.is_forbidden_identity(" FnDepot ") is True)
        for who, value in (("source_info.author", source_info.get("author")),
                           ("maintainer", app.get("maintainer")),
                           ("distributor", app.get("distributor"))):
            check("centre repo does not flag %s (%r)" % (who, value),
                  module.is_forbidden_identity(value) is False)
        # The centre repo accepts a *numeric* 2 (it compares str(value) == "2"),
        # but the spec §3.1 fixes the value to the string "2". Keep our rule
        # stricter, and record the difference rather than hiding it.
        probe_valid = module.parse_and_fingerprint(dict(data, schema_version=2))[0]
        note("centre repo accepts numeric schema_version 2 (it compares str(value));"
             " our [1] check is stricter", "numeric probe accepted=%s" % probe_valid)
        check("we still assert the spec's string form", isinstance(data["schema_version"], str)
              and data["schema_version"] == "2")

    # --- [8] optional extra sources ----------------------------------------
    if os.path.isdir(os.path.join(ROOT, "fndepot", "Preview")):
        files = sorted(os.listdir(os.path.join(ROOT, "fndepot", "Preview")))
        note("fndepot/Preview/ exists with %d file(s)" % len(files), ", ".join(files[:8]))

    print("fndepot source: PASS=%d FAIL=%d SKIP=%d NOTES=%d" % (PASS, FAIL, SKIP, len(NOTES)))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
