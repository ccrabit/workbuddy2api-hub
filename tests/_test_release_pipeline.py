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
throwaway git repository) and the repository state around it (statically).

Phase G deleted every workflow this fork maintained, so the static half now says
what the release path *is* instead of what the workflows were:
`.github/workflows/` holds upstream's `release.yml` and nothing of ours, nothing
under `.github/` schedules itself, and the steps the deleted workflows carried
live in the local tools (`scripts/build-fpk.sh`, `scripts/gh-release.py`) and in
`docs/phase-g-local-release.md`. Two of the gates below are deliberately shown to
have teeth: one reverts the script to the pre-phase-F namespace and asserts the
contract check fails, and one feeds the old mirror step to the static scan and
asserts it is caught. A gate that cannot fail is a comment.

Point WB_RELEASE_PIPELINE_ROOT at another checkout to check that tree instead -
that is how the red half of the evidence was produced. Bash or git missing skips
the behavioural half; the static gates always run.
"""

import io
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ROOT = os.path.dirname(TESTS_DIR)
WORKFLOWS_DIR = os.path.join(".github", "workflows")
UPSTREAM_RELEASE_WORKFLOW = os.path.join(WORKFLOWS_DIR, "release.yml")
SCRIPT = os.path.join("scripts", "build-fpk.sh")
GH_RELEASE = os.path.join("scripts", "gh-release.py")
RUNBOOK = os.path.join("docs", "phase-g-local-release.md")
GH_SUBCOMMANDS = ("sha256", "release-get", "release-create", "release-upload",
                  "release-edit", "tag-create")
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

# Phase G: there is no workflow left to scan, so the check that upstream's tags
# never enter this fork's refs/tags runs over the text artifacts that *do* exist.
MIRROR_PATTERN = re.compile(r"refs/tags/\$\{upstream_tag\}|git push[^\n]*--tags")


def mirrors_upstream_tags(text):
    """True when a piece of text pushes upstream's tags into this fork."""
    return MIRROR_PATTERN.search(text) is not None


def repository_texts(root):
    """Every readable text artifact under .github/ and scripts/, path -> text."""
    out = {}
    for base in (".github", "scripts"):
        for dirpath, dirnames, filenames in os.walk(os.path.join(root, base)):
            dirnames[:] = [d for d in dirnames if d != "__pycache__"]
            for name in filenames:
                path = os.path.join(dirpath, name)
                try:
                    with open(path, encoding="utf-8") as handle:
                        out[os.path.relpath(path, root)] = handle.read()
                except (OSError, UnicodeDecodeError):
                    continue
    return out


def repository_root():
    return os.path.abspath(os.environ.get("WB_RELEASE_PIPELINE_ROOT") or DEFAULT_ROOT)


