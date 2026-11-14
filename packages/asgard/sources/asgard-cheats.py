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
  Eden       switch-cheats-db's switch/<title ID>.json ({build ID: {"[name]": code}}); written as Eden's mod
             load/<title ID>/Asgard Cheats/cheats/<build ID>.txt for every build ID, with only the cheats that are on
             (Eden runs every cheat in a file it loads, and loads only the file for the running build). The title ID
             is in the file name ([0100...]) or an NSP's ticket name; an XCI without it in the name isn't read.
  Dolphin    the codes in the image's GameSettings/<game ID>.ini ([ActionReplay], [Gecko]; not the ones it enables by
             default); written as "$name" lines in [*_Enabled] of the user's GameSettings/<game ID>.ini, which also holds
             the game's other settings, so only those lines change. The game ID is the disc's first 6 bytes (.iso, .rvz,
             .wbfs, .ciso, .gcz). The start script switches Dolphin's EnableCheats on while ON_FLAG exists.
A cheat file the user made in the emulator itself (no MARK line at the top) is never replaced or removed.
"""
import difflib
import json
import os
import re
import shutil
import sys
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
    "mednafen": "No cheats for Mednafen yet: set this game's emulator to RetroArch for them",
}
EDEN_LOAD = os.environ.get("ASGARD_CHEATS_EDEN_LOAD", "/storage/.local/share/eden/load")   # Eden and Eden Duo
EDEN_MOD = "Asgard Cheats"    # our mod folder: everything in it is ours
DOLPHIN_DB = os.environ.get("ASGARD_CHEATS_DOLPHIN_DB", "/usr/config/dolphin-emu/GameSettings")    # the image's copy
DOLPHIN_OUT = os.environ.get("ASGARD_CHEATS_DOLPHIN_OUT", "/storage/.config/dolphin-emu/GameSettings")
# Set while the game starting has cheats on: for start scripts that rewrite their emulator's master switch (Dolphin)
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


def cht_write(src, dst, on):
    """src with cheatN_enable set from `on` (names), everything else as it was."""
    cheats = {c["i"]: c["name"] for c in cht_read(src)}
    out = [MARK + "\n"]
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
        if self.cso:
            total, self.block, self.align = int.from_bytes(head[8:16], "little"), int.from_bytes(head[16:20], "little"), head[21]
            n = (total + self.block - 1) // self.block + 1
            raw = self.f.read(4 * n)
            self.index = [int.from_bytes(raw[i:i + 4], "little") for i in range(0, len(raw), 4)]

    def read(self, offset, size):
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
    """A file in the ISO9660 root directory, or None."""
    pvd = img.read(16 * 2048, 2048)
    if pvd[1:6] != b"CD001":
        return None
    lba, size = int.from_bytes(pvd[158:162], "little"), int.from_bytes(pvd[166:170], "little")
    d, i = img.read(lba * 2048, size), 0
    while i < len(d):
        n = d[i]
        if n == 0:                       # records don't cross a sector: on to the next one
            i = (i // 2048 + 1) * 2048
            continue
        ident = d[i + 33:i + 33 + d[i + 32]].decode("ascii", "replace").split(";")[0]
        if ident.upper() == name:
            return img.read(int.from_bytes(d[i + 2:i + 6], "little") * 2048, int.from_bytes(d[i + 10:i + 14], "little"))
        i += n
    return None


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


BACKENDS = {"retroarch": RetroArch(), "azahar": Azahar(), "ppsspp": PPSSPP(), "melonds": MelonDS(),
            "eden": Eden(), "eden-duo": Eden(), "dolphin": Dolphin()}


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
    src = b.source(system, rom)
    if not src:
        return {"source": "", "cheats": [], "error": "No cheats found for this game"}
    on = set(load_on(system, rom))
    return {"source": os.path.basename(src), "cheats": [{"name": n, "on": n in on} for n in b.cheats(src)]}


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
