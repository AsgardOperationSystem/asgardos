#!/usr/bin/env python3
# spec: CFG-9
# requires: file:build/AsgardOS-SM8550.aarch64/toolchain/usr/local/qt6/lib/libQt6Quick.so cmd:cmake
# gap: Settings.qml optionRow does its own lookup (key, then the system's): an unset row says Default while get_setting gives the game system.X, X or global.X
"""A game's option row, with a value only at get_setting's lower scopes. The row must show what the game will get."""
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../../tools/test"))
import home_harness as hh  # noqa: E402
from home_harness import CFG, Root  # noqa: E402

FEATURES = json.dumps([{"key": "ratio", "label": "Ratio", "choices": [["4:3", "4/3"], ["16:9", "16/9"]]}])
with Root() as r:
    r.library()
    r.write(CFG, "global.ratio=4/3\n")
    out = f"{r.path}/.qml"
    shutil.copytree(f"{hh.SRC}/qml", out)
    text = open(f"{out}/Settings.qml").read()
    text = text.replace("backend.exec(", "fakeExec(").replace("    function close() {", """    function fakeExec(cmd, done) { if (done) Qt.callLater(done, %s) }
    function close() {""" % json.dumps(FEATURES))
    open(f"{out}/Settings.qml", "w").write(text)
    # A game's page: Emulator, Core, then Played and Emulator options.
    res = r.run("a start down down down a", env={"ASGARD_HOME_QML": out}, ms=500)
    assert res.shows("Ratio"), res.texts
    assert res.shows("4:3"), res.texts
