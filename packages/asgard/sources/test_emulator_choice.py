#!/usr/bin/env python3
# spec: CFG-10 CFG-11
# requires: file:build/AsgardOS-SM8550.aarch64/toolchain/usr/local/qt6/lib/libQt6Quick.so cmd:cmake
"""Asgard Home on the host: which emulator and core a launch resolves (without runemu.sh, Backend::launch logs them), what
picking another one writes, and that an emulator option is stored per system and stays when the emulator changes. CFG-11's
"not global.*" is test_emulator_global.py. A QML copy answers thor_settings.py --features with canned rows."""
import json
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "../../../tools/test"))
import home_harness as hh  # noqa: E402
from home_harness import CFG, Root  # noqa: E402

GBA_KEY = 'gba["Metroid.gba"]'
ES = "usr/config/emulationstation/es_systems.cfg"
# The default core isn't an emulator's first, to tell "reset to the first" from "reset to the default".
SYSTEM = """<systemList><system><name>gba</name><fullname>GBA console</fullname><path>/storage/roms/gba</path>
<extension>.gba</extension><emulators>
<emulator name="retroarch"><cores><core>first-ra</core><core default="true">second-ra</core></cores></emulator>
<emulator name="alt"><cores><core>first-alt</core><core>second-alt</core></cores></emulator>
</emulators></system></systemList>"""
RATIO = {"key": "ratio", "label": "Ratio", "choices": [["4:3", "4/3"], ["16:9", "16/9"]]}
FEATURES = {"--features 'retroarch'": json.dumps([RATIO, {"key": "ra_only", "label": "Only on RetroArch", "choices": [["On", "1"]]}]),
            "--features 'alt'": json.dumps([RATIO, {"key": "alt_only", "label": "Only on Alt", "choices": [["On", "1"]]}])}
OPEN_GAME, PLAY = "a", "a a"                    # the first system, then its first game
CONSOLE = "start down down a a a"               # Settings > Library > Consoles > GBA
GAME_PAGE = f"{OPEN_GAME} start"                # a game's page, on its Emulator row


def launched(root):
    res = root.run(PLAY)
    found = re.findall(r"launch \S+ \(gba\) with (\S*)/(\S*)", res.log)
    assert found, res.log
    return found[-1]


def qml(root):
    out = f"{root.path}/.qml"
    shutil.rmtree(out, ignore_errors=True)
    shutil.copytree(f"{hh.SRC}/qml", out)
    text = open(f"{out}/Settings.qml").read()
    assert "backend.exec(" in text
    text = text.replace("backend.exec(", "fakeExec(").replace("    function close() {", """    readonly property var answers: %s
    function fakeExec(cmd, done) {
        let out = ""
        for (const k in answers) if (cmd.indexOf(k) >= 0) out = answers[k]
        if (done) Qt.callLater(done, out)
    }
    function close() {""" % json.dumps(FEATURES))
    open(f"{out}/Settings.qml", "w").write(text)
    return {"ASGARD_HOME_QML": out}


def values(root):
    return dict(line.split("=", 1) for line in root.read(CFG).splitlines() if "=" in line)


with Root() as r:
    r.library({"gba": ["Metroid.gba", "Zelda.gba"]})
    r.write(ES, SYSTEM)
    # --- CFG-11: the game, then the system, then es_systems.cfg's default.
    TABLE = [("", ("retroarch", "second-ra")),
             ("gba.emulator=alt\ngba.core=second-alt\n", ("alt", "second-alt")),
             (f"gba.emulator=alt\ngba.core=second-alt\n{GBA_KEY}.emulator=retroarch\n{GBA_KEY}.core=first-ra\n",
              ("retroarch", "first-ra")),
             (f"gba.core=second-alt\n{GBA_KEY}.emulator=alt\n", ("alt", "second-alt")),
             # another game's isn't this one's
             ('gba["Zelda.gba"].emulator=alt\ngba["Zelda.gba"].core=second-alt\n', ("retroarch", "second-ra")),
             # empty is unset (CFG-9), so it inherits
             (f"gba.emulator=alt\ngba.core=first-alt\n{GBA_KEY}.emulator=\n{GBA_KEY}.core=\n", ("alt", "first-alt")),
             ("gba.emulator=\ngba.core=\n", ("retroarch", "second-ra")),
             # these scopes are get_setting's, not CFG-11's
             ("system.emulator=alt\nemulator=alt\nsystem.core=first-alt\ncore=first-alt\n", ("retroarch", "second-ra"))]
    for cfg, want in TABLE:
        r.write(CFG, cfg)
        got = launched(r)
        assert got == want, f"{cfg!r}: {got}, want {want}"

    # --- CFG-11: picking another emulator resets the core to that emulator's first. For a game...
    r.write(CFG, "")
    res = r.run(f"{GAME_PAGE} right")
    v = values(r)
    assert v.get(f"{GBA_KEY}.emulator") == "alt" and v.get(f"{GBA_KEY}.core") == "first-alt", v
    assert "gba.emulator" not in v and "gba.core" not in v, v
    assert launched(r) == ("alt", "first-alt")
    # ...which also leaves the old emulator's core behind when going back.
    r.run(f"{GAME_PAGE} right")
    v = values(r)
    assert v.get(f"{GBA_KEY}.emulator") == "retroarch" and v.get(f"{GBA_KEY}.core") == "first-ra", v
    # ...and for a system.
    r.write(CFG, "")
    r.run(f"{CONSOLE} right")
    v = values(r)
    assert v.get("gba.emulator") == "alt" and v.get("gba.core") == "first-alt", v
    assert launched(r) == ("alt", "first-alt")

    # --- CFG-10: an option is <system>.<key>, whatever the emulator; the emulator only picks which rows show.
    r.write(CFG, "")
    env = qml(r)
    options = f"{CONSOLE} down down a"          # RetroArch has two cores: Emulator, Core, Emulator options
    shown = r.run(options, env=env, ms=500)
    assert shown.shows("Only on RetroArch") and not shown.shows("Only on Alt"), shown.texts
    r.run(f"{options} right", env=env, ms=500)
    v = values(r)
    assert v.get("gba.ratio") == "4/3", v
    assert not [k for k in v if "retroarch" in k or "second-ra" in k], v
    r.run(f"{CONSOLE} right", env=env, ms=300)  # the system's emulator changes: the value stays where it is
    v = values(r)
    assert v.get("gba.emulator") == "alt" and v.get("gba.ratio") == "4/3", v
    shown = r.run(f"{CONSOLE} down down a", env=env, ms=500)
    assert shown.shows("Only on Alt") and not shown.shows("Only on RetroArch"), shown.texts
    assert shown.shows("4:3"), shown.texts
print("emulator choice: ok")
