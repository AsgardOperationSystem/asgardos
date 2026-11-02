# spec: MENU-5 OVR-4 PERF-2
# requires: cmd:node
"""Run: python -I test_game_menu_perf.py  (no Thor, no Qt): the in-game menu's Performance page, by running those functions
from GameMenu.qml and Settings.qml in node with a stub backend: what it saves, when it applies, how the d-pad moves."""
import json
import os
import re
import subprocess

QML = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../asgard-home/src/qml")
menu = open(os.path.join(QML, "GameMenu.qml")).read()
panel = open(os.path.join(QML, "Settings.qml")).read()


def function(src, name):
    """`function name(...) {...}`: on one line, or up to the first closing brace at the function's own indent."""
    m = re.search(r"^( *)function " + name + r"\(.*?^\1}", src, re.M | re.S)
    one = re.search(r"^ *function " + name + r"\(.*\) \{ .* \}$", src, re.M)
    if one and (not m or len(one.group(0)) < len(m.group(0))):
        return one.group(0)
    assert m, name
    return m.group(0)


script = """
const cfg = {}, shell = []
const get = (k, d) => cfg[k] ? cfg[k] : (d === undefined ? "" : d)
const set = (k, v) => { cfg[k] = v }
const q = v => "'" + v + "'"
const coreTypes = ["little", "mid", "prime"]
const PCT = [["50%%", "50"], ["100%%", "100"]]
const FEATS = [...coreTypes.map(t => ({ key: "cpu_cap_" + t, label: t, default: "100%%", choices: [["Off", "off"], ...PCT] })),
               { key: "gpu_cap", label: "gpu", choices: PCT }, { key: "fan_mode", label: "fan", choices: PCT }]
const SCREEN = ["top_refresh", "top_brightness", "top_ultra_black", "top_warmth", "top_tint", "top_contrast",
                "bottom_refresh", "bottom_brightness", "bottom_warmth", "bottom_tint", "bottom_contrast"]
FEATS.push(...SCREEN.map(key => ({ key, label: key, osKey: "os." + key, osDefault: "60", choices: [["A", "60"], ["B", "120"]] })))
const features = () => FEATS
%s
const settings = { get, q, perfRows, screenRows, rev: 0 }
const backend = { shell: c => shell.push(c) }
let game = ["azahar"], launched = { sys: "3ds", path: "/roms/3ds/Pokemon X.3ds", emulator: "azahar", core: "azahar" }
let perfChanged = false, screenChanged = false, group = null, groupSel = 0, sel = 0, open = true, openedAt = 0, items = [], parents = []
const resume = () => { open = false }
%s
const back_ = { title: "Back", run: () => back() }
const tile = { title: "Performance", items: perfTiles() }
Object.defineProperty(globalThis, "onPage", { get: () => !!group && !!group.page })
Object.defineProperty(globalThis, "shown", { get: () => group ? [back_].concat(group.page ? group.page() : group.items) : [{ title: "Resume" }, tile] })
const press = (...keys) => keys.forEach(nav)
const out = {}
const snap = name => { out[name] = { sel, titles: shown.map(t => t.title), subs: shown.map(t => t.sub), cfg: { ...cfg }, shell: [...shell] } }

snap("top")
press("right", "a")                     // open the tile: a small grid, on its first tile
snap("tiles")
press("a")                              // CPU and GPU, on its first row
snap("opened")
press("right")                          // little: unset -> Off
snap("stepped")
press("left", "left")                   // back to unset, then the other way round to its last value
snap("left")
press("right", "right")                 // little Off again
press("down", "right", "down", "right") // mid Off, prime can't be: its step skips Off, never all three
snap("alloff")
press("down", "a")                      // GPU, with A
snap("gpu")
press("up", "up", "up", "up", "up", "up")
snap("backrow")
press("right", "a")                     // Back: applied once
snap("left_page")
open = false; applyPerf()               // nothing changed since: not applied again
snap("closed")
open = true
press("down", "left", "a")              // the grid, two columns: Top screen is below Back
snap("top_screen")
press("right")                          // refresh rate
snap("top_stepped")
press("down", "down", "down", "a")      // Colour: a page further down
snap("top_colour")
press("right")
press("up", "right", "a")               // Back to the Top screen page: applied, with no core cycling
snap("top_back")
press("up", "up", "up", "up", "a")      // Back again, to the grid
snap("back_to_tiles")
press("right", "a")                     // Bottom screen
snap("bottom_screen")
press("up", "up", "up", "up", "a")
press("up", "up", "left", "a")          // Back to the top level
snap("top_again")
console.log(JSON.stringify(out))
""" % ("\n".join(function(panel, f) for f in ("allCoresOff", "optionRow", "perfRows", "screenRows")),
       "\n".join(function(menu, f) for f in ("hasPerf", "perfFile", "perfPrefix", "perfEmu", "perfCore", "perfPage", "screenPage", "colourTile", "topScreenPage", "bottomScreenPage", "perfTiles", "applyPerf",
                                             "activate", "back", "nav")))
