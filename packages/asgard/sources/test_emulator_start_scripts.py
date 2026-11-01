#!/usr/bin/env python3
# spec: EMU-4
# gap: cps1, cps2 and cps3 register an AdvanceMame emulator with no package or start_AdvanceMame.sh behind it: picking it can't start.
# Tree check: runemu.sh's start_<core minus -sa>.sh exists for each non-RetroArch core add_emu_core registers, or runemu.sh routes it.
import glob
import os
import re

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../.."))
with open(f"{ROOT}/virtual/emulators/package.mk") as f:
    calls = re.findall(r"^\s*add_emu_core\s+(\S+)\s+(\S+)\s+(\S+)\s+\S+", f.read(), re.M)
assert calls
scripts = {os.path.basename(p) for pattern in ("*/*/*/scripts/start_*.sh", "*/*/scripts/start_*.sh", "*/*/sources/start_*.sh", "*/*/*/*/scripts/start_*.sh",
                                               "*/src/start_*.sh") for p in glob.glob(f"{ROOT}/{pattern}")}
assert "start_azahar.sh" in scripts and "start_mplayer.sh" in scripts and "start_asgard-music.sh" in scripts
# runemu.sh's own routes: mednafen one script for all its cores; Dolphin per platform; ports and windows run the ROM; Heroic's ROMs
# are shell scripts, run directly; vice-sa installs a start_<core>.sh per machine.
ROUTED = {"retroarch", "mednafen", "dolphin", "portmaster", "wine", "heroic", "vicesa"}
missing = sorted({(emu, core) for system, emu, core in calls
                  if emu not in ROUTED and f"start_{core.rsplit('-', 1)[0]}.sh" not in scripts})
assert not missing, missing
