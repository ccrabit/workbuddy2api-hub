#!/usr/bin/env python3
"""Publish releases of this repository from this machine, using only the
Python standard library.

Why a script and not `gh`: this NAS cannot reach github.com:443 (git pull/push
over HTTPS hangs), but api.github.com *is* reachable. Every git-level step can
be done locally, so the only thing this machine cannot do with plain git is
write to the Releases API -- that is what this script is for.

Token
-----
Never stored in the repository. Read, in this order:

  1. ``$WB_GH_TOKEN`` (environment variable, wins if set and non-empty)
  2. ``--token-file`` (default ``/root/.gh-token``, mode 600)

The token file may be a bare token, or a ``KEY=value`` line (``KEY=`` is
stripped), or comments/blank lines -- the first usable line wins.

Examples
--------
    python3 scripts/gh-release.py sha256 dist/WorkBuddy2API-Hub_1.6.19_all.fpk
    python3 scripts/gh-release.py release-get fnos-1.6.19
    python3 scripts/gh-release.py release-upload fnos-1.6.19 dist/*.fpk dist/*.sha256
    python3 scripts/gh-release.py release-edit fnos-1.6.19 /tmp/release-body.md
    python3 scripts/gh-release.py tag-create fnos-1.6.19 "$(git rev-parse HEAD)"

Exit codes: 0 ok, 2 usage, 3 not found (HTTP 404), 4 any other failure.
"""

import argparse
import hashlib
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_REPO = "ccrabit/workbuddy2api-hub"
DEFAULT_TOKEN_FILE = "/root/.gh-token"
DEFAULT_API = "https://api.github.com"
DEFAULT_UPLOAD = "https://uploads.github.com"
API_VERSION = "2022-11-28"
USER_AGENT = "workbuddy2api-local-release/1.0"


class Failure(Exception):
    """Anything that should stop the run with a message and a non-zero exit."""

    def __init__(self, message, code=4):
        Exception.__init__(self, message)
        self.code = code


class NotFound(Failure):
    def __init__(self, message):
        Failure.__init__(self, message, code=3)


def read_token(path):
    env = os.environ.get("WB_GH_TOKEN", "").strip()
    if env:
        return env
    if not os.path.isfile(path):
        raise Failure(
            "no token: set $WB_GH_TOKEN or create %s (mode 600) with a GitHub token "
            "that has 'repo' scope" % path
        )
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                line = line.split("=", 1)[1].strip()
            line = line.strip('"').strip("'").strip()
            if line:
                return line
    raise Failure("no token found in %s" % path)


