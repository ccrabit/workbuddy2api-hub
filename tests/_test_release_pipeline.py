"""The release pipeline has to give one commit one version, everywhere.

Three failures motivated this file, and all of them were silent until a package
or a run reached someone:

* v1.6.17.1 built a package called 1.6.10.3. The version was derived from
  "the newest three-part tag this checkout can see", and a fresh CI checkout
  of the fork only saw the fork's own tags - upstream's v1.6.17 had never
  been mirrored. The tag on HEAD is the release intent, so it has to decide
  the version no matter which tags the environment can see. Two environments
  are covered: the mixed tag set CI had (upstream tags up to v1.6.10, the
  release tag on HEAD) and a depth-1 clone that sees the release tag alone.
* the sync workflow mirrored upstream's newest tag only while it was cutting
  a release, so the fork's tags could lag behind and every untagged build
  kept guessing from whatever was visible.
* the conflict path relied on the repository's issue tracker, and Issues were
  switched off, so `gh issue create` failed with "Resource not accessible by
  integration (createIssue)" and a conflict showed up as a red run with no
  explanation anywhere.

The behavioural gate copies the tree into a throwaway git repository, tags
HEAD and then deletes its three-part tags, which is what CI's checkout looks
like: it needs the real script but not the real history. It skips (never
fails) where bash or git is missing, so the Windows runners stay useful; the
static gates read the workflows and always run. Point
WB_RELEASE_PIPELINE_ROOT at another checkout to check that tree instead - that
is also how the gate was shown to go red before the scripts were fixed.
"""

import os
import pathlib
import re
import shutil
import subprocess
import tempfile
import unittest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ROOT = os.path.dirname(TESTS_DIR)
BUILD_WORKFLOW = os.path.join(".github", "workflows", "build-fpk.yml")
SYNC_WORKFLOW = os.path.join(".github", "workflows", "sync-upstream.yml")
THREE_PART_TAG = re.compile(r"^v[0-9]+(\.[0-9]+){2}$")
ANY_VERSION = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(\.[0-9]+)?(-alpha[0-9]+)?$")


def repository_root():
    return os.path.abspath(os.environ.get("WB_RELEASE_PIPELINE_ROOT") or DEFAULT_ROOT)


