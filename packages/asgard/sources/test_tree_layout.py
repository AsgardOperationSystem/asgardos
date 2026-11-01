#!/usr/bin/env python3
# spec: DEV-4 DEV-5 DEV-12 DEV-13 DEV-17 DEV-19 DEV-20 DEV-21
# requires: cmd:git cmd:patch
# Tree checks on how the tree is laid out and what it promises to keep. Parts, with the rest in docs/human-checks.md:
#   DEV-4   the top-level layers, and that recipes live under packages/.
#   DEV-5   system.cfg keeps every key of the fork point, runemu.sh and es_features.cfg are there and set_kill is defined;
#           es_systems.cfg is generated, so test_image_contents.py checks it.
#   DEV-12  a package that reaches into another's build or install dir depends on it, directly or through its dependencies.
#           Undeclared use by other means shows only in a clean build.
#   DEV-13  the build applies patches with `patch -p1` and fuzz on, and `git apply` only for what patch can't do.
#   DEV-17  Python imports stay in the standard library, and there's no pip; Home is on Qt 6.
#   DEV-19  every /storage, /run and /flash path SPEC names is still in the code.
#   DEV-20  status lives only in the README, rule definitions only in SPEC.md, and the other homes exist.
#   DEV-21  files from the fork point keep their copyright lines; Asgard's own recipes are GPL-2.0.
import ast
import os
import re
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
FORK_POINT = "7cffc96"
SYSTEM_CFG = "packages/asgardos/config/system/configs/system.cfg"
SYSTEM_CFG_AT_FORK = "projects/ROCKNIX/packages/rocknix/config/system/configs/system.cfg"
LAYERS = {"config", "device", "distribution", "docs", "licenses", "packages", "scripts", "tools"}
RECIPE_OUTSIDE_PACKAGES = {"config/docker/package.mk"}  # the docker tool's own, not one of the image's
# Against DEV-17, and in SPEC's known gaps: this stops new ones, and test_gap_service_languages.sh holds the rule.
IMPORTS_NOT_IN_SPEC = {("packages/asgard/sources/asgard-motiond.py", "dbussy")}
COMPILED_NOT_IN_SPEC = {"packages/asgard/gamma/asgard-gamma.c"}  # asgard-gamma.service; the same gap file holds the rule
COMPILED_NOT_SERVICES = {"packages/asgard/eq/asgard-limiter.c"}  # a LADSPA plugin PipeWire loads
NOT_SERVICES = {"packages/asgard/eq/gen-speaker-ir.py"}  # a desktop tool that makes a file in the tree; it isn't installed
problems = []


