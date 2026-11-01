#!/usr/bin/env python3
# spec: EMU-6
# gap: docs/plans/emulator-versions.md tracks 18 standalone packages; 16 (mupen64plus-sa, hatarisa and "the other small standalones") aren't checked.
# Tree check: every standalone package is in the plan's status table.
import os
import re

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../.."))
with open(f"{REPO}/docs/plans/emulator-versions.md") as f:
    tracked = set(re.findall(r"^\| [^|]+ \| `([\w-]+)` \|", f.read(), re.M))
packages = set(os.listdir(f"{REPO}/packages/emulators/standalone"))
assert tracked and not packages - tracked, sorted(packages - tracked)
