#!/usr/bin/env python3
# spec: DEV-1 DEV-3 DEV-6 DEV-7 DEV-8
# requires: cmd:git file:packages/linux/src/Makefile
# Tree check over git's own data, with no network: remote branches are read from the local tracking refs, so they're as
# of the last fetch. What this can't see is in docs/human-checks.md: that fixes come in one at a time (DEV-1), that each
# patch is one commit (DEV-6), and that force-push is limited to `asgard` (DEV-7, a GitLab setting).
import os
import re
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
KERNEL = os.path.join(ROOT, "packages", "linux", "src")
FORK_POINT = "7cffc96"
# Against the rule, and in SPEC's known gaps: these lists stop new ones, and test_gap_kernel_debug_branch.sh and
# test_gap_kernel_patch_files.sh hold the rule itself.
KERNEL_BRANCHES_NOT_IN_SPEC = {"debug/disp-rsc-dump"}
KERNEL_PATCH_FILES_NOT_IN_SPEC = {
    "packages/linux/patches/mainline/0002-input-add-input-polldev-driver.patch",
    "packages/linux/patches/mainline/0003-pwm-add-pwm_set_period.patch",
    "packages/linux/patches/mainline/0004-input-adc-keys-redirect-keycode-316-to-rocknix-joypa.patch",
    "packages/linux/patches/mainline/0005-Bluetooth-btrtl-Add-the-support-for-RTL8733BU.patch",
}
problems = []


def git(*args, cwd=ROOT):
    return subprocess.run(["git", "-C", cwd, *args], capture_output=True, text=True, errors="replace")


