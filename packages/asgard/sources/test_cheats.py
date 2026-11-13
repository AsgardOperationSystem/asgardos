#!/usr/bin/env python3
# spec: CHEAT-1
# requires: file:build/AsgardOS-SM8550.aarch64/toolchain/usr/local/qt6/lib/libQt6Quick.so cmd:cmake
"""Run: python -I test_cheats.py  (no Thor): a game's cheats. asgard-cheats.py against a fake database and state: which
database file a ROM gets, a cheat switched on and off by name, and what runemu.sh's apply writes for RetroArch (its
game-specific .cht with the chosen cheats enabled, apply_cheats_after_load for the launch, a user's own file left alone,
ours removed when nothing is on), and for Azahar (the title ID from the ROM's header, Citra's *citra_enabled) PPSSPP (the disc ID from an ISO, CSO or PBP; _C1) melonDS (<rom>.mch) and Eden (a mod folder per build).
Then Home, offscreen: Select > Cheats lists them and A switches one through the
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

# ---- PPSSPP: the disc ID from an ISO, a CSO or a PBP; cheat.db's block, or the game's shipped ini; _C1 on the ones on
import zlib  # noqa: E402


def iso(disc):
    """A minimal ISO9660: the PVD (sector 16), a root directory (18) holding UMD_DATA.BIN (19)."""
    img = bytearray(20 * 2048)
    pvd = 16 * 2048
    img[pvd:pvd + 6] = b"\x01CD001"
    img[pvd + 158:pvd + 162] = (18).to_bytes(4, "little")
    img[pvd + 166:pvd + 170] = (2048).to_bytes(4, "little")
    name = b"UMD_DATA.BIN;1"
    rec = bytearray(33 + len(name) + 1)
    rec[0], rec[32] = len(rec), len(name)
    rec[2:6], rec[10:14] = (19).to_bytes(4, "little"), (32).to_bytes(4, "little")
    rec[33:33 + len(name)] = name
    img[18 * 2048 + 34:18 * 2048 + 34 + len(rec)] = rec          # after a "." record of 34 bytes
    img[18 * 2048] = 34
    img[19 * 2048:19 * 2048 + 20] = (disc + "|0001|G").encode().ljust(20, b"\0")
    return bytes(img)


def cso(data, block=2048):
    blocks = [data[i:i + block] for i in range(0, len(data), block)]
    body, index, at = b"", [], 0x18 + 4 * (len(blocks) + 1)
    for b in blocks:
        z = zlib.compressobj(9, zlib.DEFLATED, -15)
        packed = z.compress(b) + z.flush()
        index.append(at)
        body += packed
        at += len(packed)
    index.append(at)
    head = b"CISO" + (0x18).to_bytes(4, "little") + len(data).to_bytes(8, "little") + block.to_bytes(4, "little") + bytes([1, 0, 0, 0])
    return head + b"".join(i.to_bytes(4, "little") for i in index) + body


def pbp(disc):
    keys = b"DISC_ID\0"
    data = disc.encode() + b"\0"
    sfo = (b"\0PSF" + (0x101).to_bytes(4, "little") + (20 + 16).to_bytes(4, "little")
           + (20 + 16 + len(keys)).to_bytes(4, "little") + (1).to_bytes(4, "little")
           + (0).to_bytes(2, "little") + (0x204).to_bytes(2, "little") + len(data).to_bytes(4, "little")
           + len(data).to_bytes(4, "little") + (0).to_bytes(4, "little") + keys + data)
    head = b"\0PBP" + (0x10000).to_bytes(4, "little") + (0x28).to_bytes(4, "little") + (0x28 + len(sfo)).to_bytes(4, "little")
    return head.ljust(0x28, b"\0") + sfo


with tempfile.TemporaryDirectory() as tmp:
    env = setup(tmp)
    env.update(ASGARD_CHEATS_PSP_DB=f"{tmp}/pspdb", ASGARD_CHEATS_PSP_OUT=f"{tmp}/psp")
    os.makedirs(f"{tmp}/pspdb")
    open(f"{tmp}/pspdb/cheat.db", "w").write(
        "_S ULJM-05000\n_G Other\n_C0 Nope\n_L 0x1 0x1\n"
        "_S ULUS-10041\n_G Liberty City\n_C0 Max Money\n_L 0x20000000 0x0098967F\n_C0 No Police\n_L 0x20000004 0x00000000\n")
    open(f"{tmp}/pspdb/NPEG00023.ini", "w").write("_S NPEG-00023\n_G GoW\n_C0 60 FPS\n_L 0xE00E003C 0x10003800\n")
    for name, data in (("LCS.iso", iso("ULUS-10041")), ("LCS.cso", cso(iso("ULUS-10041"))), ("LCS.pbp", pbp("ULUS10041"))):
        open(f"{tmp}/{name}", "wb").write(data)
        listed = run(env, "list", "psp", f"{tmp}/{name}", "ppsspp", "ppsspp-sa")
        assert [c["name"] for c in listed["cheats"]] == ["Max Money", "No Police"], (name, listed)
    psp = ("psp", f"{tmp}/LCS.cso", "ppsspp", "ppsspp-sa")
    run(env, "set", *psp, "No Police", "on")
    run(env, "apply", *psp)
    text = open(f"{tmp}/psp/ULUS10041.ini").read()
    assert "_S ULUS-10041" in text and "_C0 Max Money" in text and "_C1 No Police\n_L 0x20000004" in text and "Nope" not in text
    run(env, "set", *psp, "No Police", "off")
    run(env, "apply", *psp)
    assert not os.path.exists(f"{tmp}/psp/ULUS10041.ini")
    # A game with its own shipped ini: that's the list, and the image's first-boot copy is ours to replace
    open(f"{tmp}/GoW.iso", "wb").write(iso("NPEG-00023"))
    gow = ("psp", f"{tmp}/GoW.iso", "ppsspp", "ppsspp-sa")
    shutil.copy(f"{tmp}/pspdb/NPEG00023.ini", f"{tmp}/psp/NPEG00023.ini")
    run(env, "set", *gow, "60 FPS", "on")
    run(env, "apply", *gow)
    assert "_C1 60 FPS" in open(f"{tmp}/psp/NPEG00023.ini").read()
    # One the user changed in PPSSPP is theirs
    open(f"{tmp}/psp/ULUS10041.ini", "w").write("_S ULUS-10041\n_C1 Mine\n_L 0x1 0x1\n")
    run(env, "set", *psp, "Max Money", "on")
    run(env, "apply", *psp)
    assert "Mine" in open(f"{tmp}/psp/ULUS10041.ini").read()
    open(f"{tmp}/x.chd", "wb").write(b"MComprHD")                              # not read yet: no cheats, no crash
    assert run(env, "list", "psp", f"{tmp}/x.chd", "ppsspp", "ppsspp-sa")["error"]

# ---- melonDS: libretro's DS .cht as <rom>.mch beside the ROM, EnableCheats on; emulators with none say what to do
with tempfile.TemporaryDirectory() as tmp:
    env = setup(tmp)
    env["ASGARD_CHEATS_MELONDS_TOML"] = f"{tmp}/melonDS.toml"
    open(f"{tmp}/melonDS.toml", "w").write('[Instance0]\nCheatFilePath = ""\nEnableCheats = false\n')
    os.makedirs(f"{tmp}/db/Nintendo - Nintendo DS")
    open(f"{tmp}/db/Nintendo - Nintendo DS/World Ends with You, The (USA).cht", "w").write(
        'cheats = 2\ncheat0_desc = "Miscellaneous Codes"\n'
        'cheat1_desc = "Debug Menu"\ncheat1_code = "920AE5F0+00000AB1+D2000000+00000000"\ncheat1_enable = false\n')
    os.makedirs(f"{tmp}/roms")
    ds = ("nds", f"{tmp}/roms/World Ends with You, The (USA).nds", "melonds", "melonds-sa")
    assert [c["name"] for c in run(env, "list", *ds)["cheats"]] == ["Debug Menu"]          # the header isn't a cheat
    run(env, "set", *ds, "Debug Menu", "on")
    run(env, "apply", *ds)
    mch = open(f"{tmp}/roms/World Ends with You, The (USA).mch").read()
    assert "CODE 1 Debug Menu\n920AE5F0 00000AB1\nD2000000 00000000\n" in mch and mch.startswith("# Asgard")
    assert "EnableCheats = true" in open(f"{tmp}/melonDS.toml").read()
    run(env, "set", *ds, "Debug Menu", "off")
    run(env, "apply", *ds)
    assert not os.path.exists(f"{tmp}/roms/World Ends with You, The (USA).mch")
    assert "RetroArch (mGBA)" in run(env, "list", "gba", "/r/x.gba", "nanoboyadvance", "nanoboyadvance-sa")["error"]

# ---- Eden: the title ID from the name or an NSP's ticket, a mod folder with only the chosen cheats for every build
with tempfile.TemporaryDirectory() as tmp:
    env = setup(tmp)
    env["ASGARD_CHEATS_EDEN_LOAD"] = f"{tmp}/load"
    os.makedirs(f"{tmp}/asgard-db/switch")
    json.dump({"09A15C8259828A41": {"[max rupee]": "[max rupee]\n04000000 0173D27C B91B990A\n",
                                    "[max hp]": "[max hp]\n04000000 01111111 00000014\nnot a code line\n",
                                    "notes.txt": ""},
               "1234567890ABCDEF": {"[max rupee]": "{Master}\n580F0000 00000001\n[max rupee]\n04000000 0AAAAAAA 0000270F\n"}},
              open(f"{tmp}/asgard-db/switch/01008CF01BAAC000.json", "w"))
    sw = ("switch", "/r/Zelda Echoes of Wisdom [01008CF01BAAC000][EUR].nsp", "eden", "eden-sa")
    assert [c["name"] for c in run(env, "list", *sw)["cheats"]] == ["max rupee", "max hp"]   # no notes, no master
    run(env, "set", *sw, "max hp", "on")
    run(env, "apply", *sw)
    mod = f"{tmp}/load/01008CF01BAAC000/Asgard Cheats/cheats"
    assert os.listdir(mod) == ["09A15C8259828A41.txt"]                                    # only builds with it
    assert open(f"{mod}/09A15C8259828A41.txt").read() == "[max hp]\n04000000 01111111 00000014\n\n"   # stray line gone
    run(env, "set", *sw, "max rupee", "on")
    run(env, "apply", *sw)
    assert open(f"{mod}/1234567890ABCDEF.txt").read().startswith("{Master}\n580F0000 00000001\n\n[max rupee]")
    assert "max rupee" in open(f"{mod}/09A15C8259828A41.txt").read()
    for name in ("max hp", "max rupee"):
        run(env, "set", *sw, name, "off")
    run(env, "apply", *sw)
    assert not os.path.exists(f"{tmp}/load/01008CF01BAAC000/Asgard Cheats")
    # No ID in the name: an NSP's ticket names it; an update's ID shares the base game's cheats
    tik = b"01008CF01BAAC0000000000000000000.tik\0"
    nsp = b"PFS0" + (1).to_bytes(4, "little") + len(tik).to_bytes(4, "little") + bytes(4) + bytes(24) + tik
    open(f"{tmp}/Echoes.nsp", "wb").write(nsp)
    assert run(env, "list", "switch", f"{tmp}/Echoes.nsp", "eden-duo", "eden-duo-sa")["source"] == "01008CF01BAAC000.json"
    assert run(env, "list", "switch", "/r/Echoes [01008CF01BAAC800].nsp", "eden", "eden-sa")["source"] == "01008CF01BAAC000.json"

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