class Client(object):
    def __init__(self, repo, token, api, upload):
        self.repo = repo
        self.token = token
        self.api = api.rstrip("/")
        self.upload = upload.rstrip("/")

    def call(self, method, url, payload=None, content_type="application/json", expect=(200, 201)):
        body = None
        if payload is not None:
            if content_type == "application/json":
                body = json.dumps(payload).encode("utf-8")
            else:
                body = payload
        request = urllib.request.Request(url, data=body, method=method)
        request.add_header("Authorization", "Bearer %s" % self.token)
        request.add_header("Accept", "application/vnd.github+json")
        request.add_header("X-GitHub-Api-Version", API_VERSION)
        request.add_header("User-Agent", USER_AGENT)
        if body is not None:
            request.add_header("Content-Type", content_type)
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                status = response.getcode()
                raw = response.read()
        except urllib.error.HTTPError as error:
            raw = error.read()
            detail = raw.decode("utf-8", "replace").strip()
            if error.code == 404:
                raise NotFound("HTTP 404 from %s %s: %s" % (method, url, detail))
            raise Failure("HTTP %s from %s %s: %s" % (error.code, method, url, detail))
        except urllib.error.URLError as error:
            raise Failure("cannot reach %s (%s)" % (url, error.reason))
        if status not in expect:
            raise Failure("unexpected HTTP %s from %s %s" % (status, method, url))
        if not raw:
            return None
        return json.loads(raw.decode("utf-8"))

    def release_by_tag(self, tag):
        url = "%s/repos/%s/releases/tags/%s" % (self.api, self.repo, urllib.parse.quote(tag))
        return self.call("GET", url)

    def upload_asset(self, release_id, path, clobber=True):
        name = os.path.basename(path)
        existing = None
        release = self.call("GET", "%s/repos/%s/releases/%s" % (self.api, self.repo, release_id))
        for asset in release.get("assets", []):
            if asset.get("name") == name:
                existing = asset
                break
        if existing is not None:
            if not clobber:
                raise Failure(
                    "asset %s already exists on release %s (use --clobber to replace it)"
                    % (name, release_id)
                )
            self.call(
                "DELETE",
                "%s/repos/%s/releases/assets/%s" % (self.api, self.repo, existing["id"]),
                expect=(204,),
            )
            print("  deleted the existing asset %s (id %s)" % (name, existing["id"]))
        with open(path, "rb") as handle:
            data = handle.read()
        size = os.path.getsize(path)
        url = "%s/repos/%s/releases/%s/assets?%s" % (
            self.upload,
            self.repo,
            release_id,
            urllib.parse.urlencode({"name": name}),
        )
        asset = self.call("POST", url, payload=data, content_type="application/octet-stream")
        print(
            "  uploaded %s (%d bytes, sha256 %s)"
            % (name, size, sha256_file(path))
        )
        return asset


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_body(path):
    if path == "-":
        return sys.stdin.read()
    if not os.path.isfile(path):
        raise Failure("no such body file: %s" % path)
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def cmd_sha256(args):
    if not os.path.isfile(args.file):
        raise Failure("no such file: %s" % args.file)
    print("%s  %s" % (sha256_file(args.file), os.path.basename(args.file)))
    return 0


