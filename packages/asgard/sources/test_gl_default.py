#!/usr/bin/env python3
# spec: GPU-3
# Tree check: the Thor's default OpenGL really is Zink, as its row says: the quirk writes the override and the profile
# exports it. test_runemu.py: the per-game choice over it.
import os

HERE = os.path.dirname(os.path.abspath(__file__))
QUIRK = os.path.join(HERE, "../../hardware/quirks/platforms/SM8550/095-force_zink")
EXPORT = os.path.join(HERE, "../../hardware/quirks/profile.d/999-export")
lines = [line.strip() for line in open(QUIRK) if not line.lstrip().startswith("#")]
assert 'MESA_LOADER_DRIVER_OVERRIDE="zink"' in lines, lines
assert any(line.strip() == "MESA_LOADER_DRIVER_OVERRIDE" for line in open(EXPORT)), "the profile doesn't export it"
print("ok")