def git(*args):
    proc = subprocess.run(["git", "-C", ROOT, *args], capture_output=True, text=True, errors="replace")
    if proc.returncode != 0:
        sys.exit(f"FAIL: git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout


def tree_files():
    return git("ls-files", "--cached", "--others", "--exclude-standard").splitlines()


def read(path):
    with open(os.path.join(ROOT, path), errors="replace") as f:
        return f.read()


def check_layers(files):
    """DEV-4"""
    layers = {f.split("/", 1)[0] for f in files if "/" in f}
    if layers != LAYERS:
        problems.append(f"top-level directories differ from SPEC's layers (DEV-4): {sorted(layers ^ LAYERS)}")
    stray = {f for f in files if f.endswith("/package.mk") and not f.startswith("packages/")} - RECIPE_OUTSIDE_PACKAGES
    if stray:
        problems.append(f"recipes outside packages/ (DEV-4): {sorted(stray)}")
    for package in ("asgard", "asgard-home", "asgardos"):
        if f"packages/{package}/package.mk" not in files:
            problems.append(f"packages/{package}/package.mk is missing (DEV-4)")


def cfg_keys(text):
    return set(re.findall(r"^#?\s*([A-Za-z0-9_.-]+)=", text, re.M))


def check_interfaces(files):
    """DEV-5"""
    before = cfg_keys(git("show", f"{FORK_POINT}:{SYSTEM_CFG_AT_FORK}"))
    if not before:
        problems.append("no system.cfg keys at the fork point: the scan is broken (DEV-5)")
    gone = before - cfg_keys(read(SYSTEM_CFG))
    if gone:
        problems.append(f"system.cfg lost keys ROCKNIX's scripts rely on (DEV-5): {sorted(gone)}")
    for path in ("packages/asgardos/sources/scripts/runemu.sh", "packages/ui/emulationstation/config/common/es_features.cfg"):
        if path not in files:
            problems.append(f"{path} is gone (DEV-5)")
    if not re.search(r"^function set_kill\(\)", read("packages/asgardos/profile.d/001-functions"), re.M):
        problems.append("set_kill is no longer defined (DEV-5)")


def check_dependencies(files):
    """DEV-12"""
    recipes = {}
    for path in files:
        if path.startswith("packages/") and path.endswith("/package.mk"):
            recipes[path.split("/")[-2]] = read(path)
    depends = {}
    for name, text in recipes.items():
        deps = set()
        for value in re.findall(r'PKG_DEPENDS\w*\+?=\s*"([^"]*)"', text):
            deps.update(d.split(":")[0] for d in value.split())
        depends[name] = deps

    def closure(name):
        seen, todo = set(), [name]
        while todo:
            for dep in depends.get(todo.pop(), ()):
                if dep not in seen:
                    seen.add(dep)
                    todo.append(dep)
        return seen

    if not any(re.search(r"get_(build|install)_dir", text) for text in recipes.values()):
        problems.append("no recipe uses get_build_dir: the scan is broken (DEV-12)")
    for name, text in recipes.items():
        used = {u.split(":")[0] for u in re.findall(r"get_(?:build|install)_dir\s+([\w.+-]+)", text)} - {name}
        undeclared = used - closure(name)
        if undeclared:
            problems.append(f"{name} uses {sorted(undeclared)}'s build output without depending on it (DEV-12)")


def check_patching():
    """DEV-13"""
    unpack = read("scripts/unpack")
    if not re.search(r'^\s*patch -d "\$\{PKG_BUILD\}" -p1 ', unpack, re.M):
        problems.append("scripts/unpack doesn't apply patches with patch -p1 (DEV-13)")
    if re.search(r"^\s*patch .*(-F ?0|--fuzz)", unpack, re.M):
        problems.append("scripts/unpack turned fuzz off (DEV-13)")
    # git apply stays only for the formats patch can't read, on the branch that tests for them.
    lines = git("grep", "-n", "--untracked", "git apply", "--", ":!*.md", ":!docs", ":!packages/asgard/sources/test_*",
                ).splitlines()
    if len(lines) != 1 or not lines[0].startswith("scripts/unpack:"):
        problems.append(f"git apply outside scripts/unpack's binary patch branch (DEV-13): {lines}")
    else:
        number = int(lines[0].split(":")[1])
        guard = unpack.splitlines()[number - 2]
        if "GIT binary patch" not in guard:
            problems.append(f"scripts/unpack's git apply isn't only for binary or rename patches (DEV-13): {guard}")


def python_files(files):
    for path in files:
        if not path.startswith("packages/asgard/") or path in NOT_SERVICES:
            continue
        name = os.path.basename(path)
        if name.startswith("test_") or not os.path.isfile(os.path.join(ROOT, path)):
            continue
        if name.endswith(".py"):
            yield path
        else:
            with open(os.path.join(ROOT, path), "rb") as f:
                if re.match(rb"#!.*python", f.readline()):
                    yield path


def check_languages(files):
    """DEV-17"""
    found = 0
    for path in python_files(files):
        found += 1
        folder = os.path.dirname(os.path.join(ROOT, path))
        siblings = {os.path.splitext(n)[0] for n in os.listdir(folder)}
        tree = ast.parse(read(path))
        modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
                modules.add(node.module.split(".")[0])
        for module in modules - set(sys.stdlib_module_names) - siblings:
            if (path, module) not in IMPORTS_NOT_IN_SPEC:
                problems.append(f"{path} imports {module}, not in the standard library (DEV-17)")
    if not found:
        problems.append("found no Python to check: the scan is broken (DEV-17)")
    compiled = {f for f in files if f.startswith("packages/asgard/")
                and f.endswith((".c", ".cc", ".cpp", ".go", ".rs", ".lua", ".js"))} - COMPILED_NOT_SERVICES - COMPILED_NOT_IN_SPEC
    if compiled:
        problems.append(f"new code in packages/asgard that isn't shell or Python (DEV-17): {sorted(compiled)}")
    proc = subprocess.run(["git", "-C", ROOT, "grep", "-nE", r"\bpip3? install|requirements\.txt", "--",
                           "packages/asgard", "packages/asgard-home", "packages/asgardos",
                           ":!packages/asgard/sources/test_*"], capture_output=True, text=True)
    if proc.stdout:
        problems.append(f"pip in Asgard's packages (DEV-17): {proc.stdout.strip()}")
    cmake = read("packages/asgard-home/src/CMakeLists.txt")
    if "find_package(Qt6" not in cmake or "Qt5" in cmake:
        problems.append("Asgard Home isn't on Qt 6 alone (DEV-17)")
    if " qt6 " not in read("packages/asgard-home/package.mk"):
        problems.append("Asgard Home's recipe doesn't depend on the image's qt6 (DEV-17)")


def check_named_paths():
    """DEV-19"""
    names = set()
    for path in re.findall(r"/(?:storage|run|flash)/[A-Za-z0-9_./-]+", read("SPEC.md")):
        names.add(path.rstrip("./"))
    if len(names) < 5:
        problems.append(f"SPEC.md names few paths: the scan is broken (DEV-19): {names}")
    for path in sorted(names):
        parts = path.strip("/").split("/")
        if parts[0] == "flash" and len(parts) == 2:
            continue  # /flash/KERNEL and the like: the boot layout, test_image_boot.py
        # Scripts often build a path from a directory variable, so match its last two parts.
        needle = "/".join(parts[-2:])
        proc = subprocess.run(["git", "-C", ROOT, "grep", "-qF", "--untracked", needle, "--", "packages", "device",
                               "distribution", ":!packages/asgard/sources/test_*"])
        if proc.returncode != 0:
            problems.append(f"SPEC.md names {path}, but no code uses it any more (DEV-19)")


def check_homes(files):
    """DEV-20"""
    if re.search("[✅\U0001F9EA]", read("SPEC.md")):
        problems.append("SPEC.md carries status marks: what works today goes in the README (DEV-20)")
    if not re.search("[✅\U0001F9EA]", read("README.md")):
        problems.append("the README has no status marks (DEV-20)")
    for path in ("SPEC.md", "README.md", "docs/changes.md", "docs/testing.md"):
        if path not in files:
            problems.append(f"{path} is gone (DEV-20)")
    if not any(f.startswith("docs/plans/") for f in files):
        problems.append("docs/plans/ is gone (DEV-20)")
    for path in files:
        if path.endswith(".md") and path != "SPEC.md" and os.path.isfile(os.path.join(ROOT, path)):
            if re.search(r"^- \*\*[A-Z]+-[0-9]+\*\* ", read(path), re.M):
                problems.append(f"{path} defines a spec rule: they live in SPEC.md (DEV-20)")


def fork_blobs(names):
    """{name: bytes} of these paths at the fork point, for the ones that existed."""
    proc = subprocess.run(["git", "-C", ROOT, "cat-file", "--batch"], capture_output=True,
                          input="".join(f"{FORK_POINT}:{name}\n" for name in names).encode())
    stream, position, blobs = proc.stdout, 0, {}
    for name in names:
        end = stream.index(b"\n", position)
        header = stream[position:end].split()
        position = end + 1
        if header[-1] != b"missing":
            size = int(header[2])
            blobs[name] = stream[position:position + size]
            position += size + 1
    return blobs


def notices(body):
    return [] if b"\0" in body[:8000] else [n.strip() for n in re.findall(rb"Copyright \(C\)[^\n]*", body[:4000])]


def check_notices():
    """DEV-21"""
    changed = []
    for line in git("diff", "-M", "-l0", "--name-status", "--diff-filter=MR", FORK_POINT, "HEAD").splitlines():
        fields = line.split("\t")
        if not fields[-1].endswith(".md"):  # code, not the docs: the README's credits are its License section
            changed.append((fields[1], fields[-1]))
    if len(changed) < 100:
        problems.append("few files changed since the fork: the scan is broken (DEV-21)")
    # The restructure made ROCKNIX's project overrides the package itself, so a file can descend from either copy.
    overrides = [f"projects/ROCKNIX/{new}" for _, new in changed]
    blobs = fork_blobs(sorted({old for old, _ in changed} | set(overrides)))
    for old, new in changed:
        if not os.path.isfile(os.path.join(ROOT, new)):
            continue
        with open(os.path.join(ROOT, new), "rb") as f:
            now = f.read()
        ancestors = [notices(blobs[name]) for name in (old, f"projects/ROCKNIX/{new}") if name in blobs]
        if ancestors and not any(all(n in now for n in a) for a in ancestors):
            lost = [n for n in ancestors[0] if n not in now]
            problems.append(f"{new} lost its notice (DEV-21): {lost[0].decode(errors='replace')}")
    for package in ("asgard", "asgard-home", "asgardos"):
        if not re.search(r'^PKG_LICENSE="GPL(-2\.0|v2)"', read(f"packages/{package}/package.mk"), re.M):
            problems.append(f"packages/{package} isn't GPL-2.0 (DEV-21)")


def main():
    files = tree_files()
    check_layers(files)
    check_interfaces(files)
    check_dependencies(files)
    check_patching()
    check_languages(files)
    check_named_paths()
    check_homes(files)
    check_notices()
    if problems:
        sys.exit("FAIL: " + "\n".join(problems))
    print("OK")


if __name__ == "__main__":
    main()