def read_text(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def write_text(path, text):
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


def build_requirements(cwd):
    """The tools the packaging script uses that this box does not have.

    tar has to be GNU tar (the exclusions under test are GNU tar's) and find has
    to be GNU find (the staging step packs with -printf). Stock Windows has
    neither, so the payload gate below skips there instead of failing on
    something it cannot exercise - and it says so. The probes run in the
    checkout under test, like the build does.
    """
    missing = []
    for tool, marker in (("tar", "GNU tar"), ("find", "GNU findutils")):
        path = shutil.which(tool)
        if not path:
            missing.append(tool)
            continue
        try:
            output = subprocess.run(
                [path, "--version"], cwd=cwd, capture_output=True, text=True, timeout=60,
            ).stdout or ""
        except (OSError, subprocess.SubprocessError):
            missing.append(tool)
            continue
        if marker not in output:
            missing.append("%s that is %s" % (tool, marker))
    if not shutil.which("md5sum"):
        missing.append("md5sum")
    return missing


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


class PhaseGRepositoryTests(unittest.TestCase):
    """Phase G: none of our workflows are left, and the local path carries them.

    Every assertion below was about a file this repository maintained. Those
    files are gone - deliberately, and with no dispatch fallback - so each one is
    re-pointed at the capability that survived: which tags may start what, who
    may push where, and which local tool does the job now.
    """

    def setUp(self):
        self.root = repository_root()

    def path(self, relative):
        return os.path.join(self.root, relative)

    def read_file(self, relative):
        self.assertTrue(os.path.isfile(self.path(relative)), "%s is missing" % relative)
        return read_text(self.path(relative))

    def test_only_upstreams_release_workflow_is_left(self):
        names = sorted(os.listdir(self.path(WORKFLOWS_DIR)))
        self.assertEqual(
            ["release.yml"], names,
            "a workflow of ours is back: phase G deleted them on purpose and added no dispatch fallback",
        )
        text = self.read_file(UPSTREAM_RELEASE_WORKFLOW)
        self.assertIn('"v*"', text, "upstream's own workflow answers to upstream's tags")
        self.assertNotIn(
            "fnos-", text,
            "that file is upstream's, unchanged: it cannot know this fork's fnos- namespace, "
            "so it never fires on a release of ours",
        )

    def test_nothing_under_github_schedules_itself(self):
        texts = repository_texts(self.root)
        self.assertIn(
            UPSTREAM_RELEASE_WORKFLOW.replace(os.sep, "/"), 
            {name.replace(os.sep, "/") for name in texts},
            "the scan has to see upstream's file, or an empty scan proves nothing",
        )
        scheduled = sorted(
            name for name, text in texts.items()
            if "on: schedule" in text or re.search(r"(?m)^\s*cron:", text)
        )
        self.assertEqual([], scheduled, "GitHub must not run anything for this fork any more")

    def test_the_local_release_tool_covers_every_publishing_step(self):
        text = self.read_file(GH_RELEASE)
        for command in GH_SUBCOMMANDS:
            # The registration may wrap across lines, so match the call, not a line.
            self.assertRegex(
                text, r'add_parser\(\s*"%s"' % re.escape(command),
                "the local tool has to keep the step release-checksums.yml / release.yml did: %s" % command,
            )
        self.assertIn(
            'DEFAULT_REPO = "ccrabit/workbuddy2api-hub"', text,
            "the upload has to target this fork's repository",
        )
        self.assertIn("WB_GH_TOKEN", text, "the token comes from the environment first")
        self.assertIn("/root/.gh-token", text, "then from a file outside the repository")
        self.assertNotRegex(
            text, r"ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}",
            "no token may ever be committed",
        )

    def test_the_local_release_tool_runs_and_refuses_an_empty_command(self):
        # Executed, offline, with no token: the plumbing the runbook calls has to
        # exist and behave (exit 2 = usage, and the help lists every step).
        python = sys.executable or "python3"
        usage = subprocess.run(
            [python, self.path(GH_RELEASE)], cwd=self.root,
            capture_output=True, text=True, timeout=120,
        )
        self.assertEqual(2, usage.returncode, usage.stdout + usage.stderr)
        helped = subprocess.run(
            [python, self.path(GH_RELEASE), "--help"], cwd=self.root,
            capture_output=True, text=True, timeout=120,
        )
        self.assertEqual(0, helped.returncode, helped.stdout + helped.stderr)
        for command in GH_SUBCOMMANDS:
            self.assertIn(command, helped.stdout, "the help has to list %s" % command)

    def test_no_text_artifact_pushes_upstream_tags_into_this_fork(self):
        texts = repository_texts(self.root)
        offenders = sorted(name for name, text in texts.items() if mirrors_upstream_tags(text))
        self.assertEqual(
            [], offenders,
            "upstream's tags must stay out of this fork: they collide with a later fetch and they are "
            "the namespace upstream's own release workflow acts on",
        )
        # Sensitivity half: the step the fork used to run has to be caught, or
        # this scan is a comment.
        self.assertTrue(
            mirrors_upstream_tags(OLD_MIRROR_STEP),
            "the scan has to reject the pre-phase-F mirror step",
        )
        script = self.read_file(SCRIPT)
        self.assertIn("ls-remote --tags --refs upstream", script,
                      "what upstream has is asked of the upstream remote instead")

    def test_the_runbook_is_the_checklist_for_a_local_release(self):
        text = self.read_file(RUNBOOK)
        for step in ("python3 tests/run_all.py --jobs 4",
                     "bash scripts/build-fpk.sh",
                     "bash scripts/verify-fpk.sh",
                     "gh-release.py sha256",
                     "gh-release.py release-upload",
                     "gh-release.py tag-create",
                     'git tag -a "${TAG}"'):
            self.assertIn(step, text, "the runbook has to keep the step: %s" % step)
        self.assertIn("只有 `release.yml`", text,
                      "the checklist has to assert the workflow directory holds upstream's file only")
        self.assertIn("不恢复任何 CI", text,
                      "dropping CI has to be a stated decision, not a silent omission")


class TagNamespaceGateTests(FixtureTests):
    """Only fnos-X.Y.Z is a release tag - the rule the deleted gate executed.

    tests.yml carried a `version-assert` job: a release tag had to name the
    source version. Phase G deleted the job, and the rule now lives where a
    version is actually derived - `scripts/build-fpk.sh`, which is the only thing
    that turns a tag into a package version. Executed like the other behavioural
    gates: in a throwaway repository that holds a copy of the tree.
    """

    def source_version(self):
        text = read_text(os.path.join(self.work, "wb_proxy.py"))
        match = re.search(r'"version"\s*:\s*"([^"]+)"', text)
        self.assertIsNotNone(match, "wb_proxy.py has no overview version string")
        return match.group(1)

    def test_a_tag_that_names_the_source_version_is_the_package_version(self):
        source = self.source_version()
        self.tag("fnos-%s" % source)
        self.assert_release_version(self.work, source)
        self.assertRegex(self.version_at(self.work), RELEASE_VERSION)

    def test_a_tag_that_names_another_version_is_caught_by_the_comparison(self):
        # Sensitivity: the deleted gate compared the tagged version with the
        # source version, and that comparison has to stay able to say no.
        source = self.source_version()
        self.tag("fnos-9.9.9")
        tagged = self.version_at(self.work)
        self.assertEqual("9.9.9", tagged, "the tag on HEAD is what the script has to answer")
        self.assertNotEqual(
            source, tagged,
            "a tag naming another version has to be detectable, or the gate checks nothing",
        )

    def test_a_tag_outside_the_fnOS_namespace_is_not_a_release(self):
        # `release-1.6.19` names nothing the fork can publish: the answer has to
        # be a process version, which cannot be mistaken for a release.
        self.tag("release-%s" % self.source_version())
        self.assertRegex(
            self.version_at(self.work), PROCESS_VERSION,
            "only a fnos-X.Y.Z tag on HEAD may name a release of this fork",
        )

    def test_a_historical_upstream_tag_is_not_a_fork_release(self):
        # v* is upstream's namespace; the fork releases on fnos-* only, so even a
        # three-part v tag on HEAD leaves the build a process build.
        self.tag("v%s" % self.source_version())
        self.assertRegex(self.version_at(self.work), PROCESS_VERSION)


class PayloadHygieneTests(FixtureTests):
    """What a local run leaves behind may not travel inside the package.

    R19: the staging tar excluded './__pycache__', and a pattern with a slash in
    it is anchored to the repository root, so a nested release/__pycache__ that
    a local run had created went into the package. The same commit built on a
    developer's box and on CI then produced two different payloads (43 files
    against 40) and two different app.tgz checksums, which is what makes "the
    package is what this tree builds" unverifiable. The pattern that drops
    bytecode at any depth is the one without the slash.
    """

    RELEASE = "1.6.19"

    def setUp(self):
        super().setUp()
        missing = build_requirements(self.root)
        if missing:
            self.skipTest("needs the tools the packaging script uses; missing %s" % ", ".join(missing))

    def build(self, tree):
        """Build into `tree`; the checkout under test never gets a dist/."""
        env = dict(os.environ)
        env.update(
            VERSION=self.RELEASE,
            PACKAGER="ccrabit",
            PACKAGER_URL="https://github.com/ccrabit/workbuddy2api-hub",
        )
        result = subprocess.run(
            [self.bash, SCRIPT], cwd=tree, capture_output=True, text=True, timeout=900, env=env,
        )
        self.assertEqual(
            0, result.returncode,
            "build-fpk.sh failed in %s:\n%s" % (tree, result.stdout + result.stderr),
        )
        fpk = os.path.join(tree, "dist", "WorkBuddy2API-Hub_%s_all.fpk" % self.RELEASE)
        self.assertTrue(os.path.isfile(fpk), "the build left no package at %s" % fpk)
        return fpk

    def payload_members(self, fpk):
        """Every member of the inner app.tgz, as the device would unpack it."""
        with tarfile.open(fpk, "r:gz") as package:
            member = package.extractfile("app.tgz")
            self.assertIsNotNone(member, "the package carries no app.tgz")
            data = member.read()
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as payload:
            return payload.getnames()

    def scatter_bytecode(self, tree):
        """The junk a local run leaves: a cache directory and a loose .pyc."""
        cache = os.path.join(tree, "release", "__pycache__")
        os.makedirs(cache, exist_ok=True)
        write_text(os.path.join(cache, "release_tools.cpython-311.pyc"), "not really bytecode\n")
        write_text(os.path.join(tree, "release", "loose.pyc"), "not really bytecode either\n")
        return ["release/__pycache__/release_tools.cpython-311.pyc", "release/loose.pyc"]

    def test_the_payload_never_carries_compiled_bytecode(self):
        scattered = self.scatter_bytecode(self.work)
        members = self.payload_members(self.build(self.work))
        leaked = [name for name in members
                  if "__pycache__" in name.split("/") or name.endswith(".pyc")]
        self.assertEqual(
            [], leaked,
            "compiled bytecode travelled inside the package; the staging step has to drop %s"
            % ", ".join(scattered),
        )

    def test_a_stray_pyc_does_not_change_the_payload(self):
        """One commit, one package - whether or not a local run compiled."""
        clean = sorted(self.payload_members(self.build(self.work)))
        self.scatter_bytecode(self.work)
        dirty = sorted(self.payload_members(self.build(self.work)))
        self.assertEqual(
            [], [name for name in dirty if name not in clean],
            "a file only a local run created reached the package",
        )
        self.assertEqual(
            [], [name for name in clean if name not in dirty],
            "a local run removed files from the package",
        )


if __name__ == "__main__":
    unittest.main()
