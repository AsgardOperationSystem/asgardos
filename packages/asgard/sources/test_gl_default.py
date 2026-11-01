#!/usr/bin/env python3
# spec: GPU-3
# gap: the SM8550 quirk 095-force_zink exports MESA_LOADER_DRIVER_OVERRIDE=zink for everything, so an unset game may run on Zink while its row says freedreno.
# Tree check: nothing in the Thor's quirks sets a system-wide OpenGL driver, so unset really is freedreno. test_runemu.py: the per-game choice.
import glob
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../hardware/quirks"))
files = glob.glob(f"{ROOT}/platforms/SM8550/*") + glob.glob(f"{ROOT}/devices/AYN Thor/*")
assert files
forced = []
for path in files:
    if os.path.isfile(path):
        with open(path, errors="replace") as f:
            if any("MESA_LOADER_DRIVER_OVERRIDE=" in line and not line.lstrip().startswith("#") for line in f):
                forced.append(os.path.relpath(path, ROOT))
assert not forced, forced
