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
A cheat file the user made in the emulator itself (no MARK line at the top) is never replaced or removed.
"""
import difflib
import json
import os
import re
import sys

STATE = os.environ.get("ASGARD_CHEATS_STATE", "/storage/.config/asgard/cheats")
RA_DB = os.environ.get("ASGARD_CHEATS_RA_DB", "/usr/share/libretro-database/cht")
RA_OUT = os.environ.get("ASGARD_CHEATS_RA_OUT", "/tmp/database/cht")       # cheat_database_path (overlay on /storage)
RA_CORES = os.environ.get("ASGARD_CHEATS_RA_CORES", "/tmp/cores")          # <core>_libretro.info: corename
RA_APPEND = os.environ.get("ASGARD_CHEATS_RA_APPEND", "/tmp/.retroarch.cfg")  # runemu.sh's --appendconfig
DB = os.environ.get("ASGARD_CHEATS_DB", "/usr/share/asgard-cheats")          # asgard-cheats-db
AZAHAR_OUT = os.environ.get("ASGARD_CHEATS_AZAHAR_OUT", "/storage/.config/azahar/cheats")
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


BACKENDS = {"retroarch": RetroArch(), "azahar": Azahar()}


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
        return {"source": "", "cheats": [], "error": f"No cheats for {emulator} yet"}
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
        if b:
            on = load_on(system, rom)
            b.apply(system, rom, core, b.source(system, rom) if on else None, on)


if __name__ == "__main__":
    main(sys.argv[1:])
