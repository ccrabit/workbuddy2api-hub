"""Release engineering pins (M6 F1-F3, phase F namespace, phase G: no CI).

The Dockerfile and compose file are text artifacts nothing else in the suite
executes; these assertions keep the release discipline from silently
disappearing (checksums sidecar, tag namespace vs source version, healthcheck,
PUID/PGID). The version itself is upstream's own number - see
docs/phase-f-version-policy.md - so a release of this fork is tagged
fnos-<source version>.

Phase G deleted every workflow this fork maintained (`sync-upstream.yml`,
`build-fpk.yml`, `release-checksums.yml`, `docker-publish.yml`, `tests.yml`):
there is no CI here any more. A release is built, verified and uploaded from
this machine by `scripts/build-fpk.sh` + `scripts/gh-release.py`, following
`docs/phase-g-local-release.md`. So the discipline is pinned where it now lives
- the local tools and the runbook - and "`.github/workflows/` holds exactly
upstream's `release.yml` and nothing of ours" is itself an assertion. The fork
also keeps upstream's RepoHygieneTests: merge leftovers (conflict markers) must
never reach the tree.

Run with: python _test_release_engineering.py
"""
import hashlib
import os
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKFLOWS = os.path.join(".github", "workflows")
GH_RELEASE = os.path.join("scripts", "gh-release.py")
RUNBOOK = os.path.join("docs", "phase-g-local-release.md")


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as fh:
        return fh.read()


class VersionStringTests(unittest.TestCase):
    def test_source_version_strings_agree(self):
        import re
        src = read("wb_proxy.py")
        overview = re.search(r'"version"\s*:\s*"([^"]+)"', src)
        server = re.search(r'server_version\s*=\s*"wb-proxy/([^"]+)"', src)
        self.assertIsNotNone(overview, "overview version string not found")
        self.assertIsNotNone(server, "server header version string not found")
        self.assertEqual(overview.group(1), server.group(1))


class LocalReleaseTests(unittest.TestCase):
    """Phase G: none of our workflows are left; the release path is local."""

    def test_only_upstreams_release_workflow_is_left(self):
        names = sorted(os.listdir(os.path.join(ROOT, WORKFLOWS)))
        self.assertEqual(
            ["release.yml"], names,
            "our own workflows are gone for good (phase G); upstream's release.yml "
            "is the only file that may stay",
        )
        text = read(WORKFLOWS, "release.yml")
        # Upstream's file answers to upstream's tag namespace, so it cannot fire
        # on a release of this fork: ours are tagged fnos-X.Y.Z.
        self.assertIn('"v*"', text, "upstream's release workflow triggers on v* tags")
        self.assertNotIn(
            "fnos-", text,
            "this is upstream's file unchanged, so it cannot know our fnos- namespace",
        )

    def test_the_release_tag_gate_now_lives_in_the_local_script(self):
        # The deleted tests.yml ran a `version-assert` job: a release tag had to
        # name the source version. The rule is still the contract - it is just
        # carried by the only thing that turns a tag into a package version now.
        text = read("scripts", "build-fpk.sh")
        self.assertIn("head_release_tag", text, "the build script has to read the tag on HEAD")
        self.assertIn(
            r"^fnos-[0-9]+(\.[0-9]+){2,3}$", text,
            "only fnos-X.Y.Z (plus Phase Q's hot-fix fourth number) is a release "
            "of this fork",
        )
        self.assertIn("--print-version", text, "the derived version has to be readable back")
        runbook = read(RUNBOOK)
        self.assertIn("fnos-${VERSION}", runbook, "the runbook has to build the tag from the version")
        self.assertIn("上游最新 release tag 的三段数字", runbook)

    def test_the_checksum_sidecar_is_produced_by_the_local_tool(self):
        # What release-checksums.yml did (hash every asset, publish the list) is
        # now `gh-release.py sha256` writing the .sha256 sidecar beside the
        # package; the runbook redirects it into that file. Executed here: no
        # token, no network.
        payload = b"workbuddy2api release asset\n"
        with tempfile.TemporaryDirectory(prefix="wb-eng-") as tmp:
            path = os.path.join(tmp, "asset.bin")
            with open(path, "wb") as fh:
                fh.write(payload)
            result = subprocess.run(
                [sys.executable, os.path.join(ROOT, GH_RELEASE), "sha256", path],
                capture_output=True, text=True, timeout=120,
            )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(
            "%s  asset.bin" % hashlib.sha256(payload).hexdigest(), result.stdout.strip(),
            "the sidecar line has to be `<sha256>  <basename>` - that is the format "
            "the release carries and the runbook redirects into <fpk>.sha256",
        )
        self.assertIn("gh-release.py sha256", read(RUNBOOK))

    def test_the_release_runbook_is_the_checklist(self):
        runbook = read(RUNBOOK)
        for step in ("python3 tests/run_all.py --jobs 4",
                     "bash scripts/build-fpk.sh",
                     "bash scripts/verify-fpk.sh",
                     "gh-release.py sha256",
                     "gh-release.py release-upload",
                     "gh-release.py tag-create",
                     'git tag -a "${TAG}"'):
            self.assertIn(step, runbook, "the runbook has to keep the step: %s" % step)
        self.assertIn("只有 `release.yml`", runbook)
        self.assertIn("cron:", runbook)


