#!/usr/bin/env python3
# spec: CFG-9
"""Tree check: only these files build a per-game key's name (<system>["<rom>"].<key>). Anything else that wants a game's
option goes through get_setting. Which of them read it, and in what order, is test_emulator_choice.py, test_emulator_global.py
and test_option_row_scope.py; get_setting itself is test_get_setting.py."""
import glob
import os
import re

PACKAGES = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../.."))
KNOWN = {"asgard-home/src/backend.cpp",          # Backend::setting: the emulator and core at launch (CFG-11)
         "asgard-home/src/qml/Settings.qml",     # a game's Settings page: it writes these, and shows them
         "asgard-home/src/qml/GameMenu.qml",     # the in-game Performance page, the same
         "asgard/sources/thor_settings.py",      # the SDL panel's game page, the same
         "asgard/autostart/090-asgard-tuning"}   # seeds Firefox's and Moonlight's caps
# A quote-bracket-quote joined to code: '["' + x, [\"$game, f'{s}["{g}"]', in shell, Python, QML and C++.
BUILDS = re.compile(r"""'\["'|"\[\\""|\[\\"\$|\["\$\{|\["\{|\\\[\\"[A-Za-z$]""")
FILES = [p for pattern in ("asgard/sources/*", "asgard/autostart/*", "asgard/sleep.d/*", "asgard-home/src/*.cpp",
                           "asgard-home/src/qml/*.qml", "asgardos/sources/scripts/*", "asgardos/autostart/*",
                           "emulators/standalone/*/scripts/*", "emulators/libretro/*/scripts/*")
         for p in glob.glob(os.path.join(PACKAGES, pattern))
         if os.path.isfile(p) and not os.path.basename(p).startswith("test_")]
assert len(FILES) > 100, len(FILES)
found = set()
for path in FILES:
    with open(path, errors="replace") as f:
        text = f.read()
    # Not arrays and maps in general: a key name has its closing "]. near.
    for line in text.splitlines():
        if BUILDS.search(line) and re.search(r"""\]\.|\\"\]|'"\]|"\]'""", line):
            found.add(os.path.relpath(path, PACKAGES))
assert found <= KNOWN, f"a lookup of a game's option outside get_setting (CFG-9): {sorted(found - KNOWN)}"
assert {"asgard-home/src/backend.cpp", "asgard-home/src/qml/Settings.qml"} <= found, f"this check no longer sees them: {found}"
print("game option lookup: ok")