r = json.loads(subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True).stdout)
K = '3ds["Pokemon X.3ds"].'

# Only the CPU and GPU caps, one to a row under Back, opening on the first
assert r["opened"]["titles"] == ["Back", "little", "mid", "prime", "gpu"] and r["opened"]["sel"] == 1
assert r["opened"]["subs"][1] == "‹  OS (100%)  ›"

# A step goes to the game's own key, and nothing is applied yet
assert r["stepped"]["cfg"] == {K + "cpu_cap_little": "off"} and r["stepped"]["shell"] == []
assert r["stepped"]["subs"][1] == "‹  Off  ›"
# Left goes the other way, through unset (empty: inherits again, CFG-9)
assert r["left"]["cfg"][K + "cpu_cap_little"] == "100"

# PERF-2: never every core type off
off = r["alloff"]["cfg"]
assert off[K + "cpu_cap_little"] == "off" and off[K + "cpu_cap_mid"] == "off" and off[K + "cpu_cap_prime"] == "50"
assert r["gpu"]["cfg"][K + "gpu_cap"] == "50"
assert r["backrow"]["sel"] == 0

# Applied on leaving the page, once, for this game; the menu closing doesn't repeat it
want = "[ -f /run/asgard-perf.saved ] && /usr/share/asgard/asgard-perf-profile.sh cpu '3ds' 'Pokemon X.3ds'"
assert r["backrow"]["shell"] == [] and r["left_page"]["shell"] == [want] and r["closed"]["shell"] == [want]
assert r["left_page"]["titles"] == ["Back", "CPU and GPU", "Top screen", "Bottom screen"]
assert r["tiles"]["titles"] == r["left_page"]["titles"] and r["tiles"]["sel"] == 1

# The screens: every page fits the five rows the bottom screen has, Back among them.
assert r["top_screen"]["titles"] == ["Back", "top_refresh", "top_brightness", "top_ultra_black", "Colour"]
assert r["top_stepped"]["cfg"][K + "top_refresh"] == "60" and r["top_stepped"]["subs"][1] == "‹  A  ›"
assert r["top_colour"]["titles"] == ["Back", "top_warmth", "top_tint", "top_contrast"]
assert r["bottom_screen"]["titles"] == ["Back", "bottom_refresh", "bottom_brightness", "Colour"]
for page in ("opened", "top_screen", "top_colour", "bottom_screen"):
    assert len(r[page]["titles"]) <= 5, page
# Saved to the game's key, Settings' own untouched, and applied without cycling the cores.
assert not [k for k in r["top_back"]["cfg"] if k.startswith("os.")]
screens = "[ -f /run/asgard-perf.saved ] && /usr/share/asgard/asgard-perf-profile.sh screens '3ds' 'Pokemon X.3ds'"
assert r["top_stepped"]["shell"] == [want] and r["top_back"]["shell"] == [want, screens]
assert r["back_to_tiles"]["shell"] == [want, screens], r["back_to_tiles"]["shell"]
assert r["top_again"]["titles"] == ["Resume", "Performance"], r["top_again"]
print("ok")
