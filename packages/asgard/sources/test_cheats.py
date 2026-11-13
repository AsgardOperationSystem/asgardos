#!/usr/bin/env python3
# spec: CHEAT-1
# requires: file:build/AsgardOS-SM8550.aarch64/toolchain/usr/local/qt6/lib/libQt6Quick.so cmd:cmake
"""Run: python -I test_cheats.py  (no Thor): a game's cheats. asgard-cheats.py against a fake database and state: which
database file a ROM gets, a cheat switched on and off by name, and what runemu.sh's apply writes for RetroArch (its
game-specific .cht with the chosen cheats enabled, apply_cheats_after_load for the launch, a user's own file left alone,
ours removed when nothing is on), and for Azahar (the title ID from the ROM's header, Citra's *citra_enabled). Then Home, offscreen: Select > Cheats lists them and A switches one through the
script. That a cheat works in a game is a human check."""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "asgard-cheats.py")
sys.path.insert(0, os.path.join(HERE, "../../../tools/test"))

GBA = "Nintendo - Game Boy Advance"
CHT = """cheats = 2

cheat0_desc = "Infinite HP"
cheat0_code = "AAAA+0001"
cheat0_enable = false

cheat1_desc = "All Items"
cheat1_code = "BBBB+0002"
cheat1_enable = false
"""


def setup(tmp):
    env = dict(os.environ, ASGARD_CHEATS_STATE=f"{tmp}/state", ASGARD_CHEATS_RA_DB=f"{tmp}/db",
               ASGARD_CHEATS_RA_OUT=f"{tmp}/out", ASGARD_CHEATS_RA_CORES=f"{tmp}/cores",
               ASGARD_CHEATS_RA_APPEND=f"{tmp}/append.cfg", ASGARD_CHEATS_DB=f"{tmp}/asgard-db",
               ASGARD_CHEATS_AZAHAR_OUT=f"{tmp}/azahar")
    os.makedirs(f"{tmp}/db/{GBA}")
    for name in ("Metroid Fusion (USA).cht", "Metroid Fusion (Europe) (En,Fr,De,Es,It).cht",
                 "Pokemon - Ruby Version (USA).cht", "Pokemon - Sapphire Version (USA).cht"):
        open(f"{tmp}/db/{GBA}/{name}", "w").write(CHT)
    os.makedirs(f"{tmp}/cores")
    open(f"{tmp}/cores/mgba_libretro.info", "w").write('display_name = "GBA (mGBA)"\ncorename = "mGBA"\n')
    open(f"{tmp}/append.cfg", "w").write("")
    return env


def run(env, *args):
    proc = subprocess.run([sys.executable, "-I", SCRIPT, *args], env=env, capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout) if proc.stdout.strip() else None


with tempfile.TemporaryDirectory() as tmp:
    env = setup(tmp)
    rom = "/storage/roms/gba/Metroid Fusion (USA).gba"
    ra = ("gba", rom, "retroarch", "mgba")

    # The database file: the ROM's exact name; else the same title, preferring its region; never a sibling version
    listed = run(env, "list", *ra)
    assert listed["source"] == "Metroid Fusion (USA).cht" and [c["name"] for c in listed["cheats"]] == ["Infinite HP", "All Items"]
    assert not any(c["on"] for c in listed["cheats"])
    assert run(env, "list", "gba", "/r/Metroid Fusion (Europe).gba", "retroarch", "mgba")["source"].startswith("Metroid Fusion (Europe)")
    assert run(env, "list", "gba", "/r/metroid fusion.gba", "retroarch", "mgba")["source"].startswith("Metroid Fusion")
    assert run(env, "list", "gba", "/r/Pokemon - Emerald Version (USA).gba", "retroarch", "mgba")["error"]
    assert run(env, "list", "gba", "/r/Pokemon - Ruby Version (USA).gba", "retroarch", "mgba")["source"].startswith("Pokemon - Ruby")
    assert "yet" in run(env, "list", "gba", rom, "someemu", "x")["error"]

    # On and off by name, kept per game
    on = run(env, "set", *ra, "Infinite HP", "on")
    assert [c["on"] for c in on["cheats"]] == [True, False]
    assert json.load(open(f"{tmp}/state/gba/Metroid Fusion (USA).gba.json")) == {"on": ["Infinite HP"]}

    # Apply: RetroArch's game-specific file under its core name, the chosen cheat enabled, applied after load
    run(env, "apply", *ra)
    out = f"{tmp}/out/mGBA/Metroid Fusion (USA).cht"
    text = open(out).read()
    assert "cheat0_enable = true" in text and "cheat1_enable = false" in text and 'cheat0_code = "AAAA+0001"' in text
    assert 'apply_cheats_after_load = "true"' in open(f"{tmp}/append.cfg").read()

    # All off: our file goes, so RetroArch applies nothing; the state file goes too
    run(env, "set", *ra, "Infinite HP", "off")
    assert not os.path.exists(f"{tmp}/state/gba/Metroid Fusion (USA).gba.json")
    run(env, "apply", *ra)
    assert not os.path.exists(out)

    # A file the user saved from RetroArch's own menu is theirs: never replaced, never removed
    open(out, "w").write("cheats = 1\ncheat0_desc = \"Mine\"\ncheat0_enable = true\n")
    run(env, "set", *ra, "All Items", "on")
    run(env, "apply", *ra)
    assert open(out).read().startswith("cheats = 1\ncheat0_desc = \"Mine\"")
    run(env, "set", *ra, "All Items", "off")
    run(env, "apply", *ra)
    assert os.path.exists(out)

