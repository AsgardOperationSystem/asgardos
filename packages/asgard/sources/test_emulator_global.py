#!/usr/bin/env python3
# spec: CFG-11
# requires: file:build/AsgardOS-SM8550.aarch64/toolchain/usr/local/qt6/lib/libQt6Quick.so cmd:cmake
# gap: Backend::setting also reads global.emulator and global.core, between the system and es_systems.cfg's default
"""CFG-11's order has three steps. The rest of it is test_emulator_choice.py."""
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../../tools/test"))
from home_harness import CFG, Root  # noqa: E402

with Root() as r:
    r.library()
    r.write(CFG, "global.emulator=alt\nglobal.core=alt-gba\n")
    found = re.findall(r"launch \S+ \(gba\) with (\S*)/(\S*)", r.run("a a").log)
    assert found == [("retroarch", "mgba")], found
