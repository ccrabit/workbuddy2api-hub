"""The version this fork publishes is upstream's own number, everywhere.

Phase E gave the fork its own fourth version component ("upstream 1.6.10 plus
the Nth release of ours") and mirrored upstream's tags into the fork to keep it
derivable. Both halves turned out to be wrong:

* the derivation read "the newest three-part tag this checkout can see", and a
  fresh CI checkout of the fork saw only the fork's own tags, so the tag
  v1.6.17.1 built a package called 1.6.10.3;
* mirroring upstream's tags into this fork writes into upstream's own tag
  namespace, which is the namespace upstream's release.yml acts on, and gives a
  later `git fetch upstream` two tags to fight over;
* a fourth component cannot be compared with upstream's numbers: it says "how
  many of our releases sit on this upstream version", which is not something a
  user or the app store can read anything from.

The contract now is: a release of this fork is tagged fnos-<upstream version>
(fnos-1.6.19), the package version is exactly that number, and a build with no
such tag on HEAD is a process build (-alpha<k>) that cannot be mistaken for a
release. This file gates both halves of that - the script (behaviourally, in a
throwaway git repository) and the workflows that carry the number from the tag
to the package (statically, plus the tests workflow's own gate, executed).

Two of the gates below are deliberately shown to have teeth: one reverts the
script to the pre-phase-F namespace and asserts the contract check fails, and
one feeds the old mirror step to the static check and asserts it is rejected.
A gate that cannot fail is a comment.

Point WB_RELEASE_PIPELINE_ROOT at another checkout to check that tree instead -
that is how the red half of the evidence was produced. Bash or git missing
skips the behavioural half (the Windows runners stay useful) and PyYAML missing
skips the workflow-execution half; the static gates always run.
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
TESTS_WORKFLOW = os.path.join(".github", "workflows", "tests.yml")
SCRIPT = os.path.join("scripts", "build-fpk.sh")
RELEASE_VERSION = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
PROCESS_VERSION = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+-alpha[0-9]+$")

# What the merged workflow looked like before phase F. Kept as text so the
# static gate can be shown to reject it: it pushes upstream's tags into this
# fork's refs/tags, which is the namespace upstream's own release workflow acts
# on, and the tags it pushes then collide with the ones a later fetch brings in.
OLD_MIRROR_STEP = """
      - name: Mirror upstream tags
        run: |
          for upstream_tag in $(git tag --merged "upstream/main" --list 'v*'); do
            git push origin "refs/tags/${upstream_tag}"
          done
