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
const features = () => FEATS
%s
const settings = { get, q, perfRows, rev: 0 }
const backend = { shell: c => shell.push(c) }
let game = ["azahar"], launched = { sys: "3ds", path: "/roms/3ds/Pokemon X.3ds", emulator: "azahar", core: "azahar" }
let perfChanged = false, group = null, groupSel = 0, sel = 0, open = true, openedAt = 0, items = []
const resume = () => { open = false }
%s
const back_ = { title: "Back", run: () => back() }
const tile = { title: "Performance", page: perfPage }
Object.defineProperty(globalThis, "onPage", { get: () => !!group && !!group.page })
Object.defineProperty(globalThis, "shown", { get: () => group ? [back_].concat(group.page()) : [{ title: "Resume" }, tile] })
const press = (...keys) => keys.forEach(nav)
const out = {}
const snap = name => { out[name] = { sel, titles: shown.map(t => t.title), subs: shown.map(t => t.sub), cfg: { ...cfg }, shell: [...shell] } }

snap("top")
press("right", "a")                     // open it, on its first row
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
console.log(JSON.stringify(out))
""" % ("\n".join(function(panel, f) for f in ("allCoresOff", "optionRow", "perfRows")),
       "\n".join(function(menu, f) for f in ("hasPerf", "perfFile", "perfPrefix", "perfEmu", "perfCore", "perfPage", "applyPerf",
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
assert r["left_page"]["titles"] == ["Resume", "Performance"]
print("ok")
