#!/usr/bin/env python3
# Scrape one game into ES-DE's layout, which Asgard Home reads (Select on a game > Scrape this game; Settings > Library >
# Scrape missing runs it once per game without a cover). Prints JSON.
#   asgard-scrape.py <system> <rom path> <stem>
#   asgard-scrape.py --index <libretro-database tree> <out dir>    (at image build time: writes INDEX)
# Sources, first that finds the game (SCRAPE-1):
# 1. ScreenScraper's API directly, when system.cfg has an Asgard developer ID (screenscraper.devid / .devpassword; none
#    yet: written against its documented API v2, untested).
# 2. ScreenScraper through Skyscraper, when the user signed in (Settings > Library > ScreenScraper account:
#    screenscraper.username / .password). Skyscraper carries its own developer ID. Description, developer, publisher,
#    date, genre, players, cover, screenshot, marquee; Switch too. It reads every ROM whole to checksum it (~20 s/GB). It writes into a scratch folder and only this game's
#    entry and art are copied over, since it rewrites a whole gamelist.
# 3. libretro, for a game the others didn't find or gave no cover: the game is found in an index of
# libretro-database shipped in the image (by CRC, else by name), which gives its exact No-Intro/Redump name and its
# details (developer, publisher, genre, date, players; a description for PS1/PS2) offline; the cover and screenshot
# come from libretro-thumbnails on GitHub by that name. thumbnails.libretro.com, used before, serves nothing since 2026-11.
import json, os, re, shutil, subprocess, sys, tempfile, urllib.error, urllib.parse, urllib.request, zipfile, zlib
import xml.etree.ElementTree as ET

ROOT = "/storage/ES-DE"
CFG = "/storage/.config/system/configs/system.cfg"
INDEX = os.environ.get("ASGARD_SCRAPE_INDEX", "/usr/share/asgard/scrape-index")
THUMBS = "https://raw.githubusercontent.com/libretro-thumbnails/"
SKYSCRAPER = os.environ.get("ASGARD_SKYSCRAPER", "/usr/bin/Skyscraper")
SKY_ARTWORK = "/etc/skyscraper/asgard-artwork.xml"
# ROCKNIX system names Skyscraper calls something else; the rest are the same
SKY_PLATFORMS = {"gamecube": "gc", "genesis": "megadrive", "megadrive-japan": "megadrive", "sfc": "snes", "famicom": "nes",
                 "megacd": "segacd", "tg16": "pcengine", "tg16cd": "pcenginecd", "neocd": "neogeocd",
                 "colecovision": "coleco", "fbn": "fba"}
