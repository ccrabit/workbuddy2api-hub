#!/usr/bin/env python3
"""Mechanical fixups after `git merge upstream/main` — no judgement, no prose.

The human/agent part of an upstream sync is resolving conflicts and writing the
release body. Everything else is bookkeeping that has to be right before the
suites pass, and it is exactly the bookkeeping that gets forgotten by hand:

  * README suite count (ReadmeTests checks the exact string);
  * the "已发布版本的完整记录" pointer line;
  * new top-level modules must be added to the payload guard list in
    scripts/build-fpk.sh and to PKG_MODULES in tests/_test_phase_e_verify.py
    (a module that wb_proxy imports but the package does not ship is an
    ImportError on the appliance, which is the worst failure mode we have);
  * Phase G policy: .github/workflows/ holds only upstream's release.yml;
  * fnpack.json (repo root + the FnDepot staging dir) and the frozen
    EXPECTED_VERSION/EXPECTED_URL in tests/_test_fndepot_source.py;
  * the device-version claims in docs/phase-f-delivery.md, which the e15 gate
    compares against the version actually installed on the box.

Idempotent: running it twice on the same tree changes nothing.
Usage:
    auto_sync_fixups.py --version 1.7.29 --base <sha> --upstream <sha> \\
        [--fpk dist/WorkBuddy2API-Hub_1.7.29_all.fpk] [--device-version 1.7.24] \\
        [--repo DIR] [--dry-run]
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
changed = []


def note(msg):
    print("  " + msg)


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def write(path, text, dry):
    old = read(path) if os.path.exists(path) else None
    if old == text:
        return False
    changed.append(os.path.relpath(path, REPO))
    if not dry:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
    return True


def git(*args):
    out = subprocess.run(("git",) + args, cwd=REPO, capture_output=True, text=True)
    if out.returncode != 0:
        sys.exit("git %s failed: %s" % (" ".join(args), out.stderr.strip()))
    return out.stdout.strip()


# --- README ---------------------------------------------------------------

def fix_readme(v, dry):
    path = os.path.join(REPO, "README.md")
    text = read(path)

    tests = [n for n in os.listdir(os.path.join(REPO, "tests"))
             if n.startswith("_test_") and n.endswith((".py", ".js"))]
    py = sum(1 for n in tests if n.endswith(".py"))
    js = len(tests) - py
    line = "%d 个套件：%d 个 Python + %d 个 JS" % (len(tests), py, js)
    text, n = re.subn(r"\d+ 个套件：\d+ 个 Python \+ \d+ 个 JS", line, text, count=1)
    if n != 1:
        sys.exit("README: the suite-count line is gone — upstream changed its shape")
    note("README 套件数 → " + line)

    text = re.sub(r"（v1\.4\.5 ~ v[\d.]+", "（v1.4.5 ~ v" + v, text)

    bullet = ("- **自动任务并入上游 v%s**：合并 `upstream/main`（`%s`）到飞牛层，"
              "按 `docs/phase-n-automation.md` 的流程构建、校验、发布并装机。"
              % (v, git("rev-parse", "--short", "upstream/main")))
    unreleased = text.split("### Unreleased", 1)[1] if "### Unreleased" in text else ""
    if "### Unreleased" in text and ("v" + v) not in unreleased:
        head, rest = text.split("### Unreleased", 1)
        lines = rest.split("\n")
        # keep the blank line after the header, then insert the bullet
        idx = 1 if lines and lines[0].strip() == "" else 0
        lines.insert(idx, bullet)
        text = head + "### Unreleased" + "\n".join(lines)
        note("README Unreleased 顶部插入自动条目")
    write(path, text, dry)


# --- payload guards -------------------------------------------------------

ENTRY_MODULES = ("wb_proxy.py", "wb_scheduler.py", "wb_update_request.py")


def imported_modules():
    """Modules an entry point imports at top level — these must be in the pack."""
    out = set()
    for name in ENTRY_MODULES:
        path = os.path.join(REPO, name)
        if not os.path.exists(path):
            continue
        for line in read(path).splitlines():
            m = re.match(r"(?:import|from)\s+(wb_[a-z_]+)", line)
            if m:
                out.add(m.group(1) + ".py")
    return out


def fix_guards(base, upstream, dry):
    added = [p for p in git("diff", "--diff-filter=A", "--name-only",
                            "%s..%s" % (base, upstream), "--", "*.py").splitlines()
             if p and "/" not in p]
    new = sorted(set(added) | imported_modules())
    if not added:
        note("没有新增顶层模块")

    path = os.path.join(REPO, "scripts", "build-fpk.sh")
    text = read(path)
    head, sep, tail = text.partition("for required in ")
    body, sep2, rest = tail.partition("; do")
    have = set(body.replace("\\", " ").split())
    gone = sorted(t for t in have
                  if t.endswith(".py") and not os.path.exists(os.path.join(REPO, t)))
    have -= set(gone)
    missing = [m for m in new if m not in have]
    if True:
        stripped = [t for t in body.replace("\\", " ").split()
                    if t and t not in gone]
        stripped += missing
        width = 4
        rows, row = [], []
        for tok in stripped:
            row.append(tok)
            if len(row) == width:
                rows.append(" ".join(row))
                row = []
        if row:
            rows.append(" ".join(row))
        body_lines = []
        for idx, r in enumerate(rows):
            prefix = "" if idx == 0 else "                    "
            body_lines.append(prefix + r + (" \\" if idx < len(rows) - 1 else " "))
        rebuilt = "\n".join(body_lines)
        if write(path, head + sep + rebuilt + sep2 + rest, dry) and missing:
            note("build-fpk.sh 守卫名单 += " + " ".join(missing))

    path = os.path.join(REPO, "tests", "_test_phase_e_verify.py")
    text = read(path)
    m = re.search(r"PKG_MODULES = \[(.*?)\]", text, re.S)
    if not m:
        sys.exit("PKG_MODULES not found")
    pkg_all = re.findall(r'"([^"]+)"', m.group(1))
    pkg_gone = {t for t in pkg_all
                if t.endswith(".py") and not os.path.exists(os.path.join(REPO, t))}
    have = set(pkg_all) - pkg_gone
    missing = [x for x in new if x not in have]
    if True:
        items = [t for t in pkg_all if t not in pkg_gone]
        items += missing
        lines, row = [], []
        for tok in items:
            row.append('"%s"' % tok)
            if len(row) == 3:
                lines.append("               " + ", ".join(row) + ",")
                row = []
        if row:
            lines.append("               " + ", ".join(row))
        block = "PKG_MODULES = [" + "\n".join(lines).lstrip() + "]"
        write(path, text[:m.start()] + block + text[m.end():], dry)
        note("PKG_MODULES += " + " ".join(missing))


def fix_workflows(dry):
    wf = os.path.join(REPO, ".github", "workflows")
    if not os.path.isdir(wf):
        return
    for name in sorted(os.listdir(wf)):
        if name == "release.yml":
            continue
        target = os.path.join(wf, name)
        note("删除工作流 " + name + "（Phase G 政策：只剩上游 release.yml）")
        changed.append(os.path.relpath(target, REPO))
        if not dry:
            os.remove(target)


# --- release metadata -----------------------------------------------------

def fix_release_metadata(v, fpk, dry):
    size = os.path.getsize(fpk)
    with open(fpk, "rb") as fh:
        sha = hashlib.sha256(fh.read()).hexdigest()
    url = ("https://github.com/ccrabit/workbuddy2api-hub/releases/download/"
           "fnos-%s/WorkBuddy2API-Hub_%s_all.fpk" % (v, v))
    entry = {
        "changelog": "并入上游 v%s（自动任务）：上游自上一个已发布版本以来的全部改动，"
                     "飞牛层（统一网关免密入口、面板主题与移动端适配、流式空闲心跳、"
                     "可写模型目录存档、打包排除口径）保持原样。" % v,
        "updated_at": datetime.datetime.now(
            datetime.timezone(datetime.timedelta(hours=8))).replace(
                microsecond=0).isoformat(),
        "packages": {"all": {"download_url": url, "sha256": sha, "size": size}},
    }
    for path in (os.path.join(REPO, "fnpack.json"),
                 os.path.join(os.environ.get("WB_FNDEPOT_SRC", "/tmp/fndepot-src"),
                              "fnpack.json")):
        if not os.path.exists(path):
            continue
        doc = json.loads(read(path))
        doc["apps"]["workbuddy2api"]["releases"] = {v: entry}
        write(path, json.dumps(doc, ensure_ascii=False, indent=2) + "\n", dry)
        note("回填 %s → %s" % (os.path.relpath(path, REPO), v))

    path = os.path.join(REPO, "tests", "_test_fndepot_source.py")
    text = read(path)
    text = re.sub(r'EXPECTED_VERSION = "[^"]*"', 'EXPECTED_VERSION = "%s"' % v, text)
    text = re.sub(r'"fnos-[^/]*/WorkBuddy2API-Hub_[^"]*_all\.fpk"',
                  '"fnos-%s/WorkBuddy2API-Hub_%s_all.fpk"' % (v, v), text)
    write(path, text, dry)
    note("tests/_test_fndepot_source.py 期望版本 → " + v)
    return size, sha


def fix_delivery_assets(v, fpk, dry):
    """Rewrite the *current* §1 block (package name / size / sha256 / checksum).

    Without this a cron run can never reach a green suite: three e15 gates read
    those numbers straight out of this file, and they describe the asset that was
    just built.
    """
    import hashlib
    import tarfile
    import tempfile
    size = os.path.getsize(fpk)
    sha = hashlib.sha256(open(fpk, "rb").read()).hexdigest()
    with tempfile.TemporaryDirectory() as tmp:
        with tarfile.open(fpk) as tf:
            tf.extractall(tmp)
        sums = hashlib.md5(open(os.path.join(tmp, "app.tgz"), "rb").read()).hexdigest()
    path = os.path.join(REPO, "docs", "phase-f-delivery.md")
    text = read(path)
    before = text
    text = re.sub(r"^## 1\. 包与已发布资产（[^，\n]+，本轮）",
                  "## 1. 包与已发布资产（%s，本轮）" % v, text, count=1, flags=re.M)
    text = re.sub(r"\| 文件 \| `dist/WorkBuddy2API-Hub_[^`]+_all\.fpk` \|",
                  "| 文件 | `dist/WorkBuddy2API-Hub_%s_all.fpk` |" % v, text, count=1)
    text = re.sub(r"\| 大小 \| [0-9]+ B \|",
                  "| 大小 | %d B |" % size, text, count=1)
    text = re.sub(r"\| sha256 \| `[0-9a-f]{64}` \|",
                  "| sha256 | `%s` |" % sha, text, count=1)
    text = re.sub(r"\| manifest checksum \| `[0-9a-f]{32}`",
                  "| manifest checksum | `%s`" % sums, text, count=1)
    if write(path, text, dry):
        note("交付说明 §1 指纹 → %d B / %s…" % (size, sha[:8]))
    return size, sha


def fix_delivery_doc(v, upstream, device_version, dry):
    path = os.path.join(REPO, "docs", "phase-f-delivery.md")
    text = read(path)
    text = re.sub(r"设备当前装的是\s*[0-9][0-9.]*",
                  "设备当前装的是 " + device_version, text)
    text = re.sub(r"设备上跑的还是\s*[0-9][0-9.]*",
                  "设备上跑的还是 " + device_version, text)
    stamp = datetime.datetime.now(
        datetime.timezone(datetime.timedelta(hours=8))).strftime("%Y-%m-%d %H:%M")
    head = (
        "> **自动化记录（%s，cron 任务 `wb-auto-sync` 写入）**：并入 `upstream/main` = `%s`；"
        "包版本 %s，发布 tag `fnos-%s`；设备当前装的是 %s。"
        "这一段的措辞由脚本生成，人工复核看 `logs/auto-sync/` 里对应那次的报告。\n"
        % (stamp, upstream[:12], v, v, device_version))
    if head.split("\n")[0] not in text:
        first = text.split("\n", 1)
        text = first[0] + "\n\n" + head + ("\n" + first[1] if len(first) > 1 else "")
        note("交付说明顶部写自动化记录")
    write(path, text, dry)


# --- main -----------------------------------------------------------------

def main():
    global REPO
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", required=True)
    ap.add_argument("--base", required=True)
    ap.add_argument("--upstream", required=True)
    ap.add_argument("--fpk")
    ap.add_argument("--device-version", default="")
    ap.add_argument("--repo", default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    REPO = os.path.abspath(args.repo or REPO)
    v = args.version

    fix_readme(v, args.dry_run)
    fix_guards(args.base, args.upstream, args.dry_run)
    fix_workflows(args.dry_run)
    if args.fpk:
        fix_release_metadata(v, args.fpk, args.dry_run)
        fix_delivery_assets(v, args.fpk, args.dry_run)
    if args.device_version:
        fix_delivery_doc(v, args.upstream, args.device_version, args.dry_run)

    print("%s: %d file(s) %s" % (
        "dry-run" if args.dry_run else "fixups",
        len(changed), "would change" if args.dry_run else "changed"))
    for path in sorted(set(changed)):
        print("  " + path)


if __name__ == "__main__":
    main()