def read_text(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


class VersionDerivationTests(unittest.TestCase):
    """The script, exercised the way CI runs it."""

    def setUp(self):
        self.root = repository_root()
        self.bash = shutil.which("bash")
        self.git = shutil.which("git")
        if not self.bash or not self.git:
            self.skipTest("needs bash and git on PATH")
        script = os.path.join(self.root, "scripts", "build-fpk.sh")
        if not os.path.isfile(script):
            self.skipTest("no scripts/build-fpk.sh under %s" % self.root)
        self.tmp = tempfile.mkdtemp(prefix="wb-release-pipeline-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        # A copy of the working tree, not `git clone`: an uncommitted fix has to
        # be visible to this gate, and a fresh one-commit repository is all the
        # script needs to be asked for a version.
        self.work = os.path.join(self.tmp, "work")
        shutil.copytree(
            self.root, self.work,
            ignore=shutil.ignore_patterns(".git", "dist", "build", "__pycache__", "*.pyc"),
        )
        self.git_at(self.work, "init", "--quiet")
        # Annotated tags need an identity, and a CI runner or a fresh box may
        # have no global one; keep it inside the throwaway repository.
        self.git_at(self.work, "config", "user.email", "release-pipeline@example.invalid")
        self.git_at(self.work, "config", "user.name", "release pipeline check")
        self.git_at(self.work, "add", "-A")
        self.git_at(self.work, "commit", "--quiet", "-m", "release pipeline fixture")

    def git_at(self, cwd, *args):
        result = subprocess.run([self.git, *args], cwd=cwd, capture_output=True, text=True, timeout=300)
        self.assertEqual(0, result.returncode, "git %s failed: %s" % (" ".join(args), result.stderr))
        return result.stdout

    def script(self, *args):
        return self.script_at(self.work, *args)

    def script_at(self, cwd, *args):
        return subprocess.run(
            [self.bash, os.path.join("scripts", "build-fpk.sh"), *args],
            cwd=cwd, capture_output=True, text=True, timeout=180,
        )

    def drop_three_part_tags(self):
        for tag in self.git_at(self.work, "tag", "--list", "v*").split():
            if THREE_PART_TAG.match(tag):
                self.git_at(self.work, "tag", "-d", tag)

    def test_a_release_tag_on_head_decides_the_version(self):
        self.git_at(self.work, "tag", "-a", "v9.9.9.7", "-m", "synthetic release tag")
        # A fresh checkout of the fork sees the fork's own tags only. That is how
        # v1.6.17.1 built as 1.6.10.3: upstream's v1.6.17 was not visible here.
        self.drop_three_part_tags()
        result = self.script("--print-version")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(
            "9.9.9.7", result.stdout.strip(),
            "a four-part release tag on HEAD is the version, whatever tags the checkout can see",
        )

    def test_the_ci_tag_environment_still_uses_the_release_tag(self):
        # The tag set a CI checkout of this fork actually had when v1.6.17.1
        # built a package called 1.6.10.3: upstream's releases up to v1.6.10 had
        # been mirrored (plus this fork's two ordinal tags on top of it),
        # upstream's newer tags had never been pushed here, and the release tag
        # sat on HEAD. Deriving from what is visible yielded v1.6.10 with ordinal
        # 3 - the version asserted below is the one the CI log printed.
        for tag in ("v1.6.10", "v1.6.10.1", "v1.6.10.2"):
            message = "upstream %s" % tag
            self.git_at(self.work, "commit", "--quiet", "--allow-empty", "-m", message)
            self.git_at(self.work, "tag", "-a", tag, "-m", message)
        self.git_at(self.work, "commit", "--quiet", "--allow-empty", "-m", "our release commit")
        self.git_at(self.work, "tag", "-a", "v1.6.17.1", "-m", "v1.6.17.1")
        visible = sorted(self.git_at(self.work, "tag", "--list").split())
        self.assertEqual(
            ["v1.6.10", "v1.6.10.1", "v1.6.10.2", "v1.6.17.1"], visible,
            "the fixture has to reproduce the tag set CI saw, or it proves nothing",
        )
        result = self.script("--print-version")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(
            "1.6.17.1", result.stdout.strip(),
            "the pushed release tag decides the version; the visible upstream tags gave 1.6.10.3",
        )

    def test_a_shallow_clone_of_the_release_tag_reports_that_tag(self):
        # `git clone --depth 1 --branch v1.6.17.1` is what a shallow checkout of
        # the release looks like: one tag, no history, nothing to derive from.
        # The old script fell back to fnos/manifest there and answered 1.6.10 for
        # a tag called v1.6.17.1.
        self.git_at(self.work, "tag", "-a", "v1.6.17.1", "-m", "v1.6.17.1")
        shallow = os.path.join(self.tmp, "shallow")
        # A file:// URL, not a bare path: `--depth` is only honoured over a URL.
        # Built with pathlib because "file://" + "C:\\Users\\..." is not one
        # (git answers "fatal: no path specified"), and the Windows runner has
        # Git for Windows' bash, so this test does run there.
        source = pathlib.Path(self.work).resolve().as_uri()
        self.git_at(
            self.tmp, "clone", "--quiet", "--depth", "1", "--branch", "v1.6.17.1",
            source, shallow,
        )
        visible = sorted(self.git_at(shallow, "tag", "--list").split())
        self.assertEqual(
            ["v1.6.17.1"], visible,
            "a depth-1 clone has to carry the release tag and nothing else, or this gate is not the shallow case",
        )
        result = self.script_at(shallow, "--print-version")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(
            "1.6.17.1", result.stdout.strip(),
            "a checkout that can see only the release tag still has to report that tag",
        )

    def test_alpha_builds_still_report_a_version_with_a_release_tag_on_head(self):
        self.git_at(self.work, "tag", "-a", "v9.9.9.7", "-m", "synthetic release tag")
        result = self.script("--print-version", "--alpha")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertRegex(result.stdout.strip(), ANY_VERSION)

    def test_a_tag_free_checkout_still_reports_a_version(self):
        for tag in self.git_at(self.work, "tag", "--list").split():
            self.git_at(self.work, "tag", "-d", tag)
        result = self.script("--print-version")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertRegex(result.stdout.strip(), ANY_VERSION)


class ReleaseWorkflowTests(unittest.TestCase):
    """The workflows that carry the version from tag to package."""

    def setUp(self):
        self.root = repository_root()

    def workflow(self, relative):
        path = os.path.join(self.root, relative)
        self.assertTrue(os.path.isfile(path), "%s is missing" % relative)
        return read_text(path)

    def test_the_build_workflow_pins_the_tag_version_and_checks_it(self):
        text = self.workflow(BUILD_WORKFLOW)
        self.assertIn(
            "TAG_REF: ${{", text,
            "the build workflow has to notice the pushed tag instead of letting the script guess",
        )
        self.assertIn(
            "${TAG_REF#v}", text,
            "the tag has to lose its leading v before it can be a package version",
        )
        self.assertRegex(
            text, r"(?m)^\s*export VERSION=",
            "the tag version has to reach the script as VERSION",
        )
        self.assertIn(
            "--print-version", text,
            "the build workflow has to read the derived version back so it can compare",
        )
        self.assertIn("::error::", text, "a version mismatch has to be reported as an error annotation")
        self.assertRegex(text, r"(?m)^\s*exit 1\s*$", "a version mismatch has to fail the job")

    def test_the_sync_workflow_mirrors_upstream_tags(self):
        text = self.workflow(SYNC_WORKFLOW)
        lowered = text.lower()
        self.assertIn(
            "mirror upstream tags", lowered,
            "the sync workflow has to say that it mirrors upstream tags - the version scheme depends on it",
        )
        self.assertRegex(
            text, r"for upstream_tag in ",
            "the sync workflow has to mirror every upstream release tag, not only the newest one",
        )
        self.assertRegex(
            text, r"git push origin \"refs/tags/\$\{upstream_tag\}\"",
            "the sync workflow has to push upstream's tags to origin, not just cut its own release tag",
        )
        self.assertIn(
            "issues", lowered,
            "the conflict path can only be read if Issues are on, and the workflow has to say so",
        )

    def test_the_sync_workflow_reports_a_conflict_without_issues(self):
        # Issues were off on this repository, so `gh issue create` failed with
        # "Resource not accessible by integration (createIssue)" and three
        # scheduled runs went red without saying anything a human would find.
        # The failure has to survive on its own: check first, annotate always.
        text = self.workflow(SYNC_WORKFLOW)
        self.assertIn(
            "has_issues", text,
            "the conflict path has to ask whether Issues can be used before relying on them",
        )
        self.assertIn(
            "::error::", text,
            "a conflict has to be an error annotation on the run, not only an exit code",
        )
        self.assertIn(
            "GITHUB_STEP_SUMMARY", text,
            "the conflict detail (files, resolution commands) has to be written into the run summary",
        )
        self.assertIn(
            "--diff-filter=U", text,
            "the conflicted paths have to be read before the merge is aborted, or there is nothing to report",
        )


if __name__ == "__main__":
    unittest.main()