SKY_FIELDS = ("name", "desc", "developer", "publisher", "genre", "releasedate", "players")
# ES system -> (libretro playlist, ScreenScraper systemeid; None where unchecked)
SYSTEMS = {
    "nes": ("Nintendo - Nintendo Entertainment System", 3), "snes": ("Nintendo - Super Nintendo Entertainment System", 4),
    "n64": ("Nintendo - Nintendo 64", 14), "gb": ("Nintendo - Game Boy", 9), "gbc": ("Nintendo - Game Boy Color", 10),
    "gba": ("Nintendo - Game Boy Advance", 12), "nds": ("Nintendo - Nintendo DS", 15), "3ds": ("Nintendo - Nintendo 3DS", 17),
    "gamecube": ("Nintendo - GameCube", 13), "wii": ("Nintendo - Wii", 16), "switch": (None, 225),
    "psx": ("Sony - PlayStation", 57), "ps2": ("Sony - PlayStation 2", 58), "psp": ("Sony - PlayStation Portable", 61),
    "megadrive": ("Sega - Mega Drive - Genesis", 1), "genesis": ("Sega - Mega Drive - Genesis", 1),
    "mastersystem": ("Sega - Master System - Mark III", 2), "gamegear": ("Sega - Game Gear", 21),
    "dreamcast": ("Sega - Dreamcast", 23), "saturn": ("Sega - Saturn", 22), "segacd": ("Sega - Mega-CD - Sega CD", 20),
    "pcengine": ("NEC - PC Engine - TurboGrafx 16", 31), "atari2600": ("Atari - 2600", 26), "ngp": ("SNK - Neo Geo Pocket", 25),
    "ngpc": ("SNK - Neo Geo Pocket Color", 82), "wonderswan": ("Bandai - WonderSwan", 45),
    "wonderswancolor": ("Bandai - WonderSwan Color", 46), "virtualboy": ("Nintendo - Virtual Boy", 11),
    # ROCKNIX's other names for the same systems, and more of its systems libretro has art for
    "sfc": ("Nintendo - Super Nintendo Entertainment System", None), "famicom": ("Nintendo - Nintendo Entertainment System", None),
    "fds": ("Nintendo - Family Computer Disk System", None), "n64dd": ("Nintendo - Nintendo 64DD", None),
    "pokemini": ("Nintendo - Pokemon Mini", None), "satellaview": ("Nintendo - Satellaview", None),
    "sufami": ("Nintendo - Sufami Turbo", None), "megadrive-japan": ("Sega - Mega Drive - Genesis", None),
    "megacd": ("Sega - Mega-CD - Sega CD", None), "sega32x": ("Sega - 32X", None), "sg-1000": ("Sega - SG-1000", None),
    "tg16": ("NEC - PC Engine - TurboGrafx 16", None), "supergrafx": ("NEC - PC Engine SuperGrafx", None),
    "pcenginecd": ("NEC - PC Engine CD - TurboGrafx-CD", None), "tg16cd": ("NEC - PC Engine CD - TurboGrafx-CD", None),
    "pcfx": ("NEC - PC-FX", None), "atari5200": ("Atari - 5200", None), "atari7800": ("Atari - 7800", None),
    "atarilynx": ("Atari - Lynx", None), "atarijaguar": ("Atari - Jaguar", None), "colecovision": ("Coleco - ColecoVision", None),
    "intellivision": ("Mattel - Intellivision", None), "vectrex": ("GCE - Vectrex", None), "odyssey2": ("Magnavox - Odyssey2", None),
    "channelf": ("Fairchild - Channel F", None), "msx": ("Microsoft - MSX", None), "msx2": ("Microsoft - MSX2", None),
    "3do": ("The 3DO Company - 3DO", None), "neocd": ("SNK - Neo Geo CD", None), "cdi": ("Philips - CD-i", None),
    "supervision": ("Watara - Supervision", None), "scv": ("Epoch - Super Cassette Vision", None),
}
# GoodTools region codes in ROM names -> No-Intro region names libretro uses
REGIONS = {"U": "USA", "E": "Europe", "J": "Japan", "UE": "USA, Europe", "JU": "Japan, USA", "W": "World", "F": "France",
           "G": "Germany", "S": "Spain", "I": "Italy", "K": "Korea", "A": "Australia", "EUR": "Europe"}
COLS = ("name", "crc", "developer", "publisher", "genre", "year", "month", "players", "desc")
HASH_MAX = 64 << 20   # bigger files (discs) are matched by name only


class Offline(Exception):
    pass


def setting(key):
    try:
        for line in open(CFG):
            k, _, v = line.rstrip("\n").partition("=")
            if k == key:
                return v
    except OSError:
        pass
    return ""


def fetch(url, binary=False):
    req = urllib.request.Request(url, headers={"User-Agent": "AsgardOS-scraper/2"})
    with urllib.request.urlopen(req, timeout=20) as r:
        data = r.read()
    return data if binary else data.decode("utf-8", "replace")


def title(name):
    """The file name without its folder, tags, ' # NDS'-style suffixes or release numbers."""
    name = re.sub(r"\s+#\s+\S+$", "", os.path.basename(name))   # "Pokemon - White Version 2 # NDS"
    return re.sub(r"^\d+\s*-\s*", "", re.sub(r"\([^)]*\)|\[[^]]*\]", "", name).strip())   # "0171 - Golden Sun"