def out(*args, cwd=ROOT):
    proc = git(*args, cwd=cwd)
    if proc.returncode != 0:
        sys.exit(f"FAIL: git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout.strip()


def check_no_merge_of_upstream():
    """DEV-1: merging ROCKNIX brings its commits, and those keep their own committers. Cherry-picks don't: their committer
    is whoever picked them. One owner made every commit since the fork, so a second committer means upstream came in."""
    if git("merge-base", "--is-ancestor", FORK_POINT, "HEAD").returncode != 0:
        problems.append(f"the fork point {FORK_POINT} isn't in this history (SPEC DEV-1)")
        return
    committers = out("log", "--format=%cn", f"{FORK_POINT}..HEAD").splitlines()
    if not committers:
        problems.append("no commits since the fork: the scan is broken")
    elif len(set(committers)) > 1:
        problems.append(f"commits by {sorted(set(committers))} since the fork: was ROCKNIX merged? (SPEC DEV-1)")
    for line in out("log", "--merges", "--format=%h %s", f"{FORK_POINT}..HEAD").splitlines():
        if re.search(r"^\S+ Merge .*(rocknix/|upstream/|branch 'next'|/next(\s|$))", line, re.I):
            problems.append(f"a merge from upstream (SPEC DEV-1): {line}")


def remote_branches(cwd):
    refs = out("for-each-ref", "--format=%(refname)", "refs/remotes/origin", cwd=cwd).splitlines()
    names = {r[len("refs/remotes/origin/"):] for r in refs}
    if not names:
        problems.append(f"no origin branches known in {cwd}: the scan can't tell (SPEC DEV-3)")
    return names - {"HEAD"}


def check_branches():
    """DEV-3"""
    extra = remote_branches(ROOT) - {"main"}
    if extra:
        problems.append(f"long-lived branches here besides main (SPEC DEV-3): {sorted(extra)}")
    extra = remote_branches(KERNEL) - {"asgard"} - KERNEL_BRANCHES_NOT_IN_SPEC
    if extra:
        problems.append(f"branches in the kernel repo besides asgard (SPEC DEV-3): {sorted(extra)}")


def pointer():
    fields = out("ls-files", "-s", "packages/linux/src").split()
    if not fields or fields[0] != "160000":
        problems.append(f"packages/linux/src isn't a submodule (SPEC DEV-6): {fields}")
        return None
    return fields[1]


def pkg_mk():
    with open(os.path.join(ROOT, "packages", "linux", "package.mk")) as f:
        return f.read()


def check_kernel_repo(commit):
    """DEV-6"""
    with open(os.path.join(ROOT, ".gitmodules")) as f:
        modules = f.read()
    if not re.search(r"path = packages/linux/src\n\s*url = \S*asgardos/linux(\.git)?\n\s*branch = asgard\b", modules):
        problems.append(f"the submodule isn't asgardos/linux on branch asgard (SPEC DEV-6): {modules}")
    version = re.search(r'^PKG_VERSION="([^"]+)"', pkg_mk(), re.M)
    tag = f"v{version.group(1)}" if version else None
    if not version or git("merge-base", "--is-ancestor", tag, commit, cwd=KERNEL).returncode != 0:
        problems.append(f"the kernel commit isn't on the stable tag {tag} (SPEC DEV-6: Linux stable plus commits)")
        return
    if out("rev-list", "--merges", f"{tag}..{commit}", cwd=KERNEL):
        problems.append(f"merges on top of {tag}: a rebase can't replay them (SPEC DEV-6)")
    trees = out("log", "--format=%h", f"{tag}..{commit}", "--", "arch/arm64/boot/dts/qcom/*ayn-thor*", cwd=KERNEL).split()
    if len(trees) != 1:
        problems.append(f"the device trees should be one commit, found {trees} (SPEC DEV-6)")


def check_no_patch_files(commit):
    """DEV-7"""
    text = pkg_mk()
    if re.search(r'^PKG_URL=', text, re.M):
        problems.append("packages/linux/package.mk has a PKG_URL: the kernel comes from the submodule (SPEC DEV-7)")
    if not re.search(r'^PKG_PATCH_DIRS=""', text, re.M):
        problems.append('packages/linux/package.mk must keep PKG_PATCH_DIRS="" (SPEC DEV-7)')
    if not re.search(r"rsync -a --exclude=\.git \$\{PKG_DIR\}/src/ \$\{PKG_BUILD\}/", text):
        problems.append("the build doesn't copy the submodule as it is (SPEC DEV-7)")
    files = out("ls-files", "--cached", "--others", "--exclude-standard", "packages/linux", "device", "distribution",
                ).splitlines()
    kernel_side = [f for f in files if f.startswith("packages/linux/") or "/patches/linux/" in f]
    patches = {f for f in kernel_side if f.endswith((".patch", ".diff"))}
    tarballs = {f for f in kernel_side if re.search(r"\.(tar(\.\w+)?|tgz|txz)$", f)}
    extra = (patches - KERNEL_PATCH_FILES_NOT_IN_SPEC) | tarballs
    if extra:
        problems.append(f"kernel patch files or tarballs (SPEC DEV-7): {sorted(extra)}")
    makefile = out("show", f"{commit}:Makefile", cwd=KERNEL)
    parts = [re.search(rf"^{k} = (\d+)", makefile, re.M) for k in ("VERSION", "PATCHLEVEL", "SUBLEVEL")]
    actual = ".".join(p.group(1) for p in parts if p)
    version = re.search(r'^PKG_VERSION="([^"]+)"', text, re.M)
    if not version or version.group(1) != actual:
        problems.append(f"PKG_VERSION doesn't match the submodule's kernel {actual} (SPEC DEV-7)")
    if git("merge-base", "--is-ancestor", commit, "refs/remotes/origin/asgard", cwd=KERNEL).returncode != 0:
        problems.append(f"the kernel pointer {commit[:12]} isn't on origin/asgard: pushed before the bump? (SPEC DEV-7)")


def check_own_objects():
    """DEV-8"""
    for cwd in (ROOT, KERNEL):
        git_dir = out("rev-parse", "--absolute-git-dir", cwd=cwd)
        for name in ("alternates", "http-alternates"):
            path = os.path.join(git_dir, "objects", "info", name)
            if os.path.exists(path) and os.path.getsize(path):
                problems.append(f"{path} exists (SPEC DEV-8: the build container only sees the tree)")
        if not os.path.realpath(git_dir).startswith(os.path.realpath(ROOT) + os.sep):
            problems.append(f"{git_dir} is outside the tree (SPEC DEV-8)")
    gitfile = os.path.join(KERNEL, ".git")
    if os.path.isfile(gitfile):
        with open(gitfile) as f:
            target = f.read().split(":", 1)[-1].strip()
        if os.path.isabs(target):
            problems.append(f"the submodule's gitdir is an absolute path, {target}: it won't resolve at /work (SPEC DEV-8)")


def main():
    check_no_merge_of_upstream()
    check_branches()
    commit = pointer()
    if commit:
        check_kernel_repo(commit)
        check_no_patch_files(commit)
    check_own_objects()
    if problems:
        sys.exit("FAIL: " + "\n".join(problems))
    print("OK")


if __name__ == "__main__":
    main()
