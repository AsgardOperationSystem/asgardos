#!/usr/bin/env python3
# spec: EMU-3
# requires: cmd:git
"""Run: python -I test_emulator_perf.py  (no Thor): build flags and source patches that make emulators faster on the Thor
stay in place. Whether a game runs faster or draws less is measured on a Thor, not here.
- No recipe appends a compiler flag with no space: Azahar's `CXXFLAGS+=-fpch-preprocess` turned the toolchain's last
  flag into `-DNDEBUG-fpch-preprocess`, so dynarmic and the other bundled libraries were built with asserts on.
- Azahar uses no geometry shaders on Turnip, as on Android (each lit draw had one; they're slow on a tiler)."""
import os
import re
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
STANDALONE = os.path.join(ROOT, "packages", "emulators", "standalone")


def read(*p):
    with open(os.path.join(*p)) as f:
        return f.read()


def added(patch):
    return "\n".join(line[1:] for line in patch.splitlines() if line.startswith("+") and not line.startswith("+++"))


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


azahar = read(STANDALONE, "azahar-sa", "patches", "0004-vulkan-no-geometry-shaders-on-turnip.patch")
assert "vk_instance.h" in azahar and "UseGeometryShaders" not in added(azahar), "the patch should change the body only"
assert re.search(r"return features\.geometryShader && driver_id != vk::DriverIdKHR::eMesaTurnip;", added(azahar)), \
    "Azahar still uses geometry shaders on Turnip"
print("OK")
