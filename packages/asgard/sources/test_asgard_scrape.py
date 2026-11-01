#!/usr/bin/env python3
# spec: SCRAPE-1
# python3 test_asgard_scrape.py: ROM name -> libretro thumbnail name matching, and the gamelist.xml writer (offline).
import importlib.util, os, tempfile

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

with tempfile.TemporaryDirectory() as d:
    sc.ROOT = d
    sc.gamelist("snes", "Zelda (U).smc", {"name": "Zelda", "desc": "A & B <c>"})
    sc.gamelist("snes", "Zelda (U).smc", {"desc": "new"})                              # update, not a second entry
    sc.gamelist("snes", "Mario.smc", {"name": "Mario"})
    x = open(f"{d}/gamelists/snes/gamelist.xml").read()
    assert x.count("<game>") == 2 and "<desc>new</desc>" in x and "<name>Zelda</name>" in x and "./Mario.smc" in x, x
assert sc.screenscraper("snes", "/nonexistent", "x", "/tmp") is None                    # off without a developer ID
print("ok")
