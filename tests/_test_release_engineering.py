"""Release engineering pins (M6 F1-F3, phase F: the fnos- tag namespace).

The workflows, Dockerfile and compose file are text artifacts nothing else in
the suite executes; these assertions keep the release discipline from silently
disappearing (checksums asset, tag namespace vs source version, healthcheck,
PUID/PGID). The version itself is upstream's own number - see
docs/phase-f-version-policy.md - so a release of this fork is tagged
fnos-<source version>.

Run with: python _test_release_engineering.py
"""
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as fh:
        return fh.read()


class VersionStringTests(unittest.TestCase):
    def test_source_version_strings_agree(self):
        src = read("wb_proxy.py")
        overview = re.search(r'"version"\s*:\s*"([^"]+)"', src)
        server = re.search(r'server_version\s*=\s*"wb-proxy/([^"]+)"', src)
        self.assertIsNotNone(overview, "overview version string not found")
        self.assertIsNotNone(server, "server header version string not found")
        self.assertEqual(overview.group(1), server.group(1))


class WorkflowTests(unittest.TestCase):
    def test_tests_workflow_asserts_tag_against_source(self):
        text = read(".github", "workflows", "tests.yml")
        # Releases of this fork are tagged fnos-<source version> (fnos-1.6.19 for
        # source 1.6.19); the historical v<source version>[.<ordinal>] tags stay
        # readable so an old release can be re-checked. The gate body has to
        # accept the first and the second, and reject anything else.
        self.assertIn("version-assert", text)
        self.assertIn("GITHUB_REF_NAME", text)
        self.assertIn("fnos-", text)
        self.assertIn("refs/tags/", text)
        self.assertIn("::error::", text)
        # 触发列表：phase F 裁决 (a)——本仓库的发布 tag 是 fnos-<源码版本>，所以它必须
        # 在 `on.push.tags` 里，否则这道「tag 与源码版本一致」的门对我们真正要发的
        # tag 根本不跑（只由 build-fpk.sh --print-version + build-fpk.yml 的门兜住）。
        # 上游的 v* 保留，历史 release 仍可复检；代价是这一行以后可能与上游冲突，
        # 冲突时保留两边的名字即可。
        self.assertIn('"fnos-*"', text)
        self.assertIn('"v*"', text)
        self.assertIn("server_version", text)
        # The workflow's extraction must see the same two strings the source
        # test pins, otherwise a passing CI would mean nothing.
        self.assertIn('"version"', text)

    def test_release_checksums_workflow_hashes_every_asset(self):
        text = read(".github", "workflows", "release-checksums.yml")
        self.assertIn("types: [published]", text)
        self.assertIn("gh release download", text)
        self.assertIn("sha256sum *", text)
        self.assertIn("gh release upload", text)
        self.assertIn("checksums.txt", text)


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


if __name__ == "__main__":
    unittest.main()