def cmd_release_get(args):
    release = args.client.release_by_tag(args.tag)
    print(json.dumps(release, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


def cmd_release_create(args):
    release = args.client.call(
        "POST",
        "%s/repos/%s/releases" % (args.client.api, args.client.repo),
        {
            "tag_name": args.tag,
            "name": args.name or args.tag,
            "body": read_body(args.bodyfile),
            "draft": bool(args.draft),
            "prerelease": False,
        },
    )
    print("[ok] created release %s (%s)" % (release["tag_name"], release["html_url"]))
    return 0


def cmd_release_upload(args):
    release = args.client.release_by_tag(args.tag)
    release_id = release["id"]
    print("[ok] release %s is id %s" % (args.tag, release_id))
    for path in args.files:
        if not os.path.isfile(path):
            raise Failure("no such file: %s" % path)
        args.client.upload_asset(release_id, path, clobber=not args.no_clobber)
    print("[ok] uploaded %d file(s) to %s" % (len(args.files), args.tag))
    return 0


def cmd_release_edit(args):
    release = args.client.release_by_tag(args.tag)
    payload = {"body": read_body(args.bodyfile)}
    if args.name:
        payload["name"] = args.name
    updated = args.client.call(
        "PATCH",
        "%s/repos/%s/releases/%s" % (args.client.api, args.client.repo, release["id"]),
        payload,
    )
    print("[ok] edited release %s (%s)" % (updated["tag_name"], updated["html_url"]))
    return 0


def cmd_tag_create(args):
    message = args.message or args.tag
    client = args.client
    tag_object = client.call(
        "POST",
        "%s/repos/%s/git/tags" % (client.api, client.repo),
        {
            "tag": args.tag,
            "message": message,
            "object": args.sha,
            "type": "commit",
            "tagger": {
                "name": args.tagger_name,
                "email": args.tagger_email,
                "date": args.date,
            }
            if args.date
            else None,
        },
    )
    if tag_object.get("tagger") is None:
        tag_object.pop("tagger", None)
    ref = "refs/tags/%s" % args.tag
    try:
        client.call(
            "POST",
            "%s/repos/%s/git/refs" % (client.api, client.repo),
            {"ref": ref, "sha": tag_object["sha"]},
        )
        print("[ok] created %s -> %s (tag object %s)" % (ref, args.sha, tag_object["sha"]))
    except Failure as error:
        if not args.force:
            raise Failure(
                "%s already exists (pass --force to re-point it): %s" % (ref, error)
            )
        client.call(
            "PATCH",
            "%s/repos/%s/git/refs/tags/%s" % (client.api, client.repo, args.tag),
            {"sha": tag_object["sha"], "force": True},
        )
        print(
            "[ok] re-pointed %s -> %s (tag object %s)"
            % (ref, args.sha, tag_object["sha"])
        )
    return 0


def build_parser():
    parser = argparse.ArgumentParser(
        prog="gh-release.py",
        description="Publish releases of this repository through the GitHub REST API "
        "(standard library only; api.github.com is reachable from the NAS, github.com:443 is not).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="The token comes from $WB_GH_TOKEN or --token-file (default %s)."
        % DEFAULT_TOKEN_FILE,
    )
    parser.add_argument("--repo", default=os.environ.get("WB_GH_REPO", DEFAULT_REPO),
                        help="owner/name (default %s)" % DEFAULT_REPO)
    parser.add_argument("--token-file", default=DEFAULT_TOKEN_FILE,
                        help="file holding the token (default %s); ignored when $WB_GH_TOKEN is set"
                        % DEFAULT_TOKEN_FILE)
    parser.add_argument("--api", default=DEFAULT_API, help="REST API host (default %s)" % DEFAULT_API)
    parser.add_argument("--upload", default=DEFAULT_UPLOAD,
                        help="asset upload host (default %s)" % DEFAULT_UPLOAD)
    subparsers = parser.add_subparsers(dest="command")

    sha = subparsers.add_parser("sha256", help="print '<sha256>  <basename>' (the .sha256 sidecar format)")
    sha.add_argument("file")
    sha.set_defaults(func=cmd_sha256, needs_token=False)

    get = subparsers.add_parser("release-get", help="print the release for a tag as JSON")
    get.add_argument("tag")
    get.set_defaults(func=cmd_release_get)

    create = subparsers.add_parser("release-create", help="create the release for a tag")
    create.add_argument("tag")
    create.add_argument("bodyfile", help="release body, '-' reads stdin")
    create.add_argument("--name", help="release title (default: the tag)")
    create.add_argument("--draft", action="store_true", help="create it as a draft")
    create.set_defaults(func=cmd_release_create)

    upload = subparsers.add_parser(
        "release-upload", help="upload assets, replacing same-named ones (--clobber semantics)"
    )
    upload.add_argument("tag")
    upload.add_argument("files", nargs="+")
    upload.add_argument("--no-clobber", action="store_true",
                        help="fail instead of replacing an asset that already exists")
    upload.set_defaults(func=cmd_release_upload)

    edit = subparsers.add_parser("release-edit", help="replace the release body (and title)")
    edit.add_argument("tag")
    edit.add_argument("bodyfile", help="new body, '-' reads stdin")
    edit.add_argument("--name", help="also set the release title")
    edit.set_defaults(func=cmd_release_edit)

    tag = subparsers.add_parser("tag-create", help="create an annotated tag without pushing (git data API)")
    tag.add_argument("tag")
    tag.add_argument("sha", help="commit the tag points at (git rev-parse HEAD)")
    tag.add_argument("--message", help="tag message (default: the tag name)")
    tag.add_argument("--force", action="store_true", help="re-point the tag if it already exists")
    tag.add_argument("--date", help="tagger date, ISO 8601 (default: GitHub's clock)")
    tag.add_argument("--tagger-name", default="WorkBuddy2API-Hub release")
    tag.add_argument("--tagger-email", default="release@localhost")
    tag.set_defaults(func=cmd_tag_create)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 2
    if getattr(args, "needs_token", True):
        try:
            args.client = Client(args.repo, read_token(args.token_file), args.api, args.upload)
        except Failure as error:
            sys.stderr.write("error: %s\n" % error)
            return error.code
    try:
        return args.func(args)
    except NotFound as error:
        sys.stderr.write("error: %s\n" % error)
        return error.code
    except Failure as error:
        sys.stderr.write("error: %s\n" % error)
        return error.code
    except KeyboardInterrupt:
        sys.stderr.write("interrupted\n")
        return 130


if __name__ == "__main__":
    sys.exit(main())
