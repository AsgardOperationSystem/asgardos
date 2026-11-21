# spec: SCRAPE-1
# requires: file:build/AsgardOS-SM8550.aarch64/toolchain/usr/local/qt6/lib/libQt6Quick.so cmd:cmake
"""Run: python -I test_home_scrape_missing.py  (no Thor): Settings > Library > Scrape missing, offscreen. A QML copy answers
backend.exec with canned asgard-scrape.py output, so this checks which games it scrapes, in turn, and what it says; the
scraper itself is test_asgard_scrape.py, and real art arriving on a Thor is a device check."""
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "../../../tools/test"))
import home_harness as hh  # noqa: E402
from home_harness import Root  # noqa: E402

SCRAPE = "start down down a down down a"   # Settings, Library (3rd category), its 3rd row: Scrape missing


def run(root, answers):
    """Home with backend.exec in Settings answering {regex: output}, each command logged as "exec: <cmd>"."""
    out = f"{root.path}/.qml"
    shutil.rmtree(out, ignore_errors=True)
    shutil.copytree(f"{hh.SRC}/qml", out)
    text = open(f"{out}/Settings.qml").read()
    old = "    function close() {"
    assert "backend.exec(" in text and old in text
    text = text.replace("backend.exec(", "fakeExec(").replace(old, """    readonly property var answers: %s
    function fakeExec(cmd, done) {
        console.log("exec: " + cmd)
        let out = ""
        for (const k in answers) if (new RegExp(k).test(cmd)) out = answers[k]
        if (done) Qt.callLater(done, out)
    }
""" % json.dumps(answers) + old, 1)
    open(f"{out}/Settings.qml", "w").write(text)
    return root.run(SCRAPE, env={"ASGARD_HOME_QML": out}, ms=600)


def scraped(res):
    return [line.split("asgard-scrape.py ", 1)[1] for line in res.log.splitlines() if "exec: python3" in line and "asgard-scrape.py" in line]


FOUND = json.dumps({"source": "libretro", "matched": "Zelda (USA)", "by": "name", "media": ["covers"], "details": []})
with Root() as r:
    r.library()                                                       # gba: Metroid, Zelda; nds: Mario
    r.write("storage/ES-DE/downloaded_media/gba/covers/Metroid.png", "png")   # Metroid already has its cover
    res = run(r, {"Zelda": FOUND, "Mario": json.dumps({"error": "No match found for this game"})})
    assert scraped(res) == ["'gba' '/storage/roms/gba/Zelda.gba' 'Zelda'", "'nds' '/storage/roms/nds/Mario.nds' 'Mario'"], res.log
    assert res.shows("Done: found 1 of 2 games"), res.texts
    assert res.log.count("library:") >= 2                             # rescanned after, so the art shows

    # no internet: it stops at the first game and says so, instead of trying every game
    res = run(r, {"Zelda": json.dumps({"error": "No internet connection: scraping needs it"})})
    assert scraped(res) == ["'gba' '/storage/roms/gba/Zelda.gba' 'Zelda'"], res.log
    assert res.shows("No internet connection: scraping needs it"), res.texts

    # nothing to do
    r.write("storage/ES-DE/downloaded_media/gba/covers/Zelda.png", "png")
    r.write("storage/ES-DE/downloaded_media/nds/covers/Mario.png", "png")
    res = run(r, {})
    assert not scraped(res) and res.shows("Every game has a cover"), res.log
print("ok")
