#!/usr/bin/env python3
# spec: SCRAPE-1
# python3 test_asgard_scrape.py: ROM name -> libretro name matching, the libretro-database index (built from a small
# fixture), CRC matching, libretro-thumbnails URLs and fallback, and the gamelist.xml writer (offline: fetch is faked).
import importlib.util, json, os, tempfile, urllib.error, zlib

spec = importlib.util.spec_from_file_location("sc", os.path.join(os.path.dirname(os.path.abspath(__file__)), "asgard-scrape.py"))
sc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sc)

NAMES = ["Legend of Zelda, The - A Link to the Past (Canada).png", "Legend of Zelda, The - A Link to the Past (Europe).png",
         "Legend of Zelda, The - A Link to the Past (USA).png", "Legend of Zelda, The - A Link to the Past (France).png",
         "Super Mario World (USA).png", "Super Mario World (Japan).png", "Pokemon - Emerald Version (USA, Europe).png"]
assert sc.best("Legend of Zelda, The - A Link to the Past (U) [!]", NAMES).startswith("Legend of Zelda, The - A Link to the Past (USA)")
assert sc.best("Legend of Zelda, The - A Link to the Past (E)", NAMES).endswith("(Europe).png")
assert sc.best("Super Mario World", NAMES) == "Super Mario World (USA).png"            # no tags: USA first
assert sc.best("subdir/Super Mario World (J)", NAMES) == "Super Mario World (Japan).png"
assert sc.best("Pokemon Emerald", NAMES) == "Pokemon - Emerald Version (USA, Europe).png" and sc.best("Metroid", NAMES) is None
assert sc.best("Pokemon - Emerald Version (U)", NAMES) == "Pokemon - Emerald Version (USA, Europe).png"
# names seen on a real library: a " # NDS" suffix, a release number with group tags, two names joined by " ~ "
DS = ["Pokemon - White Version 2 (USA, Europe) (NDSi Enhanced)", "Golden Sun (USA, Europe)", "Lock 'n' Chase (World)"]
assert sc.best("Pokemon - White Version 2 # NDS", DS) == DS[0]
assert sc.best("0171 - Golden Sun (U)(Mode7)", DS) == DS[1]
assert sc.best("Lock n' Chase ~ Lock 'n' Chase (World)", DS) == DS[2]

# libretro-thumbnails on GitHub: spaces -> _ in the repo, &*/:`<>?\|" -> _ in the file name
assert sc.thumb_url("Nintendo - Game Boy", "Named_Boxarts", "Kwirk - He's A-maze-ing! (USA, Europe)") == \
    "https://raw.githubusercontent.com/libretro-thumbnails/Nintendo_-_Game_Boy/master/Named_Boxarts/Kwirk%20-%20He%27s%20A-maze-ing%21%20%28USA%2C%20Europe%29.png"
assert sc.thumb_url("Nintendo - GameCube", "Named_Snaps", "007: Everything or Nothing (USA)").endswith("/007_%20Everything%20or%20Nothing%20%28USA%29.png")

ROM = b"not really a game boy rom"
CRC = f"{zlib.crc32(ROM):08X}"
NOINTRO = f'''clrmamepro (
\tname "Nintendo - Game Boy"
)
game (
\tname "Tetris (World) (Rev 1)"
\tregion "World"
\trom ( name "Tetris (World) (Rev 1).gb" size 65536 crc {CRC} md5 00 )
)
game (
\tname "Tetris (Japan) (En)"
\trom ( name "Tetris (Japan) (En).gb" size 32768 crc 63F9407D )
)
game (
\tname "Tetris 2 (USA)"
\tdescription "Tetris 2 (USA)"
\trom (
\t\tname "Tetris 2 (USA).gb"
\t\tcrc AA4A1EDB
\t)
)
'''
META = {"developer": f'game (\n\tcomment "Tetris (World) (Rev 1)"\n\tdeveloper "Nintendo"\n\trom ( crc {CRC} )\n)\n',
        "genre": f'game (\n\tcomment "x"\n\tgenre "Puzzle"\n\trom ( crc {CRC} )\n)\n',
        "releaseyear": f'game (\n\tcomment "Tetris (World) (Rev 1)"\n\treleaseyear "1989"\n\trom ( crc {CRC} )\n)\n',
        "maxusers": 'game (\n\tcomment "Tetris 2 (USA)"\n\tusers 2\n\trom ( crc AA4A1EDB )\n)\n'}

