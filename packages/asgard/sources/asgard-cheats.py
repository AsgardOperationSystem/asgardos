#!/usr/bin/env python3
"""A game's cheats: listed and switched on in Asgard Home (Select on a game > Cheats), written into the game's emulator
just before it starts (runemu.sh). Each cheat is on or off per game; the emulator gets the ones on at the next launch.

  asgard-cheats.py list <system> <rom path> <emulator> <core>      JSON: {"source", "cheats": [{"name", "on"}], "error"}
  asgard-cheats.py set <system> <rom path> <emulator> <core> <name> on|off
  asgard-cheats.py apply <system> <rom path> <emulator> <core>     before the launch: the emulator's own cheat file

The choice is kept per game in STATE/<system>/<rom file>.json ({"on": [names]}), by cheat name, so it survives a
database update that renumbers cheats, and follows the game to another emulator that has the same cheats.
Cheats come from databases shipped in the image (offline):
  RetroArch  libretro-database's cht/<system>/<No-Intro name>.cht; written to <cheat_database_path>/<core>/<rom>.cht,
             RetroArch's game-specific cheat file, with apply_cheats_after_load for that launch.
  Azahar     asgard-cheats-db's 3ds/<title ID>.txt (Sharkive, already Azahar's format); written to Azahar's
             cheats/<title ID>.txt with *citra_enabled under each cheat that's on. The title ID is in the ROM's header.
  PPSSPP     the image's CWCheat database (ppsspp-sa's PSP/Cheats/cheat.db, or a game's own shipped <ID>.ini); written
             to PPSSPP's PSP/Cheats/<disc ID>.ini with _C1 on the ones on. The disc ID is read from the ISO's
             UMD_DATA.BIN (a .cso's blocks are inflated as needed) or a PBP's PARAM.SFO; a .chd isn't read yet.
  melonDS    libretro-database's Nintendo DS .cht (Action Replay); written as <rom>.mch beside the ROM (CheatFilePath
             is empty), with EnableCheats switched on in melonDS.toml.
  DraStic    the same codes as melonDS, written as DraStic's custom cheats/<rom name>.cht ("[name]+" is on).
  SkyEmu     DS: the same codes as melonDS; GB/GBC: libretro's GameShark codes it runs (A000-DFFF writes); written as
             <rom>.code beside the ROM. GBA: none (it takes encrypted Action Replay v3 only).
  Eden       switch-cheats-db's switch/<title ID>.json ({build ID: {"[name]": code}}); written as Eden's mod
             load/<title ID>/Asgard Cheats/cheats/<build ID>.txt for every build ID, with only the cheats that are on
             (Eden runs every cheat in a file it loads, and loads only the file for the running build). The title ID
             is in the file name ([0100...]) or an NSP's ticket name; an XCI without it in the name isn't read.
  Dolphin    the codes in the image's GameSettings/<game ID>.ini ([ActionReplay], [Gecko]; not the ones it enables by
             default); written as "$name" lines in [*_Enabled] of the user's GameSettings/<game ID>.ini, which also holds
             the game's other settings, so only those lines change. The game ID is the disc's first 6 bytes (.iso, .rvz,
             .wbfs, .ciso, .gcz). The start script switches Dolphin's EnableCheats on while ON_FLAG exists.
  ARMSX2     ps2-cheats-db's ps2/[<serial>_]<ELF CRC>.pnach; written as ARMSX2's cheats/<serial>_ASGARD.pnach with only
             the chosen cheats, unlabelled (always applied), and EnableCheats switched on in PCSX2.ini. The serial and
             the CRC (XOR of the boot ELF's words) come from the disc (.iso, raw .bin, .cso; not .chd yet).
  Mednafen   libretro-database's .cht for the system, decoded as Mednafen's own cheat dialog does (Game Genie,
             GameShark, Pro Action Replay, raw RAM writes, GBA Code Breaker; a cheat with a code it can't run isn't
             listed) into cheats/<module>.cht, as a section "[<game's MD5>] Asgard cheats..." (snes_faust: SHA-1).
             A section the user made in Mednafen for the game is left alone. gb gba nes snes_faust md sms gg pce.
  Flycast    libretro-database's Dreamcast .cht (already its format), written to a folder of ours that apply adds to
             emu.cfg's Dreamcast.CheatPath, as <rom file name>.cht with the chosen cheats enabled.
  mupen64plus  its own mupencheat.txt section for the ROM (by the header's CRCs; a cheat with options is one entry
             per option), else libretro-database's N64 .cht; written as a one-game mupencheat.txt (N64_OUT) with only
             the chosen cheats, which start_mupen64plus.sh puts on mupen64plus's data path, passing --cheats all.
  DuckStation  libretro-database's PlayStation .cht (GameShark), as its cheats/<serial>.cht with only the chosen
             cheats, and "Enable = <name>" in [Cheats] plus EnableCheats in [Console] of the game's gamesettings ini,
             where only those lines change (the names Asgard switched on are on a comment line). The serial is in
             the disc's SYSTEM.CNF (.bin/.cue, .iso, .m3u; not .chd or .pbp).
  AetherSX2  the same, written as its cheats/<ELF CRC>.pnach (it applies every line in it); a user's own is left alone.
A cheat file the user made in the emulator itself (no MARK line at the top) is never replaced or removed.
"""
import array
import difflib
import functools
import hashlib
import json
import operator
import os
import re
import shutil
import sys
import zipfile
import zlib

STATE = os.environ.get("ASGARD_CHEATS_STATE", "/storage/.config/asgard/cheats")
RA_DB = os.environ.get("ASGARD_CHEATS_RA_DB", "/usr/share/libretro-database/cht")
RA_OUT = os.environ.get("ASGARD_CHEATS_RA_OUT", "/tmp/database/cht")       # cheat_database_path (overlay on /storage)
RA_CORES = os.environ.get("ASGARD_CHEATS_RA_CORES", "/tmp/cores")          # <core>_libretro.info: corename
RA_APPEND = os.environ.get("ASGARD_CHEATS_RA_APPEND", "/tmp/.retroarch.cfg")  # runemu.sh's --appendconfig
DB = os.environ.get("ASGARD_CHEATS_DB", "/usr/share/asgard-cheats")          # asgard-cheats-db
AZAHAR_OUT = os.environ.get("ASGARD_CHEATS_AZAHAR_OUT", "/storage/.config/azahar/cheats")
PSP_DB = os.environ.get("ASGARD_CHEATS_PSP_DB", "/usr/config/ppsspp/PSP/Cheats")      # cheat.db + shipped inis
PSP_OUT = os.environ.get("ASGARD_CHEATS_PSP_OUT", "/storage/.config/ppsspp/PSP/Cheats")
MELONDS_TOML = os.environ.get("ASGARD_CHEATS_MELONDS_TOML", "/storage/.config/melonDS/melonDS.toml")
# Emulators with no cheat engine, or none Asgard writes yet: what the list says instead
NO_CHEATS = {
    "nanoboyadvance": "NanoBoyAdvance has no cheats: set this game's emulator to RetroArch (mGBA) for them",
}
EDEN_LOAD = os.environ.get("ASGARD_CHEATS_EDEN_LOAD", "/storage/.local/share/eden/load")   # Eden and Eden Duo
EDEN_MOD = "Asgard Cheats"    # our mod folder: everything in it is ours
DOLPHIN_DB = os.environ.get("ASGARD_CHEATS_DOLPHIN_DB", "/usr/config/dolphin-emu/GameSettings")    # the image's copy
DOLPHIN_OUT = os.environ.get("ASGARD_CHEATS_DOLPHIN_OUT", "/storage/.config/dolphin-emu/GameSettings")
# Set while the game starting has cheats on: for start scripts that rewrite their emulator's master switch (Dolphin)
PS2_INI = os.environ.get("ASGARD_CHEATS_PS2_INI", "/storage/.config/ARMSX2/inis/PCSX2.ini")
PS2_INI_IMAGE = os.environ.get("ASGARD_CHEATS_PS2_INI_IMAGE", "/usr/config/ARMSX2/inis/PCSX2.ini")
PS2_OUT = os.environ.get("ASGARD_CHEATS_PS2_OUT", "/storage/.config/ARMSX2/cheats")
MEDNAFEN_OUT = os.environ.get("ASGARD_CHEATS_MEDNAFEN_OUT", "/storage/.config/mednafen/cheats")    # <module>.cht
FLYCAST_CFG = os.environ.get("ASGARD_CHEATS_FLYCAST_CFG", "/storage/.config/flycast/emu.cfg")
FLYCAST_OUT = os.environ.get("ASGARD_CHEATS_FLYCAST_OUT", "/storage/.config/flycast/asgard-cheats")
N64_DB = os.environ.get("ASGARD_CHEATS_N64_DB", "/usr/local/share/mupen64plus/mupencheat.txt")
N64_OUT = os.environ.get("ASGARD_CHEATS_N64_OUT", "/tmp/asgard-mupencheat.txt")    # start_mupen64plus.sh copies it
DRASTIC_OUT = os.environ.get("ASGARD_CHEATS_DRASTIC_OUT", "/storage/.config/drastic/cheats")   # <rom name>.cht
DUCK = os.environ.get("ASGARD_CHEATS_DUCK", "/storage/.config/duckstation")     # cheats/, gamesettings/
AETHER = os.environ.get("ASGARD_CHEATS_AETHER", "/storage/.config/aethersx2")          # cheats/, inis/PCSX2.ini
ON_FLAG = os.environ.get("ASGARD_CHEATS_ON_FLAG", "/tmp/.asgard-cheats-on")
MARK = "# Asgard cheats: written at launch from the game's Cheats list; edits here are replaced"

