#!/usr/bin/env python3
"""The unattended sync job (scripts/auto-sync-upstream.sh) is a promise: it can
publish a release and restart the service on this box without anyone watching.

That promise only holds if the script keeps doing the boring things in the right
order, so the assertions here are about *shape and order*, not about running it
(a run would merge upstream and restart the gateway):

  * it must serialise itself (flock) — two overlapping runs would fight over the
    same branch and the same tag;
  * it must stop at a merge conflict instead of guessing (exit 3);
  * it must gate publishing on a fully green suite, and a suite that silently
    skipped the JS half must not count as green;
  * it must never leave the gateway stopped: install → health check → rollback
    on failure, and the rollback path must start the service again;
  * the mechanical fixups must be idempotent and must keep the payload guard
    lists in sync with the tree.

Run with: python3 tests/_test_auto_sync.py
"""
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "scripts", "auto-sync-upstream.sh")
FIXUPS = os.path.join(ROOT, "scripts", "auto_sync_fixups.py")


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def check(name, ok, detail=""):
    print(("PASS" if ok else "FAIL") + " " + name + ((" — " + detail) if detail else ""))
    if not ok:
        check.failed += 1


check.failed = 0


def main():
    src = read(SCRIPT)

    check("the script exists and is executable", os.access(SCRIPT, os.X_OK))
    check("it takes its own lock", "flock -n 9" in src)
    check("it fetches upstream tags", "git fetch --quiet upstream --tags" in src)
    check("it derives the version from the newest upstream tag",
          "--sort=-v:refname" in src and "sed 's/^v//'" in src)
    check("it recognises an already-released version and exits",
          "already contains upstream/main" in src)
    check("it merges with --no-commit so a conflict can be inspected",
          "git merge --no-commit --no-ff" in src)
    check("a conflict aborts the merge and exits 3", "git merge --abort" in src and
          'report "## Needs a human: merge conflicts"' in src)
    check("it verifies the package before publishing", "scripts/verify-fpk.sh" in src)
    check("it writes the sha256 sidecar", 'gh-release.py sha256' in src)
    check("the suite gate rejects skipped suites",
          " 0 failed, 0 skipped" in src)
    check("missing node is fatal, not a silent skip",
          "node is not on PATH" in src)
    check("it installs before the suite runs (the doc gate reads the box version)",
          src.index("install_package()") < src.index("run_all.py"))
    check("the installer waits for a version-stamped /health",
          "wait_health()" in src and "wb-proxy/$want" in src)
    check("a failed health check rolls back", "rolling back" in src)
    check("the rollback starts the service again",
          src.count('"$APPDIR/cmd/main" start') >= 2)
    check("it restores the payload from a backup tarball", "payload.tar" in src)
    check("it publishes main and the tag together",
          "refs/heads/main" in src and 'refs/tags/fnos-$VERSION' in src)
    check("it pushes the FnDepot source separately (classic token)",
          "FnDepot.git" in src and "FNDEPOT_TOKEN_FILE" in src)
    check("it writes a per-run report", "REPORT=" in src and "logs/auto-sync" in src)

    # --- the mechanical fixups -------------------------------------------
    import json
    with open(os.path.join(ROOT, "fnpack.json"), encoding="utf-8") as fh:
        released = sorted(json.load(fh)["apps"]["workbuddy2api"]["releases"])[-1]
    out = subprocess.run([sys.executable, FIXUPS, "--version", released,
                          "--base", "HEAD", "--upstream", "HEAD", "--dry-run"],
                         cwd=ROOT, capture_output=True, text=True)
    check("fixups run in dry-run mode", out.returncode == 0, out.stderr.strip()[:120])
    check("fixups recompute the suite count from the tree",
          "个套件：" in out.stdout)
    check("fixups leave an up-to-date tree alone (idempotent)",
          "0 file(s) would change" in out.stdout, out.stdout.strip()[-80:])

    # the suite count the fixups would write must match the tree right now
    names = [n for n in os.listdir(os.path.join(ROOT, "tests"))
             if n.startswith("_test_") and n.endswith((".py", ".js"))]
    py = sum(1 for n in names if n.endswith(".py"))
    expected = "%d 个套件：%d 个 Python + %d 个 JS" % (len(names), py, len(names) - py)
    check("README carries the current suite count", expected in read(os.path.join(ROOT, "README.md")),
          expected)

    # guard lists must cover every top-level module the server imports
    # the guard list is a curated subset, but it must cover everything the entry
    # points import: a missing module is an ImportError on the appliance
    import re
    guards = read(os.path.join(ROOT, "scripts", "build-fpk.sh"))
    verify = read(os.path.join(ROOT, "tests", "_test_phase_e_verify.py"))
    imported = set()
    for entry in ("wb_proxy.py", "wb_scheduler.py", "wb_update_request.py"):
        for line in read(os.path.join(ROOT, entry)).splitlines():
            m = re.match(r"(?:import|from)\s+(wb_[a-z_]+)", line)
            if m:
                imported.add(m.group(1) + ".py")
    missing = sorted(m for m in imported if m not in guards)
    check("every module the entry points import is in the guard list", not missing,
          ", ".join(missing))
    check("PKG_MODULES covers the same imports",
          not sorted(m for m in imported if m not in verify))
    check("PKG_MODULES lists wb_proxy.py and friends", "wb_proxy.py" in verify)

    print()
    if check.failed:
        print("%d check(s) failed" % check.failed)
        return 1
    print("auto-sync suite ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