class DockerTests(unittest.TestCase):
    def test_healthcheck_probes_the_health_endpoint(self):
        text = read("Dockerfile")
        self.assertIn("HEALTHCHECK", text)
        self.assertIn("/health", text)

    def test_compose_supports_puid_pgid(self):
        text = read("docker-compose.yml")
        self.assertIn("${PUID:-", text)
        self.assertIn("${PGID:-", text)


class ReadmeTests(unittest.TestCase):
    def test_readme_suite_count_matches_the_tree(self):
        names = [n for n in os.listdir(os.path.join(ROOT, "tests"))
                 if n.startswith("_test_") and n.endswith((".py", ".js"))]
        py = len([n for n in names if n.endswith(".py")])
        js = len([n for n in names if n.endswith(".js")])
        expected = "%d 个套件：%d 个 Python + %d 个 JS" % (len(names), py, js)
        self.assertIn(expected, read("README.md"))


class RepoHygieneTests(unittest.TestCase):
    """解冲突没解干净的残留（冲突标记）不许留在仓库里。

    main 上已经发生过三次：#131 专门清过一次 dashboard 的残留，README 又在
    #243/#245 那批合并里被提交进 12~15 行冲突标记。没有测试盯它的时候，
    Python 文件是直接 SyntaxError，HTML/JS 则是静默坏掉；回滚检查（revert
    guard）还会把「合并时顺手整理掉这些行」算成弄丢 main 的改动（见 #245）。
    """

    MARKER = re.compile(r"^(<{7}|>{7}|\|{7})(\s|$)")

    # 运行时数据与打包产物（.gitignore 里那些）：它们不是源码，不该被扫。
    SKIP_DIRS = (".git", "__pycache__", "node_modules", "accounts", "usage",
                 "logs", "suite-logs", "dist", "python", ".sdk-cache")

    def test_no_conflict_markers_in_the_tree(self):
        offenders = []
        for base, dirs, files in os.walk(ROOT):
            dirs[:] = [d for d in dirs if d not in self.SKIP_DIRS]
            for name in files:
                path = os.path.join(base, name)
                try:
                    if os.path.getsize(path) > 4 * 1024 * 1024:
                        continue
                    with open(path, "rb") as fh:
                        raw = fh.read()
                except OSError:
                    continue
                try:
                    text = raw.decode("utf-8")
                except UnicodeDecodeError:
                    continue                    # 二进制，跳过
                for line in text.splitlines():
                    if self.MARKER.match(line):
                        offenders.append("%s: %s"
                                         % (os.path.relpath(path, ROOT), line[:60]))
                        break
        self.assertEqual(
            offenders, [],
            "冲突标记残留（解冲突没解干净，两边都要留）：\n" + "\n".join(offenders))


if __name__ == "__main__":
    unittest.main()