def base(name):
    """Title without tags or punctuation: 'Legend of Zelda, The - A Link to the Past (U) [!]' -> 'legendofzeldathealinktothepast'."""
    name = title(name).lower()
    name = re.sub(r"^the\s+|,\s*the\b", "", name)              # "The Legend of Zelda" = "Legend of Zelda, The"
    return re.sub(r"[^a-z0-9]", "", name)


def regions(name):
    """The region words in a name's tags: '(U) [!]' -> {'usa'}, '(Europe) (En,Fr)' -> {'europe'}."""
    out = set()
    for tag in re.findall(r"\(([^)]*)\)", name):
        tag = REGIONS.get(tag.strip(), tag)
        out |= {w.strip().lower() for w in tag.split(",")}
    return out


def ranked(stem, names):
    """The names that are this ROM's title, best first: the most region overlap, then USA/World/Europe, then the shortest.
    A ROM named without the leading article etc. falls back to names that contain its title."""
    stem = os.path.basename(stem)
    wants = {base(p) for p in stem.split(" ~ ")} - {""}       # "Lock n' Chase ~ Lock 'n' Chase (World)"
    regs = regions(stem)
    cands = [n for n in names if {base(p) for p in n.split(" ~ ")} & wants]
    if not cands:
        cands = [n for n in names if any(w in base(n) for w in wants)]
    pref = ["usa", "world", "europe"]
    score = lambda n: (len(regs & regions(n)), max((3 - pref.index(r) for r in regions(n) if r in pref), default=0), -len(n))
    return sorted(cands, key=score, reverse=True)


def best(stem, names):
    r = ranked(stem, names)
    return r[0] if r else None


def save(data, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".tmp", "wb") as f:
        f.write(data)
    os.replace(path + ".tmp", path)


# --- the index (built at image time from libretro-database) ------------------------------------------------------
TOKEN = re.compile(r'"((?:[^"\\]|\\.)*)"|([()])|([^\s()"]+)')


def parse_dat(text):
    """clrmamepro .dat -> [{key: value}] per game; the rom's crc and serial are lifted to the game."""
    games, stack, key = [], [], None
    cur = None
    for m in TOKEN.finditer(text):
        q, paren, word = m.groups()
        if paren == "(":
            stack.append(key)
            if len(stack) == 1 and key == "game":
                cur = {}
            key = None
        elif paren == ")":
            if stack:
                if stack.pop() == "game" and not stack and cur is not None:
                    games.append(cur)
                    cur = None
            key = None
        else:
            v = q if q is not None else word
            if key is None:
                key = v
                continue
            if cur is not None and len(stack) in (1, 2):
                k = key if len(stack) == 1 else ("crc" if key == "crc" else "serial" if key == "serial" else None)
                if k == "crc":
                    cur.setdefault("crcs", set()).add(v.upper())
                elif k and k not in cur:
                    cur[k] = v
            key = None
    return games


def build_index(db, out):
    """Write <out>/<playlist>.tsv: one row per game name with its CRCs and details (COLS)."""
    os.makedirs(out, exist_ok=True)
    for pl in sorted({p for p, _ in SYSTEMS.values() if p}):
        rows, by_crc = {}, {}

        def row(name):
            return rows.setdefault(name, {"crc": set()})

        names = [f"{db}/dat/{pl}.dat"] + [f"{db}/metadat/{d}/{pl}.dat" for d in
                                           ("no-intro", "redump", "libretro-dats", "hacks", "homebrew", "developer")]
        names.append(f"{db}/metadat/no-intro/{pl} (Digital).dat")   # eShop-only games (3DS), art in the same repo
        for f in names:   # games and their names; some of these also carry details
            if os.path.exists(f):
                for g in parse_dat(open(f, encoding="utf-8", errors="replace").read()):
                    if "name" in g:
                        r = row(g["name"])
                        r["crc"] |= g.get("crcs", set())
                        for c in g.get("crcs", ()):
                            by_crc.setdefault(c, set()).add(g["name"])
                        merge(r, g)
        for d in ("developer", "publisher", "genre", "releaseyear", "releasemonth", "maxusers"):
            f = f"{db}/metadat/{d}/{pl}.dat"
            if not os.path.exists(f):
                continue
            for g in parse_dat(open(f, encoding="utf-8", errors="replace").read()):
                targets = set().union(*(by_crc.get(c, set()) for c in g.get("crcs", ()))) if g.get("crcs") else set()
                if not targets and (g.get("name") or g.get("comment")) in rows:
                    targets = {g.get("name") or g.get("comment")}
                for n in targets:
                    merge(rows[n], g)
        if not rows:
            continue
        with open(f"{out}/{pl}.tsv", "w", encoding="utf-8") as w:
            for name in sorted(rows):
                r = rows[name]
                vals = [name, " ".join(sorted(r["crc"]))] + [r.get(c, "") for c in COLS[2:]]
                w.write("\t".join(re.sub(r"\s+", " ", v).strip() for v in vals) + "\n")