# ---- Azahar: by the title ID in the ROM's header, Sharkive's file, *citra_enabled under the ones on
with tempfile.TemporaryDirectory() as tmp:
    env = setup(tmp)
    rom = f"{tmp}/Zelda.3ds"
    head = bytearray(0x200)
    head[0x100:0x104] = b"NCSD"
    head[0x108:0x110] = (0x0004000000033500).to_bytes(8, "little")
    open(rom, "wb").write(bytes(head))
    os.makedirs(f"{tmp}/asgard-db/3ds")
    open(f"{tmp}/asgard-db/3ds/0004000000033500.txt", "w").write(
        "[500 Rupees]\n1050AF88 000001F4\n\n[Always max health]\nDA000000 0058799A\nD2000000 00000000\n")
    az = ("3ds", rom, "azahar", "azahar-sa")
    assert [c["name"] for c in run(env, "list", *az)["cheats"]] == ["500 Rupees", "Always max health"]
    run(env, "set", *az, "Always max health", "on")
    run(env, "apply", *az)
    out = f"{tmp}/azahar/0004000000033500.txt"
    text = open(out).read()
    assert "[Always max health]\n*citra_enabled\nDA000000 0058799A" in text
    assert "[500 Rupees]\n1050AF88 000001F4" in text and text.count("*citra_enabled") == 1
    run(env, "set", *az, "Always max health", "off")
    run(env, "apply", *az)
    assert not os.path.exists(out)
    open(out, "w").write("[Mine]\n*citra_enabled\n00000000 00000000\n")    # made in Azahar: left alone
    run(env, "set", *az, "500 Rupees", "on")
    run(env, "apply", *az)
    assert open(out).read().startswith("[Mine]")
    open(f"{tmp}/plain.3ds", "wb").write(b"\0" * 0x200)                         # no header: no cheats, no crash
    assert run(env, "list", "3ds", f"{tmp}/plain.3ds", "azahar", "azahar-sa")["error"]

# ---- Home: Select > Cheats, and A on a cheat runs the script's set
import home_harness as hh  # noqa: E402
from home_harness import Root  # noqa: E402

LISTING = {"source": "Metroid Fusion (USA).cht", "cheats": [{"name": "Infinite HP", "on": False},
                                                            {"name": "All Items", "on": True}]}


def copy(root):
    out = f"{root.path}/.qml"
    shutil.rmtree(out, ignore_errors=True)
    shutil.copytree(f"{hh.SRC}/qml", out)
    text = open(f"{out}/Settings.qml").read()
    text = text.replace("backend.exec(", "fakeExec(")
    text = text.replace("    function close() {", """    function fakeExec(cmd, done) {
        console.log("exec: " + cmd)
        const out = /asgard-cheats.py (list|set)/.test(cmd) ? %s : ""
        if (done) Qt.callLater(done, out)
    }
    function close() {""" % json.dumps(json.dumps(LISTING)), 1)
    open(f"{out}/Settings.qml", "w").write(text)
    return {"ASGARD_HOME_QML": out}


with Root() as r:
    r.library()
    assert r.run("a select", ms=300).shows("Cheats")                               # in the game's actions
    page = r.run("a select down a", env=copy(r), ms=400)
    assert page.shows("Infinite HP") and page.shows("All Items") and page.shows("1 on")
    assert "asgard-cheats.py list 'gba' '/storage/roms/gba/Metroid.gba' 'retroarch' 'mgba'" in page.log
    flip = r.run("a select down a down a", env=copy(r), ms=400)                    # the first cheat: on
    assert "asgard-cheats.py set 'gba' '/storage/roms/gba/Metroid.gba' 'retroarch' 'mgba' 'Infinite HP' on" in flip.log
    assert r.run("a start", env=copy(r), ms=300).shows("Cheats")                   # also on the game's own page

# runemu.sh applies them before every launch
runemu = open(os.path.join(HERE, "../../asgardos/sources/scripts/runemu.sh")).read()
assert 'asgard-cheats.py apply "${PLATFORM}" "${ROMNAME}" "${EMULATOR}" "${CORE}"' in runemu
print("OK")