with tempfile.TemporaryDirectory() as d:
    db, idx = f"{d}/db", f"{d}/idx"
    for sub, text in [("no-intro", NOINTRO)] + list(META.items()):
        os.makedirs(f"{db}/metadat/{sub}")
        open(f"{db}/metadat/{sub}/Nintendo - Game Boy.dat", "w").write(text)
    assert sc.main(["x", "--index", db, idx]) == {"index": idx}
    sc.INDEX = idx
    rows = {r["name"]: r for r in sc.load("Nintendo - Game Boy")}
    assert set(rows) == {"Tetris (World) (Rev 1)", "Tetris (Japan) (En)", "Tetris 2 (USA)"}, rows
    t = rows["Tetris (World) (Rev 1)"]
    assert (t["crc"], t["developer"], t["genre"], t["year"]) == (CRC, "Nintendo", "Puzzle", "1989"), t   # by CRC, any comment
    assert rows["Tetris 2 (USA)"]["players"] == "2" and rows["Tetris 2 (USA)"]["desc"] == ""          # a name isn't a description
    assert sc.details(t)["releasedate"] == "19890101T000000"

    # a renamed ROM is found by its CRC, not its name; an unknown one by name
    rom = f"{d}/roms/gb/my tetris.gb"
    os.makedirs(os.path.dirname(rom))
    open(rom, "wb").write(ROM)
    cands, by_crc = sc.match(sc.load("Nintendo - Game Boy"), rom, "my tetris")
    assert by_crc and cands[0]["name"] == "Tetris (World) (Rev 1)" and cands[1]["name"].startswith("Tetris (Japan)"), cands
    cands, by_crc = sc.match(sc.load("Nintendo - Game Boy"), "/nonexistent.gb", "Tetris 2")
    assert not by_crc and cands[0]["name"] == "Tetris 2 (USA)"

    # libretro(): the World cover is missing on GitHub, so the Japan one is used; the screenshot is the World one
    sc.ROOT = f"{d}/ES-DE"
    asked = []
    def fake(url, binary=False):
        asked.append(url)
        if "Named_Boxarts" in url and "World" in url:
            raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)
        return b"PNG " + url.encode()
    sc.fetch = fake
    sc.gamelist("gb", "my tetris.gb", {"desc": "mine", "developer": "Me"})               # what the user wrote
    r = sc.main(["x", "gb", rom, "my tetris"])
    assert r == {"source": "libretro", "matched": "Tetris (World) (Rev 1)", "by": "checksum",
                 "media": ["covers", "screenshots"], "details": ["developer", "genre", "releasedate"]}, r
    media = f"{sc.ROOT}/downloaded_media/gb"
    assert b"Japan" in open(f"{media}/covers/my tetris.png", "rb").read()
    assert b"Named_Snaps/Tetris%20%28World%29" in open(f"{media}/screenshots/my tetris.png", "rb").read()
    x = open(f"{sc.ROOT}/gamelists/gb/gamelist.xml").read()
    assert x.count("<game>") == 1 and "<desc>mine</desc>" in x and "<developer>Me</developer>" in x, x   # kept
    assert "<genre>Puzzle</genre>" in x                                                 # filled
    assert "<releasedate>19890101T000000</releasedate>" in x

    # no internet: said so, not "no match"
    def offline(url, binary=False):
        raise urllib.error.URLError("Temporary failure in name resolution")
    sc.fetch = offline
    assert sc.main(["x", "gb", rom, "my tetris"]) == {"error": "No internet connection: scraping needs it"}
    # a system libretro has no art for, and no ScreenScraper ID: answered at once, without the network
    assert sc.main(["x", "switch", "/x.nsp", "x"]) == {"error": "No scraping source for this system yet"}
    # a game the index doesn't know
    assert sc.main(["x", "gb", "/nonexistent.gb", "Metroid II"]) == {"error": "No match found for this game"}

