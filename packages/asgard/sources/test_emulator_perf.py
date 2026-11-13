#!/usr/bin/env python3
# spec: EMU-3
# requires: cmd:git
"""Run: python -I test_emulator_perf.py  (no Thor): build flags and source patches that make Azahar and Eden faster on
the Thor stay in place. Whether a game runs faster or draws less is measured on a Thor, not here.
- No recipe appends a compiler flag with no space: Azahar's `CXXFLAGS+=-fpch-preprocess` turned the toolchain's last
  flag into `-DNDEBUG-fpch-preprocess`, so dynarmic and the other bundled libraries were built with asserts on.
- Azahar uses no geometry shaders on Turnip, as on Android (each lit draw had one; they're slow on a tiler).
- Eden's thread priorities become nice values on Linux (SCHED_OTHER's only priority is 0, so they did nothing).
- Eden and Eden Duo count a lone handheld pad as one player when a game's controller applet closes (it got 0, and
  Echoes of Wisdom asked again until Eden ran out of kernel events and crashed)."""
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

eden = read(STANDALONE, "eden-sa", "patches", "0004-common-thread-priorities-as-nice-values.patch")
body = added(eden)
assert "src/common/thread.cpp" in eden
assert re.search(r"setpriority\(PRIO_PROCESS, 0, nice_value\)", body), "Eden's thread priorities aren't set as nice values"
assert "#elif defined(__linux__) && !defined(__ANDROID__)" in body, "the Linux branch must come before the SCHED_OTHER one"
for level, nice in (("Critical", "NICE_AUDIO"), ("VeryHigh", "NICE_URGENT_DISPLAY"), ("High", "NICE_DISPLAY"),
                    ("Low", "NICE_BACKGROUND")):
    assert f"case Common::ThreadPriority::{level}: return {nice};" in body, f"{level} isn't mapped"
assert "RLIMIT_NICE" in body, "a nice value below what RLIMIT_NICE allows would just fail"

for pkg, patch in (("eden-sa", "0005"), ("eden-duo-sa", "0006")):
    applet = read(STANDALONE, pkg, "patches", f"{patch}-am-controller-applet-counts-handheld.patch")
    assert "applet_controller.cpp" in applet, pkg
    assert re.search(r"result_info\.player_count == 0 &&\s+system\.HIDCore\(\)\.GetEmulatedController\("
                     r"Core::HID::NpadIdType::Handheld\)->IsConnected\(\)\) \{\s+result_info\.player_count = 1;",
                     added(applet)), f"{pkg}: a lone handheld pad still counts as 0 players"
print("OK")
