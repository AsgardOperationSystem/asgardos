#!/usr/bin/env python3
# spec: VID-1
# gap: Screen filter isn't on RetroArch, melonDS, DSperate, Vita3K, Cemu, mupen64plus, Amiberry, Hatari, VICE, Hypseus or ScummVM yet
"""Run: python -I test_gap_screen_filter.py: every emulator with a screen scaling setting that the next batch covers is in
thor_settings.py's SCREEN_FILTERS (and so in asgard-screen-filter.sh, which test_screen_filter.py ties to it)."""
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ts = open(os.path.join(HERE, "thor_settings.py")).read()
listed = set(re.findall(r'"([a-z0-9-]+)": \[(?:NEAREST|BILINEAR)', ts))
NEXT = {"retroarch", "melonds", "dsperate", "vita3k", "cemu", "mupen64plus", "amiberry", "hatari", "vice", "hypseus",
        "scummvm"}
missing = NEXT - listed
assert not missing, f"no Screen filter yet: {sorted(missing)}"
print("ok")