# Skyscraper, signed in: its output for this game only is copied over; the login never reaches its command line
FAKE_SKY = r"""#!/bin/sh
echo "$@" >> "$SKY_LOG"
cp "$2" "$SKY_LOG.cfg"
case " $* " in *" -f esde "*) ;; *) exit 0 ;; esac
while [ $# -gt 0 ]; do case $1 in -g) gl=$2; shift ;; -o) med=$2; shift ;; esac; shift; done
mkdir -p "$gl" "$med/covers" "$med/marquees"
[ -n "$SKY_FIND" ] || exit 0
printf '<?xml version="1.0"?>\n<gameList>\n<game><path>./Other.iso</path><name>Other</name></game>\n<game><path>./%s</path><name>Wind Waker</name><desc>Sail.</desc><developer>Nintendo EAD</developer><releasedate>20030324T000000</releasedate><players>1</players></game>\n</gameList>\n' "$SKY_FIND" > "$gl/gamelist.xml"
echo marquee > "$med/marquees/Zelda (USA).png"
[ -z "$SKY_COVER" ] || echo cover > "$med/covers/Zelda (USA).png"
"""
with tempfile.TemporaryDirectory() as d:
    sc.ROOT, sc.CFG, sc.INDEX = f"{d}/ES-DE", f"{d}/system.cfg", f"{d}/no-index"
    sky = f"{d}/Skyscraper"
    open(sky, "w").write(FAKE_SKY)
    os.chmod(sky, 0o755)
    sc.SKYSCRAPER = sky
    os.environ["SKY_LOG"] = f"{d}/sky.log"
    rom = f"{d}/roms/gamecube/Zelda (USA).rvz"
    os.makedirs(os.path.dirname(rom))
    open(rom, "w").write("disc")
    assert sc.main(["x", "gamecube", rom, "Zelda (USA)"]) == {"error": "No match found for this game"}   # not signed in
    assert not os.path.exists(f"{d}/sky.log")
    open(sc.CFG, "w").write("screenscraper.username=me\nscreenscraper.password=p@ss word\n")
    sc.gamelist("gamecube", "Zelda (USA).rvz", {"name": "My Zelda"})
    sc.gamelist("gamecube", "Mario.iso", {"name": "Mario", "desc": "kept"})
    os.environ["SKY_FIND"], os.environ["SKY_COVER"] = "Zelda (USA).rvz", "1"
    r = sc.main(["x", "gamecube", rom, "Zelda (USA)"])
    assert r == {"source": "ScreenScraper", "matched": "Wind Waker", "media": ["covers", "marquees"],
                 "details": ["desc", "developer", "players", "releasedate"]}, r
    log = open(f"{d}/sky.log").read()
    assert "-p gc -i " + os.path.dirname(rom) in log and "p@ss" not in log, log                 # its name for GameCube
    assert 'userCreds="me:p@ss word"' in open(f"{d}/sky.log.cfg").read()
    x = open(f"{sc.ROOT}/gamelists/gamecube/gamelist.xml").read()
    assert "<name>My Zelda</name>" in x and "<desc>Sail.</desc>" in x and "<desc>kept</desc>" in x and "Other" not in x, x
    assert open(f"{sc.ROOT}/downloaded_media/gamecube/marquees/Zelda (USA).png").read() == "marquee\n"
    # ScreenScraper had no cover: libretro adds one (index fixture: this game by name)
    sc.INDEX = f"{d}/idx"
    os.makedirs(sc.INDEX)
    open(f"{sc.INDEX}/Nintendo - GameCube.tsv", "w").write("Zelda (USA)\t\t\t\t\t\t\t\t\n")
    sc.fetch = lambda url, binary=False: b"PNG"
    del os.environ["SKY_COVER"]
    r = sc.main(["x", "gamecube", rom, "Zelda (USA)"])
    assert r["source"] == "ScreenScraper and libretro" and r["media"] == ["covers", "marquees", "screenshots"], r
    # ScreenScraper found it, but the libretro top-up is offline: what ScreenScraper gave still counts
    sc.fetch = offline
    assert sc.main(["x", "gamecube", rom, "Zelda (USA)"])["source"] == "ScreenScraper"
    # Switch has no libretro source, but a signed-in user gets ScreenScraper's
    os.environ["SKY_FIND"] = "Pokemon Violet"
    os.makedirs(f"{d}/roms/switch/Pokemon Violet")
    r = sc.main(["x", "switch", f"{d}/roms/switch/Pokemon Violet", "Pokemon Violet"])
    assert r["source"] == "ScreenScraper" and "desc" in r["details"], r

with tempfile.TemporaryDirectory() as d:
    sc.ROOT = d
    sc.gamelist("snes", "Zelda (U).smc", {"name": "Zelda", "desc": "A & B <c>"})
    sc.gamelist("snes", "Zelda (U).smc", {"desc": "new"})                              # update, not a second entry
    sc.gamelist("snes", "Mario.smc", {"name": "Mario"})
    x = open(f"{d}/gamelists/snes/gamelist.xml").read()
    assert x.count("<game>") == 2 and "<desc>new</desc>" in x and "<name>Zelda</name>" in x and "./Mario.smc" in x, x
assert sc.screenscraper("snes", "/nonexistent", "x", "/tmp") is None                    # off without a developer ID
print("ok")