# ES system -> libretro-database cht folder
RA_SYSTEMS = {
    "nes": "Nintendo - Nintendo Entertainment System", "famicom": "Nintendo - Nintendo Entertainment System",
    "nesh": "Nintendo - Nintendo Entertainment System", "fds": "Nintendo - Family Computer Disk System",
    "snes": "Nintendo - Super Nintendo Entertainment System", "sfc": "Nintendo - Super Nintendo Entertainment System",
    "snesh": "Nintendo - Super Nintendo Entertainment System", "snesmsu1": "Nintendo - Super Nintendo Entertainment System",
    "satellaview": "Nintendo - Satellaview",
    "gb": "Nintendo - Game Boy", "gbh": "Nintendo - Game Boy", "gbc": "Nintendo - Game Boy Color",
    "gbch": "Nintendo - Game Boy Color", "gba": "Nintendo - Game Boy Advance", "gbah": "Nintendo - Game Boy Advance",
    "n64": "Nintendo - Nintendo 64", "nds": "Nintendo - Nintendo DS",
    "psx": "Sony - PlayStation", "psp": "Sony - PlayStation Portable",
    "megadrive": "Sega - Mega Drive - Genesis", "megadrive-japan": "Sega - Mega Drive - Genesis",
    "genesis": "Sega - Mega Drive - Genesis", "genh": "Sega - Mega Drive - Genesis",
    "megadriveh": "Sega - Mega Drive - Genesis", "mastersystem": "Sega - Master System - Mark III",
    "gamegear": "Sega - Game Gear", "ggh": "Sega - Game Gear", "sega32x": "Sega - 32X",
    "segacd": "Sega - Mega-CD - Sega CD", "megacd": "Sega - Mega-CD - Sega CD", "saturn": "Sega - Saturn",
    "dreamcast": "Sega - Dreamcast",
    "pcengine": "NEC - PC Engine - TurboGrafx 16", "tg16": "NEC - PC Engine - TurboGrafx 16",
    "pcenginecd": "NEC - PC Engine CD - TurboGrafx-CD", "tg16cd": "NEC - PC Engine CD - TurboGrafx-CD",
    "supergrafx": "NEC - PC Engine SuperGrafx",
    "atari2600": "Atari - 2600", "atari5200": "Atari - 5200", "atari7800": "Atari - 7800", "atari800": "Atari - 8-bit Family",
    "atarijaguar": "Atari - Jaguar", "atarilynx": "Atari - Lynx", "colecovision": "Coleco - ColecoVision",
    "intellivision": "Mattel - Intellivision", "msx": "Microsoft - MSX - MSX2 - MSX2P - MSX Turbo R",
    "msx2": "Microsoft - MSX - MSX2 - MSX2P - MSX Turbo R", "fbn": "FBNeo - Arcade Games",
}


def norm(name):
    """A title without its tags, case or punctuation: "Pokemon - Emerald Version (USA, Europe)" -> "pokemonemeraldversion"."""
    name = re.sub(r"\([^)]*\)|\[[^\]]*\]", "", name)
    return re.sub(r"[^a-z0-9]", "", name.lower().replace("&", "and"))


def tags(name):
    return {t.strip().lower() for g in re.findall(r"\(([^)]*)\)", name) for t in g.split(",")}


def best_file(folder, rom):
    """The database file for a ROM: its exact name, else the same title, with the most tags (region...) in common."""
    try:
        files = [f for f in os.listdir(folder) if f.endswith(".cht")]
    except OSError:
        return None
    stem = os.path.splitext(os.path.basename(rom))[0]
    if stem + ".cht" in files:
        return os.path.join(folder, stem + ".cht")
    want, mine = norm(stem), tags(stem)
    same = [f for f in files if norm(f[:-4]) == want]
    if not same:
        # A title spelled a little differently ("Pokemon" / "Pokémon", a missing subtitle colon). Tight: "Red" and
        # "Blue" versions of a game must not match.
        close = difflib.get_close_matches(want, [norm(f[:-4]) for f in files], n=1, cutoff=0.94)
        same = [f for f in files if close and norm(f[:-4]) == close[0]]
    if not same:
        return None
    same.sort(key=lambda f: (-len(tags(f[:-4]) & mine), len(f), f))
    return os.path.join(folder, same[0])


# --- RetroArch .cht -------------------------------------------------------------------------------------------------
def cht_read(path):
    values = {}
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            m = re.match(r'\s*([A-Za-z0-9_]+)\s*=\s*"?(.*?)"?\s*$', line)
            if m:
                values[m.group(1)] = m.group(2)
    count = int(values.get("cheats", "0") or 0)
    return [{"i": i, "name": values.get(f"cheat{i}_desc", f"Cheat {i + 1}"), "values": values} for i in range(count)]


def cht_write(src, dst, on, mark=MARK):
    """src with cheatN_enable set from `on` (names), everything else as it was."""
    cheats = {c["i"]: c["name"] for c in cht_read(src)}
    out = [mark + "\n"]
    with open(src, encoding="utf-8", errors="replace") as f:
        for line in f:
            m = re.match(r"\s*cheat(\d+)_enable\s*=", line)
            if m:
                i = int(m.group(1))
                line = f"cheat{i}_enable = {'true' if cheats.get(i) in on else 'false'}\n"
            out.append(line)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with open(dst + ".new", "w", encoding="utf-8") as f:
        f.writelines(out)
    os.replace(dst + ".new", dst)


def ra_core_name(core):
    """RetroArch's library name for a core (the folder it looks for game cheats in), from its .info file."""
    try:
        with open(os.path.join(RA_CORES, core + "_libretro.info"), encoding="utf-8", errors="replace") as f:
            for line in f:
                m = re.match(r'\s*corename\s*=\s*"(.*)"', line)
                if m:
                    return m.group(1)
    except OSError:
        pass
    return None


class RetroArch:
    def source(self, system, rom):
        folder = RA_SYSTEMS.get(system)
        return best_file(os.path.join(RA_DB, folder), rom) if folder else None

    def cheats(self, src):
        return [c["name"] for c in cht_read(src)]

    def apply(self, system, rom, core, src, on):
        name = ra_core_name(core)
        if not name:
            return
        dst = os.path.join(RA_OUT, name, os.path.splitext(os.path.basename(rom))[0] + ".cht")
        mine = os.path.exists(dst) and open(dst, encoding="utf-8", errors="replace").readline().startswith(MARK)
        if os.path.exists(dst) and not mine:
            return                       # the user's own file from RetroArch's menu: theirs, left alone
        if not src or not on:
            if mine:
                os.remove(dst)           # nothing on any more: no file, so RetroArch applies nothing
            return
        cht_write(src, dst, set(on))
        with open(RA_APPEND, "a") as f:
            f.write('apply_cheats_after_load = "true"\n')


def ours(path, mark):
    """(exists, written by us): a file without our first line is the user's."""
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return True, f.readline().startswith(mark)
    except OSError:
        return False, False