"""


def repository_root():
    return os.path.abspath(os.environ.get("WB_RELEASE_PIPELINE_ROOT") or DEFAULT_ROOT)


def read_text(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def write_text(path, text):
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


class FixtureTests(unittest.TestCase):
    """Base: a throwaway one-commit repository holding a copy of the tree."""

    def setUp(self):
        self.root = repository_root()
        self.bash = shutil.which("bash")
        self.git = shutil.which("git")
        if not self.bash or not self.git:
            self.skipTest("needs bash and git on PATH")
        script = os.path.join(self.root, SCRIPT)
        if not os.path.isfile(script):
            self.skipTest("no %s under %s" % (SCRIPT, self.root))
        self.tmp = tempfile.mkdtemp(prefix="wb-release-pipeline-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        # A copy of the working tree, not `git clone`: an uncommitted fix has to
        # be visible to this gate, and a one-commit repository with the real
        # fnos/manifest is all the script needs to be asked for a version.
        self.work = os.path.join(self.tmp, "work")
        shutil.copytree(
            self.root, self.work,
            ignore=shutil.ignore_patterns(".git", "dist", "build", "__pycache__", "*.pyc"),
        )
        self.git_at(self.work, "init", "--quiet")
        # Annotated tags need an identity, and a CI runner or a fresh box may have
        # none; keep it inside the throwaway repository.
        self.git_at(self.work, "config", "user.email", "release-pipeline@example.invalid")
        self.git_at(self.work, "config", "user.name", "release pipeline check")
        self.git_at(self.work, "add", "-A")
        self.git_at(self.work, "commit", "--quiet", "-m", "release pipeline fixture")
        self.manifest_version = self.read_manifest_version()

    def read_manifest_version(self):
        text = read_text(os.path.join(self.work, "fnos", "manifest"))
        match = re.search(r"(?m)^version\s*=\s*(\S+)\s*$", text)
        self.assertIsNotNone(match, "fnos/manifest has no version line")
        return match.group(1)

    def git_at(self, cwd, *args):
        result = subprocess.run([self.git, *args], cwd=cwd, capture_output=True, text=True, timeout=300)
        self.assertEqual(0, result.returncode, "git %s failed: %s" % (" ".join(args), result.stderr))
        return result.stdout

    def tag(self, name, message=None):
        self.git_at(self.work, "commit", "--quiet", "--allow-empty", "-m", message or name)
        self.git_at(self.work, "tag", "-a", name, "-m", message or name)

    def version_at(self, tree, *args):
        result = subprocess.run(
            [self.bash, os.path.join("scripts", "build-fpk.sh"), "--print-version", *args],
            cwd=tree, capture_output=True, text=True, timeout=300,
        )
        self.assertEqual(0, result.returncode, "build-fpk.sh --print-version failed: %s" % result.stderr)
        return result.stdout.strip()

    def assert_release_version(self, tree, expected):
        """The contract, in one assertion: this tree is that version."""
        self.assertEqual(
            expected, self.version_at(tree),
            "a %s tag on HEAD IS version %s, whatever else the checkout can see" % (expected, expected),
        )

    def revert_the_namespace(self, tree):
        """Put the pre-phase-F derivation back into a copy of the script.

        The old script looked for a four-part "v" tag on HEAD; every other part
        of the derivation is downstream of that one choice.
        """
        path = os.path.join(tree, SCRIPT)
        text = read_text(path)
        reverted = text.replace(r"^fnos-[0-9]+(\.[0-9]+){2}$", r"^v[0-9]+(\.[0-9]+){3}$")
        reverted = reverted.replace("${head_tag#fnos-}", "${head_tag#v}")
        self.assertNotEqual(text, reverted, "this gate has to change the script it is checking")
        write_text(path, reverted)


class VersionContractTests(FixtureTests):
    """What a tree says its version is."""

    def test_a_release_tag_on_head_is_the_version(self):
        # A historical four-part tag on HEAD must not outrank it, and the version
        # must stay upstream's three components - no release ordinal.
        self.git_at(self.work, "tag", "-a", "v1.6.17.1", "-m", "historical four-part tag")
        self.git_at(self.work, "tag", "-a", "fnos-1.6.19", "-m", "fnos-1.6.19")
        self.assert_release_version(self.work, "1.6.19")
        self.assertRegex(self.version_at(self.work), RELEASE_VERSION)

    def test_the_tag_set_that_produced_1_6_10_3_now_yields_the_tag(self):
        # The tags a CI checkout had when the tag v1.6.17.1 built 1.6.10.3:
        # upstream's releases up to v1.6.10, this fork's two ordinal tags on top,
        # and the release tag. Deriving from what was visible gave 1.6.10 with
        # ordinal 3 - the version the CI log printed.
        for tag in ("v1.6.1", "v1.6.10", "v1.6.10.1", "v1.6.10.2"):
            self.tag(tag, "upstream %s" % tag)
        self.tag("fnos-1.6.19", "fnos-1.6.19")
        visible = sorted(self.git_at(self.work, "tag", "--list").split())
        self.assertEqual(
            ["fnos-1.6.19", "v1.6.1", "v1.6.10", "v1.6.10.1", "v1.6.10.2"], visible,
            "the fixture has to reproduce the tag set CI saw, or it proves nothing",
        )
        self.assert_release_version(self.work, "1.6.19")

    def test_a_shallow_clone_of_the_release_tag_reports_that_tag(self):
        # `git clone --depth 1 --branch fnos-1.6.19` is what a shallow checkout
        # of a release looks like: one tag, no history, nothing to derive from.
        # The old script fell back to fnos/manifest there.
        self.git_at(self.work, "tag", "-a", "fnos-1.6.19", "-m", "fnos-1.6.19")
        # A file:// URL, not a bare path: `--depth` is only honoured over a URL.
        source = pathlib.Path(self.work).resolve().as_uri()
        shallow = os.path.join(self.tmp, "shallow")
        self.git_at(
            self.tmp, "clone", "--quiet", "--depth", "1", "--branch", "fnos-1.6.19", source, shallow,
        )
        visible = sorted(self.git_at(shallow, "tag", "--list").split())
        self.assertEqual(
            ["fnos-1.6.19"], visible,
            "a depth-1 clone has to carry the release tag and nothing else, or this is not the shallow case",
        )
        self.assert_release_version(shallow, "1.6.19")

    def test_a_historical_four_part_tag_is_not_a_release_anymore(self):
        # Nothing is deleted, but the fourth component is no longer published:
        # such a tag describes its source version and nothing else.
        self.git_at(self.work, "tag", "-a", "v1.6.17.1", "-m", "historical tag")
        version = self.version_at(self.work)
        self.assertNotEqual("1.6.17.1", version)
        self.assertRegex(version, PROCESS_VERSION)

    def test_alpha_builds_of_a_release_commit_stay_process_builds(self):
        # Rebuilding a released commit as "the same version, plus alpha" would
        # hand out a number the app store cannot compare; the suffix stays.
        self.git_at(self.work, "tag", "-a", "fnos-1.6.19", "-m", "fnos-1.6.19")
        alpha = self.version_at(self.work, "--alpha")
        self.assertEqual("1.6.19-alpha0", alpha)

    def test_a_tree_with_no_release_tag_never_prints_a_release_version(self):
        result = self.version_at(self.work)
        self.assertRegex(result, PROCESS_VERSION)
        self.assertTrue(
            result.startswith(self.manifest_version + "-alpha"),
            "with no tags and no upstream remote the manifest is the base: %s" % result,
        )

    def test_the_last_release_is_preferred_over_the_manifest(self):
        self.git_at(self.work, "tag", "-a", "fnos-1.6.19", "-m", "fnos-1.6.19")
        self.git_at(self.work, "commit", "--quiet", "--allow-empty", "-m", "work after the release")
        self.assertEqual("1.6.19-alpha1", self.version_at(self.work))

    def test_the_upstream_remote_is_asked_when_no_tag_is_visible(self):
        # A fresh clone of this fork has the fork's remote only, and this fork no
        # longer mirrors upstream's tags - so the script has to ask upstream.
        bare = os.path.join(self.tmp, "upstream.git")
        seed = os.path.join(self.tmp, "upstream-seed")
        self.git_at(self.tmp, "init", "--quiet", "--bare", bare)
        self.git_at(self.tmp, "init", "--quiet", seed)
        self.git_at(seed, "config", "user.email", "upstream@example.invalid")
        self.git_at(seed, "config", "user.name", "upstream seed")
        self.git_at(seed, "commit", "--quiet", "--allow-empty", "-m", "upstream release")
        self.git_at(seed, "tag", "-a", "v1.6.19", "-m", "v1.6.19")
        self.git_at(seed, "remote", "add", "origin", bare)
        self.git_at(seed, "push", "--quiet", "origin", "HEAD:refs/heads/main", "--tags")
        self.assertEqual(
            [], sorted(self.git_at(self.work, "tag", "--list").split()),
            "the fixture has to start without tags, or the fallback chain is not being tested",
        )
        self.git_at(self.work, "remote", "add", "upstream", bare)
        self.assertEqual("1.6.19-alpha0", self.version_at(self.work))

    def test_the_contract_fails_on_a_script_without_the_fnOS_namespace(self):
        # The sensitivity half: revert the namespace in a copy of the tree and
        # the contract above has to break, loudly. If this passes while the
        # contract passes, the contract is not checking anything.
        self.git_at(self.work, "tag", "-a", "fnos-9.9.9", "-m", "fnos-9.9.9")
        self.assert_release_version(self.work, "9.9.9")
        pre_fix = os.path.join(self.tmp, "pre-fix")
        shutil.copytree(self.work, pre_fix)
        self.revert_the_namespace(pre_fix)
        self.assertNotEqual(
            "9.9.9", self.version_at(pre_fix),
            "the pre-fix script has to answer something else, or the reverting fixture proves nothing",
        )
        with self.assertRaises(AssertionError):
            self.assert_release_version(pre_fix, "9.9.9")


class WorkflowGateTests(unittest.TestCase):
    """The workflows: which tag they answer to, and what they may push."""

    def setUp(self):
        self.root = repository_root()

    def workflow(self, relative):
        path = os.path.join(self.root, relative)
        self.assertTrue(os.path.isfile(path), "%s is missing" % relative)
        return read_text(path)

    def test_the_build_workflow_answers_to_the_fnOS_namespace(self):
        text = self.workflow(BUILD_WORKFLOW)
        self.assertIn(
            'tags: ["fnos-*"', text,
            "a release of this fork is tagged fnos-X.Y.Z, so that has to start a build",
        )
        self.assertIn(
            "TAG_REF: ${{", text,
            "the build workflow has to notice the pushed tag instead of letting the script guess",
        )
        self.assertIn(
            "${TAG_REF#fnos-}", text,
            "the tag has to lose its fnos- prefix before it can be a package version",
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

    def test_the_sync_workflow_schedules_three_attempts_a_day(self):
        text = self.workflow(SYNC_WORKFLOW)
        for slot in ('cron: "17 3 * * *"', 'cron: "23 9 * * *"', 'cron: "41 15 * * *"'):
            self.assertIn(slot, text, "the sync has to survive a dropped scheduled run: %s" % slot)

    def test_the_sync_workflow_never_pushes_upstream_tags_into_this_fork(self):
        text = self.workflow(SYNC_WORKFLOW)
        self.assertNotIn(
            "refs/tags/${upstream_tag}", text,
            "upstream's tags must stay out of this fork: they collide with a later fetch and "
            "they are the namespace upstream's own release workflow acts on",
        )
        self.assertIn("ls-remote", text, "what upstream has is asked of the upstream remote instead")
        self.assertIn("fnos-", text, "releases of this fork are tagged fnos-X.Y.Z")

    def test_the_static_check_rejects_the_old_mirror_step(self):
        # Sensitivity half for the check above.
        text = self.workflow(SYNC_WORKFLOW)
        self.assertNotIn("refs/tags/${upstream_tag}", text)
        with self.assertRaises(AssertionError):
            self.assertNotIn("refs/tags/${upstream_tag}", text + OLD_MIRROR_STEP)

    def test_the_sync_workflow_publishes_only_a_newer_upstream_release(self):
        text = self.workflow(SYNC_WORKFLOW)
        self.assertIn(
            "ls-remote --tags --refs origin", text,
            "what this fork has already published has to be read from origin, not from the local tags",
        )
        self.assertRegex(
            text, r"not newer than", "a version that is already published must not be published again",
        )
        self.assertIn("fnos-${version}", text, "the release tag has to be built from the upstream version")
        self.assertNotRegex(
            text, r"fnos-[0-9]+\.[0-9]+\.[0-9]+\.",
            "no release tag of this fork carries a fourth component",
        )

    def test_the_sync_workflow_keeps_a_conflicted_merge_visible(self):
        text = self.workflow(SYNC_WORKFLOW)
        self.assertIn(
            "sync-conflict/", text,
            "a conflict has to leave the conflicted merge somewhere a human can pick it up",
        )
        self.assertIn("git push --force", text, "the conflict branch is pushed, not left in the runner")
        self.assertIn(
            "--diff-filter=U", text,
            "the conflicted paths have to be read before the merge is aborted, or there is nothing to report",
        )
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


class TagAssertWorkflowTests(unittest.TestCase):
    """The tests workflow's tag gate, executed with synthetic tag names."""

    def setUp(self):
        self.root = repository_root()
        self.bash = shutil.which("bash")
        if not self.bash:
            self.skipTest("needs bash on PATH")
        path = os.path.join(self.root, TESTS_WORKFLOW)
        if not os.path.isfile(path):
            self.skipTest("no %s under %s" % (TESTS_WORKFLOW, self.root))
        try:
            import yaml
        except ImportError:
            self.skipTest("needs PyYAML to read the workflow")
        job = yaml.safe_load(read_text(path))["jobs"]["version-assert"]
        runs = [step["run"] for step in job["steps"] if "run" in step]
        self.assertEqual(1, len(runs), "expected exactly one run step in the version-assert job")
        self.run_step = runs[0]
        source = os.path.join(self.root, "wb_proxy.py")
        if not os.path.isfile(source):
            self.skipTest("no wb_proxy.py under %s" % self.root)
        match = re.search(r'"version"\s*:\s*"([^"]+)"', read_text(source))
        self.assertIsNotNone(match, "wb_proxy.py has no overview version string")
        self.overview = match.group(1)

    def gate(self, tag):
        tmp = tempfile.mkdtemp(prefix="wb-tag-assert-")
        self.addCleanup(shutil.rmtree, tmp, True)
        script = os.path.join(tmp, "gate.sh")
        write_text(script, self.run_step)
        env = dict(os.environ)
        env["GITHUB_REF_NAME"] = tag
        return subprocess.run(
            [self.bash, script], cwd=self.root, capture_output=True, text=True, env=env, timeout=120,
        )

    def test_a_release_tag_that_names_the_source_version_passes(self):
        result = self.gate("fnos-%s" % self.overview)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_a_release_tag_that_names_another_version_fails(self):
        result = self.gate("fnos-9.9.9")
        self.assertNotEqual(0, result.returncode, "a tag that names another version has to be rejected")
        self.assertIn("::error::", result.stdout + result.stderr)

    def test_historical_tags_are_still_accepted(self):
        for tag in ("v%s" % self.overview, "v%s.1" % self.overview):
            result = self.gate(tag)
            self.assertEqual(0, result.returncode, "%s: %s" % (tag, result.stdout + result.stderr))

    def test_a_tag_outside_both_namespaces_is_rejected(self):
        result = self.gate("release-%s" % self.overview)
        self.assertNotEqual(0, result.returncode, "only v* (historical) and fnos-* tags are releases")
        self.assertIn("::error::", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
