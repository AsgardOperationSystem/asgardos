#!/usr/bin/env python3
# spec: EMU-3
# requires: cmd:git
"""Run: python -I test_emulator_perf.py  (no Thor): build flags and source patches that make emulators faster on the Thor
stay in place. Whether a game runs faster or draws less is measured on a Thor, not here.
- No recipe appends a compiler flag with no space: Azahar's `CXXFLAGS+=-fpch-preprocess` turned the toolchain's last
  flag into `-DNDEBUG-fpch-preprocess`, so dynarmic and the other bundled libraries were built with asserts on."""
import os
import re
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))


def read(*p):
    with open(os.path.join(*p)) as f:
        return f.read()


recipes = subprocess.run(["git", "-C", ROOT, "ls-files", "*.mk"], capture_output=True, text=True, check=True).stdout
glued = []
for name in recipes.split():
    for n, line in enumerate(read(ROOT, name).splitlines(), 1):
        if line.lstrip().startswith("#"):
            continue
        # FLAGS+=-x or FLAGS+="-x": joined onto the previous flag. FLAGS+=" -x" and FLAGS+=${X} are fine.
        if re.search(r"FLAGS\+=(\"?)(?![ \"$])\S", line):
            glued.append(f"{name}:{n}: {line.strip()}")
assert not glued, "a flag appended with no space joins the one before it:\n  " + "\n  ".join(glued)

print("OK")
