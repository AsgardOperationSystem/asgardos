#!/usr/bin/env python3
# Scrape one game into ES-DE's layout, which Asgard Home reads (Select on a game > Scrape this game). Prints JSON.
#   asgard-scrape.py <system> <rom path> <stem>
# ScreenScraper first when system.cfg has a developer ID (screenscraper.devid / .devpassword; user account
# screenscraper.username / .password optional): description, developer, date, genre, cover, screenshot, marquee,
# matched by checksum. Otherwise, or when it finds nothing, libretro's thumbnail server (no account): cover and
# screenshot, matched by the ROM's name. Needs internet either way.
# ScreenScraper stays off until a developer ID is set (none yet): written against its documented API v2, untested.
import json, os, re, sys, urllib.parse, urllib.request, zlib
import xml.etree.ElementTree as ET

ROOT = "/storage/ES-DE"
CFG = "/storage/.config/system/configs/system.cfg"
LIBRETRO = "https://thumbnails.libretro.com/"
# ES system -> (libretro playlist, ScreenScraper systemeid)
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
}
# GoodTools region codes in ROM names -> No-Intro region names libretro uses
REGIONS = {"U": "USA", "E": "Europe", "J": "Japan", "UE": "USA, Europe", "JU": "Japan, USA", "W": "World", "F": "France",
           "G": "Germany", "S": "Spain", "I": "Italy", "K": "Korea", "A": "Australia"}


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
    req = urllib.request.Request(url, headers={"User-Agent": "AsgardOS-scraper/1"})
    with urllib.request.urlopen(req, timeout=20) as r:
        data = r.read()
    return data if binary else data.decode("utf-8", "replace")


def base(name):
    """Title without tags or punctuation: 'Legend of Zelda, The - A Link to the Past (U) [!]' -> 'legendofzeldathealinktothepast'."""
    name = re.sub(r"\([^)]*\)|\[[^]]*\]", "", name).lower()
    name = re.sub(r"^\d+\s*-\s*", "", name.strip())          # release-list numbers: "0171 - Golden Sun"
    name = re.sub(r"^the\s+|,\s*the\b", "", name)              # "The Legend of Zelda" = "Legend of Zelda, The"
    return re.sub(r"[^a-z0-9]", "", name)


def regions(name):
    """The region words in a name's tags: '(U) [!]' -> {'usa'}, '(Europe) (En,Fr)' -> {'europe'}."""
    out = set()
    for tag in re.findall(r"\(([^)]*)\)", name):
        tag = REGIONS.get(tag.strip(), tag)
        out |= {w.strip().lower() for w in tag.split(",")}
    return out


def best(stem, names):
    """The libretro name for this ROM: same title, then the most region overlap, USA/World/Europe first."""
    want, regs = base(os.path.basename(stem)), regions(os.path.basename(stem))
    cands = [n for n in names if base(n) == want]
    if not cands:   # ROM named without the leading article etc.: accept a title that contains ours
        cands = [n for n in names if want and want in base(n)]
    pref = ["usa", "world", "europe"]
    score = lambda n: (len(regs & regions(n)), max((3 - pref.index(r) for r in regions(n) if r in pref), default=0), -len(n))
    return max(cands, key=score) if cands else None


def listing(url):
    """File names on an Apache index page."""
    return [urllib.parse.unquote(h) for h in re.findall(r'href="([^"?/][^"]*\.png)"', fetch(url))]


def save(data, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".tmp", "wb") as f:
        f.write(data)
    os.replace(path + ".tmp", path)


def libretro(system, stem, media):
    playlist = SYSTEMS.get(system, (None,))[0]
    if not playlist:
        return None
    sysurl = LIBRETRO + urllib.parse.quote(playlist) + "/"
    got = {}
    for kind, folder in (("covers", "Named_Boxarts"), ("screenshots", "Named_Snaps")):
        try:
            name = best(stem, listing(sysurl + folder + "/"))
            if name:
                save(fetch(sysurl + folder + "/" + urllib.parse.quote(name), True), f"{media}/{kind}/{stem}.png")
                got[kind] = name[:-4]
        except OSError:
            continue
    return {"source": "libretro", "matched": got.get("covers") or got.get("screenshots"), "media": sorted(got)} if got else None


def screenscraper(system, rom, stem, media):
    devid, devpw = setting("screenscraper.devid"), setting("screenscraper.devpassword")
    ssid = SYSTEMS.get(system, (None, None))[1]
    if not (devid and devpw and ssid):
        return None
    size = os.path.getsize(rom)
    q = {"devid": devid, "devpassword": devpw, "softname": "AsgardOS", "output": "json", "systemeid": ssid,
         "romtype": "rom", "romnom": os.path.basename(rom), "romtaille": size,
         "ssid": setting("screenscraper.username"), "sspassword": setting("screenscraper.password")}
    if size < 64 << 20:   # checksum small ROMs; discs are matched by name and size
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
    return {"source": "ScreenScraper", "matched": meta["name"], "media": got}


def gamelist(system, rel, meta):
    """Add or update this game's entry in ES-DE's gamelist.xml (Home reads name, desc, developer, date, genre)."""
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
        (game.find(k) if game.find(k) is not None else ET.SubElement(game, k)).text = v
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tree.write(path + ".tmp", encoding="utf-8", xml_declaration=True)
    os.replace(path + ".tmp", path)


def main(argv):
    if len(argv) != 4:
        return {"error": "usage: asgard-scrape.py <system> <rom path> <stem>"}
    system, rom, stem = argv[1], argv[2], argv[3]
    media = f"{ROOT}/downloaded_media/{system}"
    try:
        fetch(LIBRETRO, False)
    except OSError:
        return {"error": "No internet connection: scraping needs it"}
    r = screenscraper(system, rom, stem, media) or libretro(system, stem, media)
    return r or {"error": "No match found for this game"}


if __name__ == "__main__":
    print(json.dumps(main(sys.argv)))
