# spec: HOME-2
# requires: file:build/AsgardOS-SM8550.aarch64/toolchain/usr/local/qt6/lib/libQt6Quick.so cmd:cmake
# gap: Home's QML never reads backend.recent, so the home tab has no Recently played
"""Run: python -I test_home_recently_played.py  (no Thor): HOME-2's Recently played, offscreen: a game in the play log
shows on the home tab, under that name, before any console is opened."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../../tools/test"))
from home_harness import Root  # noqa: E402

with Root() as r:
    r.library()
    r.write("storage/.config/thor/playtime.jsonl",
            '{"rom": "/storage/roms/gba/Metroid.gba", "sys": "gba", "start": 1700000000, "secs": 60}\n')
    home = r.run("")
    assert "1 recently played" in home.log, home.log           # the backend has it
    assert home.shows("Recently played") and "Metroid" in home.window("Asgard Home")
print("ok")
