# spec: MENU-2 MENU-4 GAME-5
# requires: cmd:node
"""Run: python -I test_game_menu_items.py  (no Thor, no Qt): the in-game menu's tiles per emulator, by running GameMenu.qml's
list in node with a stub backend. MENU-2: each emulator's items and what they send. MENU-4: every level fits the grid's 5
rows. GAME-5: Resume, Quit, Back to Home and Quit and save log, and unpausing on the way out; pausing on the way in is the C++
below, read as a tree check, and that the picture stops is a human check."""
import json
import os
import re
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
menu = open(os.path.join(HERE, "../../asgard-home/src/qml/GameMenu.qml")).read()
list_src = re.search(r"    function withExit.*?(?=    property var group: null)", menu, re.S).group(0)
list_src = re.sub(r"^    readonly property var (\w+): ", r"const \1 = ", list_src, flags=re.M)
resume = "\n".join(re.search(r"^    function " + f + r"\(.*?^    }", menu, re.M | re.S).group(0) for f in ("resume", "raResume"))

SCRIPT = """
const sent = []
const log = name => (...args) => { sent.push([name, ...args]) }
const backend = { retroarch: log("ra"), gameKeys: log("key"), padChord: log("chord"), quitGame: log("quit"),
                  toBackground: log("background"), set gameMenu(v) { sent.push(["menu", v]) } }
function menuFor(game, launched) {
    const azahar = game.includes("azahar"), eden = game.includes("eden"), retroarch = game.includes("retroarch"),
          steam = game.includes("steam"), wwhd = game.includes("wwhd")
    const hasPerf = () => false
    %s
    %s
    const show = list => list.map(t => {
        const out = { title: t.title }
        if (t.items) out.items = show(t.items)
        if (t.run) { sent.length = 0; t.run(); out.sent = [...sent] }
        return out
    })
    return show(items)
}
const out = {}
for (const g of ["azahar", "eden", "retroarch", "steam", "wwhd", "melonds"]) out[g] = menuFor([g], { path: "/r/x", sys: "s" })
out.tool = menuFor([], {})
console.log(JSON.stringify(out))
""" % (resume, list_src)
menus = json.loads(subprocess.run(["node", "-e", SCRIPT], check=True, capture_output=True, text=True).stdout)


def flat(tiles):
    for t in tiles:
        yield t
        yield from flat(t.get("items", []))


def tile(name, title):
    return next(t for t in flat(menus[name]) if t["title"] == title)


def titles(name):
    return {t["title"] for t in flat(menus[name])}


# MENU-2: each one's own items
OWN = {"retroarch": {"RetroArch menu", "Quick save", "Quick load", "Screenshot", "Restart"},
       "azahar": {"Quick save", "Quick load", "Swap screens", "Change layout", "Screenshot", "Restart"},
       "eden": {"Docked mode", "Speed limit", "Performance overlay", "Screenshot", "Restart"},
       "steam": {"Steam overlay", "Quick Access"},
       "wwhd": {"Wind Waker HD settings"}}
for name, items in OWN.items():
    assert items <= titles(name), (name, items - titles(name))
assert not any(items <= titles("melonds") for items in OWN.values())


def sends(name, title, *wanted):
    got = tile(name, title)["sent"]
    for w in wanted:
        assert w in got, (name, title, got)


sends("retroarch", "RetroArch menu", ["ra", "MENU_TOGGLE"])
sends("retroarch", "Quick save", ["ra", "SAVE_STATE"], ["ra", "PAUSE_TOGGLE"])
sends("retroarch", "Quick load", ["ra", "LOAD_STATE"], ["ra", "PAUSE_TOGGLE"])
sends("retroarch", "Screenshot", ["ra", "SCREENSHOT"])
sends("retroarch", "Restart", ["ra", "RESET"])
sends("azahar", "Quick save", ["key", "Alt+S"], ["key", "F4"])
sends("azahar", "Quick load", ["key", "Alt+L"])
sends("azahar", "Swap screens", ["key", "F9"])
sends("azahar", "Change layout", ["key", "F10"])
sends("azahar", "Screenshot", ["key", "Ctrl+P"])
sends("azahar", "Restart", ["key", "F6"])
sends("eden", "Docked mode", ["key", "F10"], ["key", "F4"])
sends("eden", "Speed limit", ["key", "Ctrl+U"])
sends("eden", "Performance overlay", ["key", "Ctrl+V"])
sends("eden", "Screenshot", ["key", "Ctrl+P"])
sends("eden", "Restart", ["key", "F6"])
sends("steam", "Steam overlay", ["chord", ["Gamepad:Button:Guide"]])
sends("steam", "Quick Access", ["chord", ["Gamepad:Button:QuickAccess"]])
sends("wwhd", "Wind Waker HD settings", ["key", "F1"])

# GAME-5: every game Resume and Quit; with kill data also Back to Home and Quit and save log. Resume unpauses what can pause.
for name in menus:
    quit_title = "Exit Steam" if name == "steam" else "Quit game"
    assert {"Resume", quit_title} <= titles(name), name
    sends(name, quit_title, ["quit"])
    if name == "tool":
        assert not {"Back to Home", "Quit and save log"} & titles(name)
        continue
    assert {"Back to Home", "Quit and save log"} <= titles(name), name
    sends(name, "Back to Home", ["background"])
    assert ["quit", True] in tile(name, "Quit and save log")["sent"]
sends("azahar", "Resume", ["key", "F4"])
sends("eden", "Resume", ["key", "F4"])
sends("retroarch", "Resume", ["ra", "PAUSE_TOGGLE"])
assert not [s for s in tile("melonds", "Resume")["sent"] if s[0] != "menu"]   # no pause of its own: nothing to undo

backend = open(os.path.join(HERE, "../../asgard-home/src/backend.cpp")).read()
assert re.search(r'cmd == "menu" && playing\(\).*?togglePause\(\);\s*if \(open\)\s*setGameMenu\(true\)', backend, re.S)
pause = re.search(r"bool Backend::togglePause\(\)\n\{.*?\n\}", backend, re.S).group(0)
assert re.search(r'"azahar".*"eden".*gameKeys\("F4"\)', pause, re.S) and 'retroarch("PAUSE_TOGGLE")' in pause

# MENU-4: two columns of 5 rows at most at every level: a sub-grid's own Back tile counts
ROWS, COLUMNS = 5, 2
assert re.search(r"columns: menu\.onPage \? 1 : 2", menu)
rowh = int(re.search(r"\(menu\.width - 72 - 64 - 20\) / 2; height: (\d+)", menu).group(1))
spacing = int(re.search(r"rowSpacing: (\d+)", menu).group(1))
top = int(re.search(r"x: 32; y: (\d+); columns", menu).group(1))
assert 36 + top + ROWS * rowh + (ROWS - 1) * spacing <= 1080 - 36      # the sheet's inside on the 1080 tall layout
for name, tiles in menus.items():
    assert len(tiles) <= ROWS * COLUMNS, name
    for t in flat(tiles):
        if "items" in t:
            assert len(t["items"]) + 1 <= ROWS * COLUMNS, (name, t["title"])
# MENU-4's point: the risky ones aren't on the first level when there's a choice
assert "Quit and save log" not in {t["title"] for t in menus["azahar"]} and "Restart" not in {t["title"] for t in menus["azahar"]}
print("ok")