def write_file(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".new", "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(path + ".new", path)


# --- Azahar (Citra's Gateway format: "[name]", code lines, "*citra_enabled" to switch one on) ----------------------
def title_id_3ds(rom):
    """The program ID from a .3ds/.cci (NCSD: media ID at 0x108) or .cxi (NCCH: program ID at 0x118), or None."""
    try:
        with open(rom, "rb") as f:
            head = f.read(0x200)
    except OSError:
        return None
    if len(head) < 0x120:
        return None
    if head[0x100:0x104] == b"NCSD":
        return "%016X" % int.from_bytes(head[0x108:0x110], "little")
    if head[0x100:0x104] == b"NCCH":
        return "%016X" % int.from_bytes(head[0x118:0x120], "little")
    return None


def gateway_read(path):
    cheats, cur = [], None
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            m = re.match(r"^\[(.+)\]$", line)
            if m:
                cur = {"name": m.group(1).strip(), "code": []}
                cheats.append(cur)
            elif cur is not None and line and not line.startswith("*"):
                cur["code"].append(line)
    return cheats


AZAHAR_MARK = "*" + MARK.lstrip("#")   # a "*" line is a comment to Azahar


class Azahar:
    def source(self, system, rom):
        tid = title_id_3ds(rom)
        path = os.path.join(DB, "3ds", tid + ".txt") if tid else None
        return path if path and os.path.exists(path) else None

    def cheats(self, src):
        return [c["name"] for c in gateway_read(src)]

    def apply(self, system, rom, core, src, on):
        tid = title_id_3ds(rom)
        if not tid:
            return
        dst = os.path.join(AZAHAR_OUT, tid + ".txt")
        exists, mine = ours(dst, AZAHAR_MARK)
        if exists and not mine:
            return
        if not src or not on:
            if mine:
                os.remove(dst)
            return
        text = [AZAHAR_MARK + "\n"]
        for c in gateway_read(src):   # every cheat, so Azahar's own list shows them all; ours switched on
            text += ["\n", f"[{c['name']}]\n"] + (["*citra_enabled\n"] if c["name"] in on else []) + \
                    [code + "\n" for code in c["code"]]
        write_file(dst, "".join(text))


# --- PPSSPP (CWCheat: "_S <disc ID>", "_G <title>", "_C0|_C1 <name>", "_L <code>") -------------------------------
class Image:
    """Random reads from a PSP disc image: a plain .iso, or a .cso (CISO: an index of deflated blocks)."""
    def __init__(self, path):
        self.f = open(path, "rb")
        head = self.f.read(0x18)
        self.cso = head[:4] == b"CISO"
        self.raw = None                  # a raw CD .bin: 2352-byte sectors, the 2048 data bytes at 16 (mode 1) or 24
        if head[:12] == b"\0" + b"\xff" * 10 + b"\0":
            self.f.seek(16 * 2352 + 15)
            self.raw = 24 if self.f.read(1) == b"\x02" else 16
        if self.cso:
            total, self.block, self.align = int.from_bytes(head[8:16], "little"), int.from_bytes(head[16:20], "little"), head[21]
            n = (total + self.block - 1) // self.block + 1
            raw = self.f.read(4 * n)
            self.index = [int.from_bytes(raw[i:i + 4], "little") for i in range(0, len(raw), 4)]

    def read(self, offset, size):
        if self.raw:
            out = b""
            while size > 0:
                sector, inner = divmod(offset, 2048)
                self.f.seek(sector * 2352 + self.raw + inner)
                chunk = self.f.read(min(size, 2048 - inner))
                if not chunk:
                    break
                out, offset, size = out + chunk, offset + len(chunk), size - len(chunk)
            return out
        if not self.cso:
            self.f.seek(offset)
            return self.f.read(size)
        out = b""
        while size > 0:
            b, inner = divmod(offset, self.block)
            if b + 1 >= len(self.index):
                break
            start, end = (self.index[b] & 0x7FFFFFFF) << self.align, (self.index[b + 1] & 0x7FFFFFFF) << self.align
            self.f.seek(start)
            data = self.f.read(end - start)
            if not self.index[b] & 0x80000000:
                data = zlib.decompressobj(-15).decompress(data)
            chunk = data[inner:inner + size]
            if not chunk:
                break
            out += chunk
            offset, size = offset + len(chunk), size - len(chunk)
        return out


def iso_file(img, name):
    """A file in an ISO9660 image ("UMD_DATA.BIN", "DATA/SLUS_200.62"), or None."""
    pvd = img.read(16 * 2048, 2048)
    if pvd[1:6] != b"CD001":
        return None
    lba, size = int.from_bytes(pvd[158:162], "little"), int.from_bytes(pvd[166:170], "little")
    parts = [p for p in name.upper().replace("\\", "/").split("/") if p]
    for depth, part in enumerate(parts):
        d, i, found = img.read(lba * 2048, size), 0, None
        while i < len(d):
            n = d[i]
            if n == 0:                   # records don't cross a sector: on to the next one
                i = (i // 2048 + 1) * 2048
                continue
            ident = d[i + 33:i + 33 + d[i + 32]].decode("ascii", "replace").split(";")[0]
            if ident.upper() == part:
                found = int.from_bytes(d[i + 2:i + 6], "little"), int.from_bytes(d[i + 10:i + 14], "little")
                break
            i += n
        if not found:
            return None
        lba, size = found
    return img.read(lba * 2048, size)


def sfo_value(sfo, key):
    if not sfo or sfo[:4] != b"\0PSF":
        return None
    keys, data, count = (int.from_bytes(sfo[o:o + 4], "little") for o in (8, 12, 16))
    for e in range(count):
        at = 20 + 16 * e
        name = sfo[keys + int.from_bytes(sfo[at:at + 2], "little"):].split(b"\0")[0].decode("ascii", "replace")
        if name == key:
            off, size = data + int.from_bytes(sfo[at + 12:at + 16], "little"), int.from_bytes(sfo[at + 4:at + 8], "little")
            return sfo[off:off + size].split(b"\0")[0].decode("ascii", "replace")
    return None


def disc_id_psp(rom):
    """ULUS-10041, as cheat.db names it; None for what isn't read (.chd)."""
    try:
        if rom.lower().endswith(".pbp"):
            with open(rom, "rb") as f:
                head = f.read(0x28)
                start, end = int.from_bytes(head[8:12], "little"), int.from_bytes(head[12:16], "little")
                f.seek(start)
                v = sfo_value(f.read(end - start), "DISC_ID")
            return v[:4] + "-" + v[4:] if v and "-" not in v else v
        img = Image(rom)
        umd = iso_file(img, "UMD_DATA.BIN")
        return umd[:10].decode() if umd and re.match(rb"^[A-Z]{4}-\d{5}", umd) else None
    except (OSError, ValueError, zlib.error, IndexError):
        return None


def cw_blocks(path, disc):
    """The lines of every _S block for this disc in a CWCheat file."""
    out, take = [], False
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.rstrip("\r\n")
            if line.startswith("_S"):
                take = line[2:].strip().replace("-", "") == disc.replace("-", "")
            if take:
                out.append(line)
    return out


class PPSSPP:
    def _db(self, disc):
        shipped = os.path.join(PSP_DB, disc.replace("-", "") + ".ini")
        return shipped if os.path.exists(shipped) else os.path.join(PSP_DB, "cheat.db")

    def source(self, system, rom):
        disc = disc_id_psp(rom)
        if not disc:
            return None
        db = self._db(disc)
        return f"{db}|{disc}" if os.path.exists(db) and cw_blocks(db, disc) else None

    def cheats(self, src):
        db, disc = src.split("|")
        return [l[3:].strip() for l in cw_blocks(db, disc) if re.match(r"_C\d", l)]

    def apply(self, system, rom, core, src, on):
        disc = disc_id_psp(rom)
        if not disc:
            return
        dst = os.path.join(PSP_OUT, disc.replace("-", "") + ".ini")
        exists, mine = ours(dst, MARK)
        shipped = os.path.join(PSP_DB, disc.replace("-", "") + ".ini")
        if exists and not mine:
            try:
                same = open(dst, "rb").read() == open(shipped, "rb").read()   # the image's copy: ours to replace
            except OSError:
                same = False
            if not same:
                return
        if not src or not on:
            if mine:
                os.remove(dst)
            return
        db, disc = src.split("|")
        lines = [MARK]
        for l in cw_blocks(db, disc):
            m = re.match(r"_C\d\s*(.*)", l)
            lines.append(("_C1 " if m.group(1).strip() in on else "_C0 ") + m.group(1).strip() if m else l)
        write_file(dst, "\n".join(lines) + "\n")


# --- melonDS (.mch: "CAT <name>", "CODE <0|1> <name>", then 8+8 hex digit lines) -----------------------------------
class MelonDS:
    FOLDER = "Nintendo - Nintendo DS"

    def source(self, system, rom):
        return best_file(os.path.join(RA_DB, self.FOLDER), rom)

    def coded(self, src):
        out = []
        for c in cht_read(src):
            code = c["values"].get(f"cheat{c['i']}_code", "")
            words = [w for w in re.split(r"[+\s]+", code) if re.fullmatch(r"[0-9A-Fa-f]{8}", w)]
            if words and len(words) % 2 == 0:     # headers ("Miscellaneous Codes") have no code
                out.append((c["name"][:120], [f"{words[i]} {words[i + 1]}" for i in range(0, len(words), 2)]))
        return out

    def cheats(self, src):
        return [name for name, _ in self.coded(src)]

    def apply(self, system, rom, core, src, on):
        dst = os.path.splitext(rom)[0] + ".mch"
        exists, mine = ours(dst, MARK)
        if exists and not mine:
            return
        if not src or not on:
            if mine:
                os.remove(dst)
            return
        text = [MARK + "\n", "CAT Cheats\n"]
        for name, lines in self.coded(src):
            text += [f"CODE {1 if name in on else 0} {name}\n"] + [l + "\n" for l in lines] + ["\n"]
        write_file(dst, "".join(text))
        try:
            with open(MELONDS_TOML) as f:
                toml = f.read()
            new = re.sub(r"(?m)^(\s*EnableCheats\s*=\s*)false\s*$", r"\1true", toml)
            if new != toml:
                write_file(MELONDS_TOML, new)
        except OSError:
            pass


class DraStic(MelonDS):
    """The same Action Replay codes, as DraStic's custom cheat file cheats/<rom name>.cht: "[name]+" (on), code lines.
    Our file starts with a "[...]" entry without "+" or codes, which DraStic ignores: the mark."""
    MARK = "[" + MARK.lstrip("# ") + "]"

    def apply(self, system, rom, core, src, on):
        dst = os.path.join(DRASTIC_OUT, os.path.splitext(os.path.basename(rom))[0] + ".cht")
        exists, mine = ours(dst, self.MARK)
        if exists and not mine:
            return False
        if mine:
            os.remove(dst)
        chosen = [(n, l) for n, l in self.coded(src) if n in on] if src else []
        if chosen:
            write_file(dst, "".join([self.MARK + "\n\n"] + [f"[{n}]+\n" + "".join(x + "\n" for x in l) + "\n" for n, l in chosen]))
        return bool(chosen)


class SkyEmu(MelonDS):
    """<rom>.code beside the ROM: one cheat a line, 'on "name" "hex words"', at most 32, names cut at 31 characters.
    DS games: libretro's Action Replay codes, as melonDS. GB/GBC: GameShark codes that write A000-DFFF (SkyEmu runs
    no others). GBA: SkyEmu takes encrypted Action Replay v3 only, which libretro's database doesn't hold."""
    MARK = '0 "Asgard cheats" ""'       # a first entry with no code: ours. SkyEmu keeps it when it saves the file.
    GB = {"gb", "gbc", "gbh", "gbch"}

    def source(self, system, rom):
        if system in self.GB:
            return RetroArch().source(system, rom)
        return super().source(system, rom) if system == "nds" else None

    def coded(self, src):
        if os.path.basename(os.path.dirname(src)) == self.FOLDER:
            return [(n, [w for l in lines for w in l.split()]) for n, lines in super().coded(src)]
        out = []
        for c in cht_read(src):
            words = [w.strip().upper() for w in c["values"].get(f"cheat{c['i']}_code", "").split("+")]
            if words[0] and all(re.fullmatch(r"[0-9A-F]{8}", w) and 0xA000 <= int(w[6:8] + w[4:6], 16) <= 0xDFFF
                                for w in words):
                out.append((c["name"], words))
        return out

    def apply(self, system, rom, core, src, on):
        dst = os.path.splitext(rom)[0] + ".code"
        exists, mine = ours(dst, self.MARK)
        if exists and not mine:
            return False
        if mine:
            os.remove(dst)
        chosen = [(n, w) for n, w in self.coded(src) if n in on][:31] if src else []
        if chosen:
            lines = [self.MARK] + ['1 "%s" "%s"' % (n.replace('"', "'")[:31], " ".join(w)) for n, w in chosen]
            write_file(dst, "\n".join(lines) + "\n")
        return bool(chosen)


# --- Eden (Atmosphère's cheat text: "[name]" or "{master}", then 8-hex-digit words) ---------------------------------
def title_id_switch(rom):
    """The base title ID: from the file name's [0100...] tag, else an NSP's ticket (its rights ID starts with it)."""
    m = re.search(r"\[(01[0-9A-Fa-f]{14})\]", os.path.basename(rom))
    tid = m.group(1).upper() if m else None
    if not tid and rom.lower().endswith(".nsp"):
        try:
            with open(rom, "rb") as f:
                head = f.read(16)
                if head[:4] == b"PFS0":
                    count, strsize = int.from_bytes(head[4:8], "little"), int.from_bytes(head[8:12], "little")
                    f.seek(16 + 24 * count)
                    names = f.read(strsize).split(b"\0")
                    tik = [n.decode("ascii", "replace") for n in names if n.lower().endswith(b".tik")]
                    if tik and re.match(r"[0-9A-Fa-f]{16}", tik[0]):
                        tid = tik[0][:16].upper()
        except OSError:
            pass
    return tid[:-3] + "000" if tid else None    # an update's or DLC's ID shares the base game's cheats


def atmo_lines(code):
    """Only what Eden's parser takes: a stray character elsewhere makes it drop the whole file."""
    out = []
    for line in code.splitlines():
        line = line.strip()
        if re.fullmatch(r"\[[^\[\]{}]+\]|\{[^\[\]{}]+\}", line) or re.fullmatch(r"[0-9A-Fa-f]{8}( [0-9A-Fa-f]{8})*", line):
            out.append(line)
    return out


def atmo_cheats(code):
    """[(name, lines, master)] from one cheat's text, which can hold a {master} section and several [cheats]."""
    out, cur = [], None
    for line in atmo_lines(code):
        if line[0] in "[{":
            cur = (line[1:-1].strip(), [line], line[0] == "{")
            out.append(cur)
        elif cur:
            cur[1].append(line)
    return [c for c in out if len(c[1]) > 1]


class Eden:
    def source(self, system, rom):
        tid = title_id_switch(rom)
        path = os.path.join(DB, "switch", tid + ".json") if tid else None
        return path if path and os.path.exists(path) else None

    def builds(self, src):
        with open(src, encoding="utf-8", errors="replace") as f:
            data = json.load(f)
        return {bid: [c for code in cheats.values() for c in atmo_cheats(code)] for bid, cheats in data.items()}

    def cheats(self, src):
        seen = []
        for cheats in self.builds(src).values():
            for name, _, master in cheats:
                if not master and name not in seen:
                    seen.append(name)
        return seen

    def apply(self, system, rom, core, src, on):
        tid = title_id_switch(rom)
        if not tid:
            return
        mod = os.path.join(EDEN_LOAD, tid, EDEN_MOD)
        shutil.rmtree(mod, ignore_errors=True)
        if not src or not on:
            return
        for bid, cheats in self.builds(src).items():
            chosen = [c for c in cheats if not c[2] and c[0] in on]
            if chosen:   # a build's master code goes with its cheats
                lines = [l for c in cheats if c[2] for l in c[1] + [""]] + [l for c in chosen for l in c[1] + [""]]
                write_file(os.path.join(mod, "cheats", bid.upper() + ".txt"), "\n".join(lines) + "\n")


# --- Dolphin (its per-game ini: "$name" + code lines in [ActionReplay] and [Gecko], "$name" in [<section>_Enabled]) -
def game_id_dolphin(rom):
    """The 6-character game ID (GALE01) from a GameCube/Wii disc: plain .iso/.gcm, .rvz/.wia, .wbfs, .ciso, .gcz."""
    try:
        with open(rom, "rb") as f:
            head = f.read(0x60)
            if head[:4] in (b"RVZ\x01", b"WIA\x01"):
                gid = head[0x58:0x5E]                     # the disc header's copy after the file and disc structs
            elif head[:4] == b"WBFS":
                f.seek(1 << head[8])                      # the first disc's header copy, one HD sector in
                gid = f.read(6)
            elif head[:4] == b"CISO":
                f.seek(0x8000)                            # block 0 follows the 32 KiB block map
                gid = f.read(6)
            elif head[:4] == bytes.fromhex("01C00BB1"):   # GCZ: block 0, zlib unless its pointer's top bit is set
                count = int.from_bytes(head[0x1C:0x20], "little")
                f.seek(0x20)
                ptrs = f.read(16)
                p0, p1 = int.from_bytes(ptrs[:8], "little"), int.from_bytes(ptrs[8:16], "little") & ~(1 << 63)
                f.seek(0x20 + 12 * count + (p0 & ~(1 << 63)))
                block = f.read(p1 - (p0 & ~(1 << 63)) if count > 1 else 0x8000)
                gid = block[:6] if p0 >> 63 else zlib.decompressobj().decompress(block)[:6]
            else:
                gid = head[:6]
    except (OSError, zlib.error):
        return None
    gid = gid.decode("ascii", "replace")
    return gid if re.fullmatch(r"[A-Z0-9]{6}", gid) else None


def ini_sections(text):
    """[(header or None for the lines before the first section, [lines])] in file order."""
    out = [(None, [])]
    for line in text.splitlines():
        m = re.match(r"^\[([^\]]*)\]", line)
        if m:
            out.append((m.group(1), []))
        else:
            out[-1][1].append(line)
    return out


def dolphin_name(section, line):
    """A code's name as Dolphin matches it in _Enabled: a Gecko name stops at its "[author]"."""
    name = line[1:]
    return name.split("[")[0].strip() if section == "Gecko" else name


def dolphin_codes(text):
    """{section: [(name, lines)]} for ActionReplay and Gecko, and the names enabled in each by default."""
    codes, enabled = {"ActionReplay": [], "Gecko": []}, set()
    for head, lines in ini_sections(text):
        if head in codes:
            for line in lines:
                if line.startswith("$"):
                    codes[head].append((dolphin_name(head, line), [line]))
                elif codes[head] and line.strip() and not line.startswith("#"):
                    codes[head][-1][1].append(line)
        elif head in ("ActionReplay_Enabled", "Gecko_Enabled"):
            enabled |= {(head[:-8], l[1:]) for l in lines if l.startswith("$")}
    return {s: [c for c in v if len(c[1]) > 1 and (s, c[0]) not in enabled] for s, v in codes.items()}


DOLPHIN_MARK = "# Asgard cheats on: "    # before the first section, which Dolphin ignores; the names we switched on


class Dolphin:
    def source(self, system, rom):
        gid = game_id_dolphin(rom)
        path = os.path.join(DOLPHIN_DB, gid + ".ini") if gid else None
        if not path or not os.path.exists(path):
            return None
        with open(path, encoding="utf-8", errors="replace") as f:
            return path if any(dolphin_codes(f.read()).values()) else None

    def cheats(self, src):
        with open(src, encoding="utf-8", errors="replace") as f:
            codes = dolphin_codes(f.read())
        seen = []
        for name, _ in codes["ActionReplay"] + codes["Gecko"]:
            if name not in seen:
                seen.append(name)
        return seen

    def apply(self, system, rom, core, src, on):
        """Only the enable lines of the database's cheats change, in the game's ini, which holds the user's other
        settings too. A cheat the user switched on in Dolphin itself stays on: only ours (the mark) are switched off."""
        gid = game_id_dolphin(rom)
        if not gid:
            return False
        dst = os.path.join(DOLPHIN_OUT, gid + ".ini")
        try:
            with open(dst, encoding="utf-8", errors="replace") as f:
                text = f.read()
        except OSError:
            text = None
        sections = ini_sections(text) if text is not None else None
        before = []
        if sections:
            for line in sections[0][1]:
                if line.startswith(DOLPHIN_MARK):
                    try:
                        before = json.loads(line[len(DOLPHIN_MARK):])
                    except ValueError:
                        pass
        db = {"ActionReplay": [], "Gecko": []}
        if src:
            with open(src, encoding="utf-8", errors="replace") as f:
                shipped = f.read()
            db = dolphin_codes(shipped)
            if sections is None:
                sections = ini_sections(shipped)          # what Dolphin's first start would have copied
        if sections is None or (not before and not on):
            return False
        now = [n for s in db.values() for n, _ in s if n in on]
        heads = [h for h, _ in sections]
        for sec in ("ActionReplay", "Gecko"):
            want = [n for n, _ in db[sec] if n in on]
            for name, lines in db[sec]:
                if name in want:
                    if sec not in heads:
                        sections.append((sec, []))
                        heads.append(sec)
                    body = sections[heads.index(sec)][1]
                    if not any(l.startswith("$") and dolphin_name(sec, l) == name for l in body):
                        body += lines
            for suffix, keep in (("_Enabled", False), ("_Disabled", True)):
                head = sec + suffix
                if head not in heads:
                    if suffix == "_Disabled" or not want:
                        continue
                    sections.append((head, []))
                    heads.append(head)
                body = sections[heads.index(head)][1]
                drop = set(before) | set(want)    # ours, re-added below; and none of ours stays in _Disabled
                body[:] = [l for l in body if not (l.startswith("$") and l[1:] in drop)]
                if not keep:
                    body[:] = [l for l in body if l.strip()] + ["$" + n for n in want] + [""]
        pre = [l for l in sections[0][1] if not l.startswith(DOLPHIN_MARK)]
        sections[0] = (None, ([DOLPHIN_MARK + json.dumps(now)] if now else []) + pre)
        out = []
        for head, lines in sections:
            out += ([f"[{head}]"] if head is not None else []) + lines
        write_file(dst, "\n".join(out).rstrip("\n") + "\n")
        return bool(now)


# --- ARMSX2 (pnach: "[name]" groups of "patch=1,EE,<addr>,<type>,<value>" lines) -----------------------------------
def ps2_game(rom):
    """(serial, ELF CRC) of a PS2 disc (.iso, raw .bin, .cso): SYSTEM.CNF's BOOT2 names the ELF, and the CRC PCSX2
    keys cheats by is the XOR of its 32-bit words. (None, None) for what isn't read (.chd, .gz, .zso)."""
    try:
        img = Image(rom)
        cnf = iso_file(img, "SYSTEM.CNF")
        m = re.search(rb"BOOT2\s*=\s*cdrom0?:\\?([^;\r\n]+)", cnf or b"")
        if not m:
            return None, None
        path = m.group(1).decode("ascii", "replace").strip()
        elf = iso_file(img, path)
        if not elf:
            return None, None
        words = array.array("I", elf[:len(elf) // 4 * 4])
        if sys.byteorder != "little":
            words.byteswap()
        crc = functools.reduce(operator.xor, words, 0)
        stem = path.replace("\\", "/").split("/")[-1].upper()
        serial = stem.replace("_", "-").replace(".", "") if re.fullmatch(r"[A-Z]{4}_\d{3}\.\d{2}", stem) else None
        return serial, "%08X" % crc
    except (OSError, ValueError, zlib.error, IndexError):
        return None, None


def pnach_groups(path):
    """[(name, [patch lines])], groups of one name (a cheat in several parts) joined."""
    groups, cur = {}, None
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            m = re.fullmatch(r"\[(.+)\]", line)
            if m:
                cur = groups.setdefault(m.group(1).strip(), [])
            elif cur is not None and line.startswith("patch="):
                cur.append(line)
    return [(n, lines) for n, lines in groups.items() if lines]


class ARMSX2:
    def source(self, system, rom):
        _, crc = ps2_game(rom)
        folder = os.path.join(DB, "ps2")
        try:
            names = sorted(f for f in os.listdir(folder) if re.fullmatch(r"(?:.*_)?%s\.pnach" % crc, f, re.I))
        except OSError:
            names = []
        return os.path.join(folder, names[0]) if crc and names else None

    def cheats(self, src):
        return [n for n, _ in pnach_groups(src)]

    def file(self, rom):
        serial, _ = ps2_game(rom)
        return os.path.join(PS2_OUT, serial + "_ASGARD.pnach") if serial else None

    def ini(self):
        return PS2_INI, PS2_INI_IMAGE

    def apply(self, system, rom, core, src, on):
        """Our own pnach, <serial>_ASGARD.pnach (ARMSX2 loads every <serial>_*.pnach in cheats/), holding only the
        chosen cheats' lines, unlabelled: those always apply, with no enable list in the game's settings."""
        dst = self.file(rom)
        if not dst:
            return False
        exists, mine = ours(dst, MARK.replace("#", "//", 1))
        if exists and not mine:
            return False                 # AetherSX2's <CRC>.pnach the user made
        if mine:
            os.remove(dst)
        chosen = [(n, lines) for n, lines in pnach_groups(src) if n in on] if src else []
        if not chosen:
            return False
        text = [MARK.replace("#", "//", 1), "gametitle=" + os.path.basename(rom)]
        for name, lines in chosen:
            text += ["", "// " + name] + lines
        write_file(dst, "\n".join(text) + "\n")
        ini, image = self.ini()
        if not os.path.exists(ini) and os.path.exists(image):
            os.makedirs(os.path.dirname(ini), exist_ok=True)
            shutil.copy(image, ini)      # what the start script would copy at its first run
        try:
            with open(ini) as f:
                text = f.read()
            new = re.sub(r"(?m)^(\s*EnableCheats\s*=\s*)false\s*$", r"\1true", text)
            if new != text:
                write_file(ini, new)
        except OSError:
            pass
        return True


class AetherSX2(ARMSX2):
    """An older PCSX2: it loads cheats/<ELF CRC>.pnach and applies every patch line in it, labelled or not."""
    def file(self, rom):
        _, crc = ps2_game(rom)
        return os.path.join(AETHER, "cheats", crc + ".pnach") if crc else None

    def ini(self):
        return os.path.join(AETHER, "inis", "PCSX2.ini"), "/usr/config/aethersx2/inis/PCSX2.ini"


# --- Mednafen (cheats/<module>.cht: "[<md5>] <name>", then "<type> A|I <len> L|B 0 <addr> <value> [compare] <name>"
# lines, each followed by a (here empty) conditions line). It keeps decoded patches only, so the database's codes are
# decoded here, as Mednafen's own cheat dialog does; a cheat with a code that doesn't decode isn't listed.
GG_NES = "APZLGITYEOXUKSVN"


def nes_gg(code):
    if len(code) not in (6, 8) or any(c not in GG_NES for c in code):
        return None
    t = [GG_NES.index(c) for c in code]
    a, v, c = 0x8000, (t[0] & 7) | ((t[0] & 8) << 4) | ((t[1] & 7) << 4), 0
    a |= ((t[1] & 8) << 4) | ((t[2] & 7) << 4) | ((t[3] & 7) << 12) | (t[3] & 8) | (t[4] & 7) | ((t[4] & 8) << 8)
    a |= (t[5] & 7) << 8
    if len(code) == 6:
        return ("S", 1, a, v | (t[5] & 8), None)
    c = (t[5] & 8) | (t[6] & 7) | ((t[6] & 8) << 4) | ((t[7] & 7) << 4)
    return ("C", 1, a, v | (t[7] & 8), c)


def gb_gg(code):
    raw = code.replace("-", "")
    if len(raw) not in (6, 9) or not re.fullmatch(r"[0-9A-F]+", raw):
        return None
    n = [int(x, 16) for x in raw]
    addr, val = ((n[5] << 12) | (n[2] << 8) | (n[3] << 4) | n[4]) ^ 0xF000, (n[0] << 4) | n[1]
    if len(raw) == 6:
        return ("S", 1, addr, val, None)
    cmp = (n[6] << 4) | n[8]
    return ("C", 1, addr, val, (((cmp >> 2) | (cmp << 6)) & 0xFF) ^ 0xBA)


def gb_gs(code):
    if not re.fullmatch(r"[0-9A-F]{8}", code):
        return None
    bank, la = int(code[:2], 16), int(code[6:8] + code[4:6], 16)
    addr = 0x10000 | ((bank & 7) << 12) | (la & 0xFFF) if 0xD000 <= la <= 0xDFFF else la
    return ("R", 1, addr, int(code[2:4], 16), None)


def snes_gg(code):
    if not re.fullmatch(r"[0-9A-F]{4}-[0-9A-F]{4}", code):
        return None
    sub = [0x4, 0x6, 0xD, 0xE, 0x2, 0x7, 0x8, 0x3, 0xB, 0x5, 0xC, 0x9, 0xA, 0x0, 0xF, 0x1]
    ev = 0
    for ch in code.replace("-", ""):
        ev = (ev << 4) | sub[int(ch, 16)]
    bm = [6, 7, 8, 9, 16, 17, 18, 19, 14, 15, 0, 1, 20, 21, 22, 23, 2, 3, 4, 5, 10, 11, 12, 13]
    return ("S", 1, sum(((ev >> b) & 1) << i for i, b in enumerate(bm)), ev >> 24, None)


def raw_write(code, lo=0, hi=0xFFFFFFFF, rom=None, big=False):
    """"AAAAAA:VV" or "AAAAAA:VVVV": a RAM write (R) in [lo, hi]; at or above `rom`, a ROM read substitution (S)."""
    m = re.fullmatch(r"([0-9A-F]{4,8}):([0-9A-F]{2}|[0-9A-F]{4})", code)
    if not m:
        return None
    addr, val, size = int(m.group(1), 16), int(m.group(2), 16), len(m.group(2)) // 2
    if rom is not None and addr >= rom and size == 1:
        return ("S", 1, addr, val, None)
    if not lo <= addr <= hi:
        return None
    return ("R", size, addr, val, None, big)


def nes_decode(code):
    return nes_gg(code) or raw_write(code, 0, 0x7FFF, rom=0x8000)


def gb_decode(code):
    return gb_gs(code) or gb_gg(code)


def snes_decode(code):
    if re.fullmatch(r"[0-9A-F]{8}", code):
        return ("R", 1, int(code[:6], 16), int(code[6:], 16), None)
    return snes_gg(code) or raw_write(code)


def sms_decode(code):        # Pro Action Replay "00AA-AAVV": a RAM write
    m = re.fullmatch(r"00([0-9A-F]{2})-([0-9A-F]{2})([0-9A-F]{2})", code)
    return ("R", 1, int(m.group(1) + m.group(2), 16), int(m.group(3), 16), None) if m else None


def gba_decode(parts):
    """Code Breaker, unencrypted: "3AAAAAAA+00VV" an 8-bit write, "8AAAAAAA+VVVV" a 16-bit one."""
    out = []
    if len(parts) % 2:
        return None
    for i in range(0, len(parts), 2):
        a, v = parts[i], parts[i + 1]
        if not re.fullmatch(r"[38][0-9A-F]{7}", a) or not re.fullmatch(r"[0-9A-F]{4}", v):
            return None
        size = 1 if a[0] == "3" else 2
        out.append(("R", size, int(a[1:], 16), int(v, 16) & (0xFF if size == 1 else 0xFFFF), None))
    return out


MEDNAFEN = {   # module: (decoder of one code part, big-endian, ROM extensions)
    "gb": (gb_decode, False), "gba": (None, False), "nes": (nes_decode, False), "snes_faust": (snes_decode, False),
    "md": (lambda c: raw_write(c, 0xFF0000, 0xFFFFFF, big=True), True), "sms": (sms_decode, False),
    "gg": (sms_decode, False), "pce": (lambda c: raw_write(c, 0x1F0000, 0x1F7FFF), False),
    "pce_fast": (lambda c: raw_write(c, 0x1F0000, 0x1F7FFF), False),
}


def rom_bytes(rom):
    """The ROM's data, out of a .zip as Mednafen does (its first file that isn't text)."""
    if rom.lower().endswith(".zip"):
        with zipfile.ZipFile(rom) as z:
            names = [n for n in z.namelist() if not n.endswith("/") and not n.lower().endswith((".txt", ".nfo", ".diz"))]
            return z.read(names[0]) if names else b""
    with open(rom, "rb") as f:
        return f.read()


def mednafen_id(module, rom):
    """The ID Mednafen keys a game's cheats by (its MDFNGameInfo->MD5), or None."""
    try:
        data = rom_bytes(rom)
    except (OSError, zipfile.BadZipFile, KeyError):
        return None
    if module == "gb":
        if len(data) < 0x150 or data[0x148] > 8:
            return None
        size = 0x8000 << data[0x148]
        data = data[:size].ljust(size, b"\xff")
    elif module == "nes":
        if data[:4] != b"NES\x1a":
            return None
        prg, chr_ = (data[4] or 256) * 0x4000, data[5] * 0x2000
        start = 16 + (512 if data[6] & 4 else 0)
        data = data[start:start + prg + chr_]
    elif module == "snes_faust":     # the first 16 bytes of the SHA-1, after a copier header
        data = data[512:] if len(data) & 0x7FFF == 512 else data
        return hashlib.sha1(data).hexdigest()[:32]
    elif module in ("sms", "gg", "pce", "pce_fast"):
        data = data[512:] if len(data) & 512 else data
    elif module not in ("gba", "md"):
        return None
    return hashlib.md5(data).hexdigest()


def mednafen_lines(module, code):
    """A cheat's patches [(type, length, addr, value, compare, big)], or None if any part doesn't decode."""
    dec, big = MEDNAFEN[module]
    parts = [p.strip().upper() for p in re.split(r"[+;,]", code) if p.strip()]
    if not parts:
        return None
    if module == "gba":
        out = gba_decode(parts)
        return [p + (False,) for p in out] if out else None
    out = []
    for p in parts:
        d = dec(p)
        if not d:
            return None
        out.append(d if len(d) == 6 else d + (big,))
    return out


class Mednafen:
    def module(self, core):
        return core if core in MEDNAFEN else None

    def coded(self, src, module):
        out = []
        for c in cht_read(src):
            lines = mednafen_lines(module, c["values"].get(f"cheat{c['i']}_code", ""))
            if lines and not any(n == c["name"] for n, _ in out):
                out.append((c["name"], lines))
        return out

    def source(self, system, rom):
        folder = RA_SYSTEMS.get(system)
        return best_file(os.path.join(RA_DB, folder), rom) if folder else None

    def listing(self, src, core):
        module = self.module(core)
        return [n for n, _ in self.coded(src, module)]

    def apply(self, system, rom, core, src, on):
        module = self.module(core)
        gid = mednafen_id(module, rom) if module else None
        if not gid:
            return False
        path = os.path.join(MEDNAFEN_OUT, module + ".cht")
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                text = f.read()
        except OSError:
            text = ""
        blocks = [[]]                     # [lines before any section], then one list per section
        for line in text.splitlines(keepends=True):
            if line.startswith("["):
                blocks.append([])
            blocks[-1].append(line)
        mine = f"[{gid}] {MEDNAFEN_MARK}"
        if any(b and b[0].lower().startswith(f"[{gid}]") and not b[0].startswith(mine) for b in blocks[1:]):
            return False                  # the user's own cheats for this game, from Mednafen's dialog
        blocks = [b for b in blocks if not (b and b[0].startswith(mine))]
        chosen = [(n, l) for n, l in self.coded(src, module) if n in on] if src else []
        if chosen:
            sec = [mine + "\n"]
            for name, patches in chosen:
                for t, size, addr, val, cmp, big in patches:
                    fmt = "%02x" if size == 1 else "%04x"
                    vals = (fmt % val) + (" " + fmt % cmp if t == "C" else "")
                    sec += [f"{t} A {size} {'B' if big else 'L'} 0 {addr:08x} {vals} {name}\n", "\n"]
            blocks.append(sec)
        new = "".join("".join(b) for b in blocks)
        if new != text:
            write_file(path, new)
        return bool(chosen)


# --- Flycast (RetroArch's .cht, decoded entries: cheatN_address/_value/...; libretro's Dreamcast files are that) -----
FLYCAST_MARK = ";" + MARK.lstrip("#")     # a ";" line is a comment to Flycast's ini parser


def flycast_cheat_path(cfg):
    """emu.cfg's Dreamcast.CheatPath with our folder in it (Flycast looks for <rom file name>.cht in each)."""
    lines = cfg.splitlines()
    for i, line in enumerate(lines):
        m = re.match(r"\s*Dreamcast\.CheatPath\s*=\s*(.*)$", line)
        if m:
            if FLYCAST_OUT in m.group(1):
                return cfg
            lines[i] = f"Dreamcast.CheatPath = {m.group(1) + ';' if m.group(1).strip() else ''}{FLYCAST_OUT}"
            return "\n".join(lines) + "\n"
    for i, line in enumerate(lines):
        if line.strip() == "[config]":
            lines.insert(i + 1, f"Dreamcast.CheatPath = {FLYCAST_OUT}")
            return "\n".join(lines) + "\n"
    return cfg + f"\n[config]\nDreamcast.CheatPath = {FLYCAST_OUT}\n"


class Flycast(RetroArch):
    """The game's file in a folder of ours on Flycast's cheat path, as <rom file name>.cht. Flycast then remembers
    it for the game (emu.cfg's [cheats]); a file the user picks in Flycast replaces that, and wins."""
    def apply(self, system, rom, core, src, on):
        dst = os.path.join(FLYCAST_OUT, os.path.basename(rom) + ".cht")
        if not src or not on:
            if os.path.exists(dst):
                os.remove(dst)
            return False
        cht_write(src, dst, set(on), FLYCAST_MARK)
        try:
            with open(FLYCAST_CFG, encoding="utf-8", errors="replace") as f:
                cfg = f.read()
        except OSError:
            cfg = ""
        new = flycast_cheat_path(cfg)
        if new != cfg:
            write_file(FLYCAST_CFG, new)
        return True


# --- mupen64plus (mupencheat.txt: "crc <CRC1>-<CRC2>-C:<country>", " cn <name>", "  <code>" lines; a "????" code
# picks a value from its options) ----------------------------------------------------------------------------------
def n64_section(rom):
    """mupencheat.txt's key for a ROM, from its header in any byte order (.z64, .v64, .n64; or in a .zip)."""
    try:
        if rom.lower().endswith(".zip"):
            with zipfile.ZipFile(rom) as z:
                names = [n for n in z.namelist() if not n.endswith("/")]
                head = z.open(names[0]).read(0x40) if names else b""
        else:
            with open(rom, "rb") as f:
                head = f.read(0x40)
    except (OSError, zipfile.BadZipFile, KeyError):
        return None
    if len(head) < 0x40:
        return None
    if head[:4] == bytes.fromhex("37804012"):
        head = b"".join(head[i + 1:i + 2] + head[i:i + 1] for i in range(0, 0x40, 2))
    elif head[:4] == bytes.fromhex("40123780"):
        head = b"".join(head[i:i + 4][::-1] for i in range(0, 0x40, 4))
    elif head[:4] != bytes.fromhex("80371240"):
        return None
    return "%08X-%08X-C:%X" % (int.from_bytes(head[0x10:0x14], "big"), int.from_bytes(head[0x14:0x18], "big"), head[0x3E])


def mupen_cheats(path, section):
    """[(name, [code lines])] of the ROM's section; a cheat with options is one entry per option ("name: option")."""
    out, take, cur = [], False, None
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if line.startswith("crc "):
                take = line[4:].strip().upper() == section
                cur = None
            elif take and line.startswith("cn "):
                cur = [line[3:].strip(), []]
                out.append(cur)
            elif take and cur and re.match(r"[0-9A-Fa-f]{8} ", line):
                cur[1].append(line)
    flat = []
    for name, lines in out:
        var = [l for l in lines if "????" in l]
        if not var:
            flat.append((name, lines))
            continue
        for value, label in re.findall(r'([0-9A-Fa-f]{2,4}):"([^"]*)"', var[0]):
            fixed = [l.split("????")[0] + value if l is var[0] else l for l in lines]
            flat.append((f"{name}: {label}", fixed))
    return [(n, l) for n, l in flat if l]


class Mupen64Plus:
    """The ROM's cheats from mupen64plus's own database (by the header's CRCs), else libretro's N64 .cht (by name).
    Written as a one-game mupencheat.txt holding only the chosen ones; the start script hands it to mupen64plus
    with --cheats all."""
    def source(self, system, rom):
        section = n64_section(rom)
        if section and os.path.exists(N64_DB) and mupen_cheats(N64_DB, section):
            return f"{N64_DB}|{section}"
        return best_file(os.path.join(RA_DB, "Nintendo - Nintendo 64"), rom)

    def coded(self, src):
        if "|" in src:
            return mupen_cheats(*src.split("|"))
        out = []
        for c in cht_read(src):
            lines = [l.strip() for l in c["values"].get(f"cheat{c['i']}_code", "").split(";")]
            if lines and all(re.fullmatch(r"[0-9A-Fa-f]{8} [0-9A-Fa-f]{4}", l) for l in lines):
                out.append((c["name"], lines))
        return out

    def cheats(self, src):
        return [n for n, _ in self.coded(src)]

    def apply(self, system, rom, core, src, on):
        if os.path.exists(N64_OUT):
            os.remove(N64_OUT)
        section = n64_section(rom)
        chosen = [(n, l) for n, l in self.coded(src) if n in on] if src and section else []
        if not chosen:
            return False
        text = [f"crc {section}", "gn " + os.path.basename(rom)]
        for name, lines in chosen:
            text += [" cn " + name.replace("\\", "/")] + ["  " + l for l in lines]
        write_file(N64_OUT, "\n".join(text) + "\n")
        return True


# --- DuckStation (cheats/<serial>.cht: "[name]", "Type = Gameshark", "Activation = EndFrame", code lines; the ones on
# are "Enable = <name>" lines in [Cheats] of the game's gamesettings/<serial>.ini, with EnableCheats on) ------------
def disc_track(rom):
    """The data file of a .cue or .m3u (its first entry), else the file itself."""
    for _ in range(3):
        low = rom.lower()
        if not low.endswith((".cue", ".m3u")):
            return rom
        try:
            with open(rom, encoding="utf-8", errors="replace") as f:
                text = f.read()
        except OSError:
            return rom
        if low.endswith(".cue"):
            m = re.search(r'FILE\s+"([^"]+)"', text) or re.search(r"FILE\s+(\S+)", text)
        else:
            m = re.search(r"^\s*([^#\s].*?)\s*$", text, re.M)
        if not m:
            return rom
        rom = os.path.join(os.path.dirname(rom), m.group(1))
    return rom


def psx_serial(rom):
    """SLUS-00508 from SYSTEM.CNF's BOOT line (.bin/.cue, .iso, .m3u; not .chd or .pbp)."""
    try:
        cnf = iso_file(Image(disc_track(rom)), "SYSTEM.CNF")
    except (OSError, ValueError, zlib.error, IndexError):
        return None
    m = re.search(rb"BOOT\s*=\s*cdrom:\\?([A-Z]{4})_(\d{3})\.(\d{2})", cnf or b"")
    return "%s-%s%s" % tuple(g.decode() for g in m.groups()) if m else None


DUCK_MARK = "; Asgard cheats on: "      # in the game's settings ini: the names Asgard switched on


class DuckStation:
    """libretro-database's PlayStation .cht (GameShark codes), as DuckStation's cheats/<serial>.cht; the chosen ones
    switched on in the game's settings ini, beside the user's own settings and cheats."""
    def source(self, system, rom):
        return best_file(os.path.join(RA_DB, "Sony - PlayStation"), rom) if psx_serial(rom) else None

    def coded(self, src):
        out = []
        for c in cht_read(src):
            words = [w.strip() for w in re.split(r"[+\s]+", c["values"].get(f"cheat{c['i']}_code", "")) if w.strip()]
            if words and len(words) % 2 == 0 and all(re.fullmatch(r"[0-9A-Fa-f]{8}", words[i]) and
                                                     re.fullmatch(r"[0-9A-Fa-f]{4}", words[i + 1])
                                                     for i in range(0, len(words), 2)):
                name = re.sub(r"[\[\]\r\n]", "", c["name"]).strip()
                if name and not any(n == name for n, _ in out):
                    out.append((name, [f"{words[i]} {words[i + 1]}" for i in range(0, len(words), 2)]))
        return out

    def cheats(self, src):
        return [n for n, _ in self.coded(src)]

    def apply(self, system, rom, core, src, on):
        serial = psx_serial(rom)
        if not serial:
            return False
        cht = os.path.join(DUCK, "cheats", serial + ".cht")
        ini_path = os.path.join(DUCK, "gamesettings", serial + ".ini")
        try:
            with open(ini_path, encoding="utf-8", errors="replace") as f:
                sections = ini_sections(f.read())
        except OSError:
            sections = [(None, [])]
        before = []
        for line in sections[0][1]:
            if line.startswith(DUCK_MARK):
                try:
                    before = json.loads(line[len(DUCK_MARK):])
                except ValueError:
                    pass
        exists, mine = ours(cht, MARK.replace("#", ";", 1))
        chosen = [(n, l) for n, l in self.coded(src) if n in on] if src else []
        if exists and not mine:
            chosen = []                  # a cheat file the user made: theirs, and so are its switches
        if not chosen and not before:
            return False
        if mine:
            os.remove(cht)
        if chosen:
            text = [MARK.replace("#", ";", 1)]
            for name, lines in chosen:
                text += ["", f"[{name}]", "Type = Gameshark", "Activation = EndFrame"] + lines
            write_file(cht, "\n".join(text) + "\n")
        heads = [h for h, _ in sections]
        names = [n for n, _ in chosen]
        for head, keep in (("Cheats", names), ("Console", None)):
            if head not in heads:
                if not names:
                    continue
                sections.append((head, []))
                heads.append(head)
            body = sections[heads.index(head)][1]
            if head == "Cheats":
                body[:] = [l for l in body if not re.match(r"\s*Enable\s*=\s*(.*?)\s*$", l) or
                           re.match(r"\s*Enable\s*=\s*(.*?)\s*$", l).group(1) not in set(before) | set(names)]
                body[:] = [l for l in body if l.strip()] + [f"Enable = {n}" for n in names] + [""]
            elif names:
                body[:] = [l for l in body if not re.match(r"\s*EnableCheats\s*=", l) and l.strip()] + \
                          ["EnableCheats = true", ""]
        pre = [l for l in sections[0][1] if not l.startswith(DUCK_MARK)]
        sections[0] = (None, ([DUCK_MARK + json.dumps(names)] if names else []) + pre)
        out = []
        for head, lines in sections:
            out += ([f"[{head}]"] if head is not None else []) + lines
        write_file(ini_path, "\n".join(out).strip("\n") + "\n")
        return bool(names)


MEDNAFEN_MARK = "Asgard cheats: written at launch from the game's Cheats list"


BACKENDS = {"retroarch": RetroArch(), "azahar": Azahar(), "ppsspp": PPSSPP(), "melonds": MelonDS(),
            "eden": Eden(), "eden-duo": Eden(), "dolphin": Dolphin(), "armsx2": ARMSX2(), "aethersx2": AetherSX2(),
            "mednafen": Mednafen(), "flycast": Flycast(),
            "mupen64plus": Mupen64Plus(), "drastic": DraStic(),
            "skyemu": SkyEmu(), "duckstation": DuckStation()}


def backend(emulator):
    return BACKENDS.get(emulator)


def state_path(system, rom):
    return os.path.join(STATE, system, os.path.basename(rom) + ".json")


def load_on(system, rom):
    try:
        with open(state_path(system, rom)) as f:
            return list(json.load(f).get("on", []))
    except (OSError, ValueError):
        return []


def save_on(system, rom, on):
    path = state_path(system, rom)
    if not on:
        if os.path.exists(path):
            os.remove(path)
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".new", "w") as f:
        json.dump({"on": on}, f)
    os.replace(path + ".new", path)


def listing(system, rom, emulator, core):
    b = backend(emulator)
    if not b:
        return {"source": "", "cheats": [], "error": NO_CHEATS.get(emulator, f"No cheats for {emulator} yet")}
    if hasattr(b, "module") and not b.module(core):
        return {"source": "", "cheats": [], "error": f"No cheats for {emulator}'s {core} yet: set this game's emulator to RetroArch for them"}
    src = b.source(system, rom)
    if not src:
        return {"source": "", "cheats": [], "error": "No cheats found for this game"}
    on = set(load_on(system, rom))
    names = b.listing(src, core) if hasattr(b, "listing") else b.cheats(src)
    if not names and hasattr(b, "listing"):
        return {"source": "", "cheats": [], "error": f"No cheats for this game that {emulator} can run"}
    return {"source": os.path.basename(src), "cheats": [{"name": n, "on": n in on} for n in names]}


def main(argv):
    if len(argv) < 5 or argv[0] not in ("list", "set", "apply"):
        sys.exit(__doc__)
    cmd, system, rom, emulator, core = argv[:5]
    if cmd == "list":
        print(json.dumps(listing(system, rom, emulator, core)))
    elif cmd == "set":
        name, value = argv[5], argv[6]
        on = [n for n in load_on(system, rom) if n != name]
        if value == "on":
            on.append(name)
        save_on(system, rom, on)
        print(json.dumps(listing(system, rom, emulator, core)))
    else:
        b = backend(emulator)
        if os.path.exists(ON_FLAG):
            os.remove(ON_FLAG)
        if b:
            on = load_on(system, rom)
            if b.apply(system, rom, core, b.source(system, rom) if on else None, on):
                open(ON_FLAG, "w").close()


if __name__ == "__main__":
    main(sys.argv[1:])
