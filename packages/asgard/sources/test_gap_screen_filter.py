#!/usr/bin/env python3
# spec: VID-1
# gap: Screen filter isn't on Amiberry or VICE yet
"""Run: python -I test_gap_screen_filter.py: the emulators with a screen scaling setting still to do are in
thor_settings.py's SCREEN_FILTERS (and so in asgard-screen-filter.sh, which test_screen_filter.py ties to it)."""
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ts = open(os.path.join(HERE, "thor_settings.py")).read()
listed = set(re.findall(r'"([a-z0-9-]+)": \[(?:NEAREST|BILINEAR)', ts))
NEXT = {"amiberry", "vicesa"}
missing = NEXT - listed
assert not missing, f"no Screen filter yet: {sorted(missing)}"
print("ok")
