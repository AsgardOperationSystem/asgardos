#!/usr/bin/env python3
# spec: CHEAT-1
# requires: file:build/AsgardOS-SM8550.aarch64/toolchain/usr/local/qt6/lib/libQt6Quick.so cmd:cmake
"""Run: python -I test_cheats.py  (no Thor): a game's cheats. asgard-cheats.py against a fake database and state: which
database file a ROM gets, a cheat switched on and off by name, and what runemu.sh's apply writes for RetroArch (its
game-specific .cht with the chosen cheats enabled, apply_cheats_after_load for the launch, a user's own file left alone,
ours removed when nothing is on), and for Azahar (the title ID from the ROM's header, Citra's *citra_enabled) PPSSPP (the disc ID from an ISO, CSO or PBP; _C1) melonDS (<rom>.mch), Eden (a mod folder per build) and
Dolphin (the [*_Enabled] lines of its game ini).
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
import re  # noqa: E402
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

# ---- Dolphin: the game ID from the disc, the image's GameSettings codes, only [*_Enabled] lines changed in the user's ini
GM4 = """# GM4E01 - Mario Kart: Double Dash!!

[OnFrame]
[ActionReplay]
# Add action replay cheats here.
$Everything Unlocked
023BC1C0 0003FFFF
$Tiny Karts
043D45A4 3F000000
[Gecko]
$Fix Something [Dolphin]
04000000 00000000
$Moon Jump [kiwi]
*Hold B
C2000000 00000001
60000000 00000000
[Gecko_Enabled]
$Fix Something
"""
with tempfile.TemporaryDirectory() as tmp:
    env = setup(tmp)
    env.update(ASGARD_CHEATS_DOLPHIN_DB=f"{tmp}/sys", ASGARD_CHEATS_DOLPHIN_OUT=f"{tmp}/user",
               ASGARD_CHEATS_ON_FLAG=f"{tmp}/on")
    os.makedirs(f"{tmp}/sys")
    open(f"{tmp}/sys/GM4E01.ini", "w").write(GM4)
    disc = b"GM4E01" + bytes(0x16) + bytes.fromhex("C2339F3D")
    rvz = b"RVZ\x01".ljust(0x58, b"\0") + b"GM4E01"
    wbfs = b"WBFS" + bytes(4) + bytes([9]) + bytes(0x200 - 9) + b"GM4E01"
    ciso = b"CISO".ljust(0x8000, b"\0") + b"GM4E01"
    block = zlib.compress(disc.ljust(0x8000, b"\0"))
    gcz = (bytes.fromhex("01C00BB1") + bytes(0x18) + (2).to_bytes(4, "little") + (0).to_bytes(8, "little")
           + len(block).to_bytes(8, "little") + bytes(8) + block + b"x")
    for name, data in (("MKDD.iso", disc), ("MKDD.rvz", rvz), ("MKDD.wbfs", wbfs), ("MKDD.ciso", ciso), ("MKDD.gcz", gcz)):
        open(f"{tmp}/{name}", "wb").write(data)
        listed = run(env, "list", "gamecube", f"{tmp}/{name}", "dolphin", "dolphin-sa-gc")
        assert [c["name"] for c in listed["cheats"]] == ["Everything Unlocked", "Tiny Karts", "Moon Jump"], (name, listed)
    gc = ("gamecube", f"{tmp}/MKDD.rvz", "dolphin", "dolphin-sa-gc")
    # No user ini yet: Dolphin's first-start copy of the image's, with ours enabled; the start script's flag set
    run(env, "set", *gc, "Moon Jump", "on")
    run(env, "apply", *gc)
    ini = open(f"{tmp}/user/GM4E01.ini").read()
    assert "[Gecko_Enabled]\n$Fix Something\n$Moon Jump\n" in ini and "$Tiny Karts\n043D45A4" in ini, ini
    assert "[ActionReplay_Enabled]" not in ini and os.path.exists(f"{tmp}/on")
    # The user's ini, with their own settings and a cheat they switched on in Dolphin: both stay
    open(f"{tmp}/user/GM4E01.ini", "w").write("[Video_Settings]\nSafeTextureCacheSize = 0\n"
                                              "[ActionReplay_Enabled]\n$Everything Unlocked\n[ActionReplay_Disabled]\n$Tiny Karts\n")
    run(env, "set", *gc, "Tiny Karts", "on")
    run(env, "apply", *gc)
    ini = open(f"{tmp}/user/GM4E01.ini").read()
    assert "SafeTextureCacheSize = 0" in ini and "[ActionReplay_Enabled]\n$Everything Unlocked\n$Tiny Karts\n" in ini, ini
    assert "[ActionReplay_Disabled]\n$Tiny" not in ini and "$Tiny Karts\n043D45A4 3F000000" in ini         # code added
    assert "$Moon Jump [kiwi]\n*Hold B\nC2000000" in ini and "[Gecko_Enabled]\n$Moon Jump" in ini
    # Off: ours go, theirs stay, and no flag
    for name in ("Tiny Karts", "Moon Jump"):
        run(env, "set", *gc, name, "off")
    run(env, "apply", *gc)
    ini = open(f"{tmp}/user/GM4E01.ini").read()
    enabled = re.findall(r"\[(\w+_Enabled)\]\n((?:\$.*\n)*)", ini)
    assert enabled == [("ActionReplay_Enabled", "$Everything Unlocked\n"), ("Gecko_Enabled", "")] and "Asgard" not in ini, ini
    assert not os.path.exists(f"{tmp}/on")
    assert run(env, "list", "gamecube", f"{tmp}/sys/GM4E01.ini", "dolphin", "dolphin-sa-gc")["error"]   # not a disc

# ---- ARMSX2: serial and ELF CRC from SYSTEM.CNF's BOOT2; <serial>_ASGARD.pnach with only the chosen, unlabelled
def iso_files(files):
    """An ISO9660 with these files in its root, in sectors 19 on."""
    sectors, recs, lba = [], b"", 19
    for name, data in files:
        ident = (name + ";1").encode()
        rec = bytearray(33 + len(ident) + (len(ident) + 1) % 2)
        rec[0], rec[32] = len(rec), len(ident)
        rec[2:6], rec[10:14] = lba.to_bytes(4, "little"), len(data).to_bytes(4, "little")
        rec[33:33 + len(ident)] = ident
        recs += bytes(rec)
        n = max(1, (len(data) + 2047) // 2048)
        sectors.append(data.ljust(n * 2048, b"\0"))
        lba += n
    img = bytearray(16 * 2048) + bytearray(2048) + bytearray(2048) + bytes([34]).ljust(34, b"\0") + recs
    img[16 * 2048:16 * 2048 + 6] = b"\x01CD001"
    img[16 * 2048 + 158:16 * 2048 + 162] = (18).to_bytes(4, "little")
    img[16 * 2048 + 166:16 * 2048 + 170] = (2048).to_bytes(4, "little")
    return bytes(img.ljust(19 * 2048, b"\0")) + b"".join(sectors)


def raw_bin(iso, mode=2):
    out = b""
    for i in range(0, len(iso), 2048):
        head = b"\0" + b"\xff" * 10 + b"\0" + bytes([0, 2, 0, mode])
        out += head + (bytes(8) if mode == 2 else b"") + iso[i:i + 2048] + bytes(2352 - 2048 - len(head) - (8 if mode == 2 else 0))
    return out


with tempfile.TemporaryDirectory() as tmp:
    env = setup(tmp)
    env.update(ASGARD_CHEATS_PS2_OUT=f"{tmp}/cheats", ASGARD_CHEATS_PS2_INI=f"{tmp}/inis/PCSX2.ini",
               ASGARD_CHEATS_PS2_INI_IMAGE=f"{tmp}/PCSX2.ini", ASGARD_CHEATS_ON_FLAG=f"{tmp}/on")
    open(f"{tmp}/PCSX2.ini", "w").write("[EmuCore]\nEnablePatches = true\nEnableCheats = false\n")
    elf = (0x11223344).to_bytes(4, "little") + (0x01020304).to_bytes(4, "little") + b"\x7f"    # CRC 0x10203040
    cnf = b"BOOT2 = cdrom0:\\SLUS_208.88;1\r\nVER = 1.00\r\n"
    disc = iso_files([("SLUS_208.88", elf), ("SYSTEM.CNF", cnf)])
    os.makedirs(f"{tmp}/asgard-db/ps2")
    open(f"{tmp}/asgard-db/ps2/SLUS-20888_10203040.pnach", "w").write(
        "gametitle=Front Mission 4 [SLUS-20888] [10203040]\n\n[Infinite Health]\nauthor=x\n// Infinite Health\n"
        "patch=1,EE,9012D8C4,extended,0C04C9D4\n\n[Infinite Funds]\npatch=1,EE,103B6200,extended,0000FFFF\n\n"
        "[Infinite Funds]\npatch=1,EE,103B7224,extended,0000FFFF\n\n[Empty]\nauthor=x\n")
    for name, data in (("FM4.iso", disc), ("FM4.bin", raw_bin(disc)), ("FM4 m1.bin", raw_bin(disc, 1)), ("FM4.cso", cso(disc))):
        open(f"{tmp}/{name}", "wb").write(data)
        listed = run(env, "list", "ps2", f"{tmp}/{name}", "armsx2", "armsx2-sa")
        assert [c["name"] for c in listed["cheats"]] == ["Infinite Health", "Infinite Funds"], (name, listed)
    ps2 = ("ps2", f"{tmp}/FM4.bin", "armsx2", "armsx2-sa")
    run(env, "set", *ps2, "Infinite Funds", "on")
    run(env, "apply", *ps2)
    pnach = open(f"{tmp}/cheats/SLUS-20888_ASGARD.pnach").read()
    assert "[" not in pnach and "patch=1,EE,103B6200" in pnach and "patch=1,EE,103B7224" in pnach and "9012D8C4" not in pnach
    assert "EnableCheats = true" in open(f"{tmp}/inis/PCSX2.ini").read() and os.path.exists(f"{tmp}/on")
    run(env, "set", *ps2, "Infinite Funds", "off")
    run(env, "apply", *ps2)
    assert not os.path.exists(f"{tmp}/cheats/SLUS-20888_ASGARD.pnach") and not os.path.exists(f"{tmp}/on")
    # AetherSX2: the same cheats as cheats/<CRC>.pnach; one the user made there is theirs
    env["ASGARD_CHEATS_AETHER"] = f"{tmp}/aether"
    os.makedirs(f"{tmp}/aether/inis")
    open(f"{tmp}/aether/inis/PCSX2.ini", "w").write("EnableCheats = false\n")
    aeth = ("ps2", f"{tmp}/FM4.iso", "aethersx2", "aethersx2-sa")
    run(env, "set", *aeth, "Infinite Health", "on")
    run(env, "apply", *aeth)
    assert "9012D8C4" in open(f"{tmp}/aether/cheats/10203040.pnach").read()
    assert "EnableCheats = true" in open(f"{tmp}/aether/inis/PCSX2.ini").read()
    open(f"{tmp}/aether/cheats/10203040.pnach", "w").write("patch=1,EE,mine\n")
    run(env, "apply", *aeth)
    assert open(f"{tmp}/aether/cheats/10203040.pnach").read() == "patch=1,EE,mine\n"

# ---- Mednafen: libretro's codes decoded into cheats/<module>.cht, a section keyed by the MD5 Mednafen computes
import hashlib  # noqa: E402
import zipfile  # noqa: E402

with tempfile.TemporaryDirectory() as tmp:
    env = setup(tmp)
    env["ASGARD_CHEATS_MEDNAFEN_OUT"] = f"{tmp}/mcheats"
    gbdir, nesdir = f"{tmp}/db/Nintendo - Game Boy", f"{tmp}/db/Nintendo - Nintendo Entertainment System"
    os.makedirs(gbdir)
    os.makedirs(nesdir)
    open(f"{gbdir}/Tetris (World).cht", "w").write(
        'cheats = 4\ncheat0_desc = "Codes"\ncheat1_desc = "Lives"\ncheat1_code = "010F1AC0"\n'
        'cheat2_desc = "Level"\ncheat2_code = "00A-17B-C49+010F1AC0"\ncheat3_desc = "Bad"\ncheat3_code = "ZZZZ"\n')
    open(f"{nesdir}/Super Mario Bros. (World).cht", "w").write(
        'cheats = 2\ncheat0_desc = "Infinite Lives"\ncheat0_code = "SXIOPO"\ncheat1_desc = "Coins"\ncheat1_code = "075E:09"\n')
    gb = bytearray(0x8000)                           # header 0x148 = 0: 32 KiB; a short file is padded with FF
    os.makedirs(f"{tmp}/roms")
    open(f"{tmp}/roms/Tetris (World).gb", "wb").write(bytes(gb[:0x6000]))
    gbmd5 = hashlib.md5(bytes(gb[:0x6000]).ljust(0x8000, b"\xff")).hexdigest()
    tet = ("gb", f"{tmp}/roms/Tetris (World).gb", "mednafen", "gb")
    assert [c["name"] for c in run(env, "list", *tet)["cheats"]] == ["Lives", "Level"]    # no header, no bad code
    run(env, "set", *tet, "Level", "on")
    run(env, "apply", *tet)
    cht = open(f"{tmp}/mcheats/gb.cht").read()
    assert cht.startswith(f"[{gbmd5}] Asgard cheats")
    assert "C A 1 L 0 00004a17 00 c8 Level\n\nR A 1 L 0 0000c01a 0f Level\n\n" in cht, cht
    # Another game's section stays; a section the user made for this game is theirs
    open(f"{tmp}/mcheats/gb.cht", "a").write("[0123456789abcdef0123456789abcdef] Other\nR A 1 L 0 00000001 01 x\n\n")
    run(env, "set", *tet, "Level", "off")
    run(env, "apply", *tet)
    assert open(f"{tmp}/mcheats/gb.cht").read() == "[0123456789abcdef0123456789abcdef] Other\nR A 1 L 0 00000001 01 x\n\n"
    open(f"{tmp}/mcheats/gb.cht", "a").write(f"[{gbmd5}] Tetris\nR A 1 L 0 00000002 02 mine\n\n")
    run(env, "set", *tet, "Lives", "on")
    run(env, "apply", *tet)
    assert "Asgard" not in open(f"{tmp}/mcheats/gb.cht").read()
    # NES: the MD5 of PRG+CHR without the iNES header, read from a .zip; Game Genie and a RAM write
    prg = bytes(range(256)) * 64
    with zipfile.ZipFile(f"{tmp}/roms/Super Mario Bros. (World).zip", "w") as z:
        z.writestr("readme.txt", "hi")
        z.writestr("smb.nes", b"NES\x1a\x01\x00" + bytes(10) + prg)
    smb = ("nes", f"{tmp}/roms/Super Mario Bros. (World).zip", "mednafen", "nes")
    for name in ("Infinite Lives", "Coins"):
        run(env, "set", *smb, name, "on")
    run(env, "apply", *smb)
    cht = open(f"{tmp}/mcheats/nes.cht").read()
    assert cht.startswith(f"[{hashlib.md5(prg).hexdigest()}] Asgard")
    assert "S A 1 L 0 000091d9 ad Infinite Lives\n\nR A 1 L 0 0000075e 09 Coins\n" in cht, cht
    assert "RetroArch" in run(env, "list", "atarilynx", "/r/x.lnx", "mednafen", "lynx")["error"]

# ---- Flycast: libretro's Dreamcast .cht in a folder of ours on its CheatPath, <rom file name>.cht
with tempfile.TemporaryDirectory() as tmp:
    env = setup(tmp)
    env.update(ASGARD_CHEATS_FLYCAST_CFG=f"{tmp}/emu.cfg", ASGARD_CHEATS_FLYCAST_OUT=f"{tmp}/fc")
    open(f"{tmp}/emu.cfg", "w").write("[audio]\nbackend = pulse\n\n[config]\npvr.AutoSkipFrame = 2\n")
    os.makedirs(f"{tmp}/db/Sega - Dreamcast")
    open(f"{tmp}/db/Sega - Dreamcast/Crazy Taxi (USA).cht", "w").write(
        'cheats = 2\ncheat0_desc = "Time"\ncheat0_address = "1691412"\ncheat0_value = "99"\ncheat0_enable = "false"\n'
        'cheat1_desc = "Money"\ncheat1_address = "1691416"\ncheat1_value = "9999"\ncheat1_enable = "false"\n')
    dc = ("dreamcast", "/r/Crazy Taxi (USA).chd", "flycast", "flycast-sa")
    assert [c["name"] for c in run(env, "list", *dc)["cheats"]] == ["Time", "Money"]
    run(env, "set", *dc, "Money", "on")
    run(env, "apply", *dc)
    cht = open(f"{tmp}/fc/Crazy Taxi (USA).chd.cht").read()
    assert cht.startswith(";") and "cheat1_enable = true" in cht and "cheat0_enable = false" in cht
    cfg = open(f"{tmp}/emu.cfg").read()
    assert f"[config]\nDreamcast.CheatPath = {tmp}/fc\n" in cfg
    open(f"{tmp}/emu.cfg", "w").write("[config]\nDreamcast.CheatPath = /mine\n")
    run(env, "apply", *dc)
    assert f"Dreamcast.CheatPath = /mine;{tmp}/fc\n" in open(f"{tmp}/emu.cfg").read()
    run(env, "set", *dc, "Money", "off")
    run(env, "apply", *dc)
    assert not os.path.exists(f"{tmp}/fc/Crazy Taxi (USA).chd.cht")

# ---- mupen64plus: its mupencheat.txt by the header's CRCs (any byte order), else libretro's; a one-game file
with tempfile.TemporaryDirectory() as tmp:
    env = setup(tmp)
    env.update(ASGARD_CHEATS_N64_DB=f"{tmp}/mupencheat.txt", ASGARD_CHEATS_N64_OUT=f"{tmp}/n64.txt",
               ASGARD_CHEATS_ON_FLAG=f"{tmp}/on")
    open(f"{tmp}/mupencheat.txt", "w").write(
        "crc 11111111-22222222-C:4A\ngn Other\n cn Nope\n  80000000 0001\n"
        "crc 80F41131-384645F6-C:4A\ngn AeroGauge (J)\n//----\n cn No Damage\\Player 1\n  50000402 0000\n  8113D058 0000\n"
        " cn Laps\n  cd How many\n  8013CD0E ???? 0001:\"1 Lap\",0002:\"2 Laps\"\n")
    z64 = bytes.fromhex("80371240") + bytes(12) + bytes.fromhex("80F41131384645F6") + bytes(0x26) + b"J\0"
    v64 = b"".join(z64[i + 1:i + 2] + z64[i:i + 1] for i in range(0, 0x40, 2))
    n64 = b"".join(z64[i:i + 4][::-1] for i in range(0, 0x40, 4))
    for name, data in (("Aero.z64", z64), ("Aero.v64", v64), ("Aero.n64", n64)):
        open(f"{tmp}/{name}", "wb").write(data)
        names = [c["name"] for c in run(env, "list", "n64", f"{tmp}/{name}", "mupen64plus", "mupen64plus-sa")["cheats"]]
        assert names == ["No Damage\\Player 1", "Laps: 1 Lap", "Laps: 2 Laps"], (name, names)
    aero = ("n64", f"{tmp}/Aero.v64", "mupen64plus", "mupen64plus-sa")
    run(env, "set", *aero, "Laps: 2 Laps", "on")
    run(env, "apply", *aero)
    assert open(f"{tmp}/n64.txt").read() == "crc 80F41131-384645F6-C:4A\ngn Aero.v64\n cn Laps: 2 Laps\n  8013CD0E 0002\n"
    assert os.path.exists(f"{tmp}/on")
    # Not in mupen64plus's database: libretro's N64 file by name
    os.makedirs(f"{tmp}/db/Nintendo - Nintendo 64")
    open(f"{tmp}/db/Nintendo - Nintendo 64/Mario Kart 64 (USA).cht", "w").write(
        'cheats = 1\ncheat0_desc = "Lives"\ncheat0_code = "81103B66 0021;50000D01 0000"\n')
    mk = bytes.fromhex("80371240") + bytes(12) + bytes.fromhex("3E5055B6") + bytes(0x2A) + b"E\0"
    open(f"{tmp}/Mario Kart 64 (USA).z64", "wb").write(mk)
    mk64 = ("n64", f"{tmp}/Mario Kart 64 (USA).z64", "mupen64plus", "mupen64plus-sa")
    run(env, "set", *mk64, "Lives", "on")
    run(env, "apply", *mk64)
    assert open(f"{tmp}/n64.txt").read().endswith(" cn Lives\n  81103B66 0021\n  50000D01 0000\n")
    run(env, "set", *mk64, "Lives", "off")
    run(env, "apply", *mk64)
    assert not os.path.exists(f"{tmp}/n64.txt") and not os.path.exists(f"{tmp}/on")

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
# mupen64plus's start script hands over the one-game file
m64 = open(os.path.join(HERE, "../../emulators/standalone/mupen64plus-sa/mupen64plus-sa-core/scripts/start_mupen64plus.sh")).read()
assert "cp /tmp/asgard-mupencheat.txt ${TMP}/mupencheat.txt" in m64 and '${SET_PARAMS} ${CHEATS} "${TMP}/${ROM}"' in m64
# and Dolphin's start scripts, which rewrite EnableCheats, keep it on while the game has cheats on
for script in ("start_dolphin_gc.sh", "start_dolphin_wii.sh"):
    text = open(os.path.join(HERE, "../../emulators/standalone/dolphin-sa/scripts", script)).read()
    assert '[ "$ENBCHEATS" = "1" ] || [ -e /tmp/.asgard-cheats-on ]; then' in text, script
print("OK")