def merge(r, g):
    for src, dst in (("developer", "developer"), ("publisher", "publisher"), ("genre", "genre"), ("releaseyear", "year"),
                     ("releasemonth", "month"), ("users", "players"), ("description", "desc")):
        v = g.get(src, "")
        if v and not r.get(dst) and not (dst == "desc" and v == g.get("name")):   # no-intro's description = its name
            r[dst] = v


def load(playlist):
    try:
        with open(f"{INDEX}/{playlist}.tsv", encoding="utf-8") as f:
            return [dict(zip(COLS, line.rstrip("\n").split("\t"))) for line in f]
    except OSError:
        return []


def crc_of(rom):
    """The ROM's CRC32 as libretro-database lists it: a zip's first file's, else the file's (small files only)."""
    try:
        if rom.lower().endswith(".zip"):
            with zipfile.ZipFile(rom) as z:
                infos = [i for i in z.infolist() if not i.is_dir()]
                return f"{infos[0].CRC:08X}" if infos else None
        if os.path.getsize(rom) > HASH_MAX or rom.lower().endswith((".7z", ".chd", ".rvz", ".cso", ".m3u")):
            return None
        crc = 0
        with open(rom, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                crc = zlib.crc32(chunk, crc)
        return f"{crc:08X}"
    except (OSError, zipfile.BadZipFile, IndexError):
        return None


def match(rows, rom, stem):
    """The index rows for this ROM, best first: its CRC's, then by name."""
    crc = crc_of(rom)
    hits = [r for r in rows if crc and crc in r["crc"].split()]
    names = ranked(stem, [r["name"] for r in rows])
    if hits:   # same title, other regions after it: their art is the next best
        names = [h["name"] for h in hits] + [n for n in ranked(hits[0]["name"], [r["name"] for r in rows])
                                              if n not in {h["name"] for h in hits}]
    by = {r["name"]: r for r in rows}
    return [by[n] for n in names], bool(hits)


def thumb_url(playlist, folder, name):
    """libretro-thumbnails' file for a game: &*/:`<>?\\|" become _ in the name."""
    return (THUMBS + urllib.parse.quote(playlist.replace(" ", "_")) + "/master/" + folder + "/"
            + urllib.parse.quote(re.sub(r'[&*/:`<>?\\|"]', "_", name)) + ".png")


def details(r):
    month = r.get("month", "").zfill(2) if r.get("month", "").isdigit() else "01"
    return {"developer": r.get("developer", ""), "publisher": r.get("publisher", ""), "genre": r.get("genre", ""),
            "players": r.get("players", ""), "desc": r.get("desc", ""),
            "releasedate": f"{r['year']}{month}01T000000" if r.get("year", "").isdigit() else ""}


def libretro(system, rom, stem, media):
    playlist = SYSTEMS.get(system, (None,))[0]
    rows = load(playlist) if playlist else []
    if not rows:
        return None
    cands, by_crc = match(rows, rom, stem)
    if not cands:
        return None
    top, got = cands[0], []
    for kind, folder in (("covers", "Named_Boxarts"), ("screenshots", "Named_Snaps")):
        for r in cands[:4]:   # the match first, then the same game's other regions
            try:
                save(fetch(thumb_url(playlist, folder, r["name"]), True), f"{media}/{kind}/{stem}.png")
                got.append(kind)
                break
            except urllib.error.HTTPError:
                continue
            except OSError as e:
                raise Offline() from e
    meta = {k: v for k, v in details(top).items() if v}
    gamelist(system, stem + os.path.splitext(rom)[1], meta, keep=True)
    return {"source": "libretro", "matched": top["name"], "by": "checksum" if by_crc else "name", "media": got,
            "details": sorted(meta)}


def screenscraper(system, rom, stem, media):
    devid, devpw = setting("screenscraper.devid"), setting("screenscraper.devpassword")
    ssid = SYSTEMS.get(system, (None, None))[1]
    if not (devid and devpw and ssid):
        return None
    size = os.path.getsize(rom)
    q = {"devid": devid, "devpassword": devpw, "softname": "AsgardOS", "output": "json", "systemeid": ssid,
         "romtype": "rom", "romnom": os.path.basename(rom), "romtaille": size,
         "ssid": setting("screenscraper.username"), "sspassword": setting("screenscraper.password")}
    if size < HASH_MAX:   # checksum small ROMs; discs are matched by name and size
        crc = 0
        with open(rom, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                crc = zlib.crc32(chunk, crc)
        q["crc"] = f"{crc:08X}"
    try:
        jeu = json.loads(fetch("https://api.screenscraper.fr/api2/jeuInfos.php?" + urllib.parse.urlencode(q)))["response"]["jeu"]
    except (OSError, ValueError, KeyError):
        return None
    pick = lambda items, key="text": next((i[key] for lang in ("en", "us", "wor", "eu", "ss")
                                           for i in items or [] if lang in (i.get("langue"), i.get("region"))), "")
    meta = {"name": pick(jeu.get("noms")), "desc": pick(jeu.get("synopsis")),
            "developer": (jeu.get("developpeur") or {}).get("text", ""),
            "releasedate": re.sub(r"\D", "", pick(jeu.get("dates")))[:8].ljust(8, "0") + "T000000" if jeu.get("dates") else "",
            "genre": pick([n for g in jeu.get("genres", []) for n in g.get("noms", [])])}
    got = []
    for kind, typ in (("covers", "box-2D"), ("screenshots", "ss"), ("marquees", "wheel")):
        url = pick([m for m in jeu.get("medias", []) if m.get("type") == typ], "url")
        if url:
            try:
                save(fetch(url, True), f"{media}/{kind}/{stem}.png")
                got.append(kind)
            except OSError:
                pass
    gamelist(system, stem + os.path.splitext(rom)[1], {k: v for k, v in meta.items() if v})
    return {"source": "ScreenScraper", "matched": meta["name"], "media": got, "details": sorted(k for k, v in meta.items() if v)}


def skyscraper(system, rom, stem, media):
    """ScreenScraper through Skyscraper, signed in as the user: gather this ROM into Skyscraper's cache, generate ES-DE
    output for it into a scratch folder, then copy its entry and art over (ROOT's gamelist keeps every other game)."""
    user, password = setting("screenscraper.username"), setting("screenscraper.password")
    if not (user and password and os.access(SKYSCRAPER, os.X_OK)):
        return None
    platform = SKY_PLATFORMS.get(system, system)
    ext = os.path.splitext(rom)[1] if os.path.isfile(rom) else ""
    rel = stem + ext
    romdir = rom[:len(rom) - len(rel)].rstrip("/") or "/"
    with tempfile.TemporaryDirectory(prefix="asgard-scrape.") as tmp:
        cfg = f"{tmp}/config.ini"   # the login goes in a private file, not on a command line others can read
        with open(os.open(cfg, os.O_WRONLY | os.O_CREAT, 0o600), "w") as f:
            f.write(f'[main]\nunattend="true"\nverbosity="0"\n[screenscraper]\nuserCreds="{user}:{password}"\n')
        run = lambda *args: subprocess.run([SKYSCRAPER, "-c", cfg, "-p", platform, "-i", romdir, *args, rom],
                                           stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=600)
        try:
            run("-s", "screenscraper")
            run("-f", "esde", "-g", f"{tmp}/gamelist", "-o", f"{tmp}/media", "-a", SKY_ARTWORK)
        except (OSError, subprocess.SubprocessError):
            return None
        try:
            # Skyscraper writes the ROM's absolute path, ES-DE a ./ one: either is this game
            entry = next((g for g in ET.parse(f"{tmp}/gamelist/gamelist.xml").getroot().iter("game")
                          if g.findtext("path") in ("./" + rel, rom)), None)
        except (OSError, ET.ParseError):
            entry = None
        if entry is None:
            return None
        meta = {k: (entry.findtext(k) or "").strip() for k in SKY_FIELDS}
        meta = {k: v for k, v in meta.items() if v and v != "T000000"}
        got = []
        for kind in ("covers", "screenshots", "marquees"):
            src = f"{tmp}/media/{kind}/{stem}.png"
            if os.path.isfile(src):
                os.makedirs(os.path.dirname(f"{media}/{kind}/{stem}.png"), exist_ok=True)
                shutil.copyfile(src, f"{media}/{kind}/{stem}.png")
                got.append(kind)
    if not got and not meta:
        return None
    # Its name is the file's with the brackets squashed ("Tetris (World)(Rev 1)"), no better than Home's own: not written.
    name = meta.pop("name", "")
    gamelist(system, rel, meta)                       # ScreenScraper's details replace older ones
    return {"source": "ScreenScraper", "matched": name, "media": got, "details": sorted(meta)}


def gamelist(system, rel, meta, keep=False):
    """Add or update this game's entry in ES-DE's gamelist.xml (Home reads name, desc, developer, date, genre).
    keep: only fill fields the entry doesn't have yet (what the user or a richer scraper wrote stays)."""
    path = f"{ROOT}/gamelists/{system}/gamelist.xml"
    try:
        tree = ET.parse(path)
    except (OSError, ET.ParseError):
        tree = ET.ElementTree(ET.Element("gameList"))
    root = tree.getroot()
    key = "./" + rel
    game = next((g for g in root.findall("game") if g.findtext("path") == key), None)
    if game is None:
        game = ET.SubElement(root, "game")
        ET.SubElement(game, "path").text = key
    for k, v in meta.items():
        el = game.find(k)
        if el is None:
            el = ET.SubElement(game, k)
        elif keep and (el.text or "").strip():
            continue
        el.text = v
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tree.write(path + ".tmp", encoding="utf-8", xml_declaration=True)
    os.replace(path + ".tmp", path)


def main(argv):
    if len(argv) == 4 and argv[1] == "--index":
        build_index(argv[2], argv[3])
        return {"index": argv[3]}
    if len(argv) != 4:
        return {"error": "usage: asgard-scrape.py <system> <rom path> <stem>"}
    system, rom, stem = argv[1], argv[2], argv[3]
    media = f"{ROOT}/downloaded_media/{system}"
    signed_in = setting("screenscraper.username") and os.access(SKYSCRAPER, os.X_OK)
    if not SYSTEMS.get(system, (None, None))[0] and not signed_in and \
            not (SYSTEMS.get(system, (None, None))[1] and setting("screenscraper.devid")):
        return {"error": "No scraping source for this system yet"}
    try:
        r = screenscraper(system, rom, stem, media) or skyscraper(system, rom, stem, media)
        if not r or "covers" not in r["media"]:   # libretro for what ScreenScraper didn't have
            try:
                lr = libretro(system, rom, stem, media)
            except Offline:
                if not r:
                    raise
                lr = None
            if lr and r:
                r = dict(r, media=sorted(set(r["media"]) | set(lr["media"])), details=sorted(set(r["details"]) | set(lr["details"])),
                         source=r["source"] + " and libretro")
            r = r or lr
    except Offline:
        return {"error": "No internet connection: scraping needs it"}
    if r and not r["media"] and not r.get("details"):
        r = None
    return r or {"error": "No match found for this game"}


if __name__ == "__main__":
    print(json.dumps(main(sys.argv)))
