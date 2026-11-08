#!/usr/bin/env python3
# spec: SND-7
# requires: cmd:node
"""Run: python -I test_game_menu_sound.py  (no Thor, no Qt): the in-game menu's Sound page, by running its functions from
GameMenu.qml and Settings' rows from Settings.qml in node with a stub backend. The page shows the playing output's EQ and
its bass, mid and treble (the speaker's on Bluetooth, which Back says), fits the page's 5 rows with Back, steps run
asgard-eq.py's set / use / tone, the tone stops at ±6 dB, and a game's override is shown and left alone. That the change
is heard at once with no gap is a device check; asgard-eq.py's side is test_asgard_eq.py."""
import json
import os
import re
import subprocess

QML = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../asgard-home/src/qml")
menu = open(os.path.join(QML, "GameMenu.qml")).read()
panel = open(os.path.join(QML, "Settings.qml")).read()


def function(src, name):
    """`function name(...) {...}`: on one line, or up to the first closing brace at the function's own indent."""
    one = re.search(r"^ *function " + name + r"\(.*\) \{ .* \}(?= *(//.*)?$)", src, re.M)
    if one:
        return one.group(0)
    m = re.search(r"^( *)function " + name + r"\(.*?^\1}", src, re.M | re.S)
    assert m, name
    return m.group(0)


tile = re.search(r"^    readonly property var soundTile: (\(\{.*?\} \}\))$", menu, re.M | re.S)
assert tile, "no Sound tile in GameMenu.qml"
assert re.search(r"list\.concat\(settings \? \[soundTile\] : \[\]\)", menu), "withExit doesn't add the Sound tile"

script = """
const runs = []
const backend = { exec: (cmd, then) => { runs.push(cmd.replace("python3 /usr/share/asgard/asgard-eq.py ", "")); then('{"ok": true}') } }
// Settings' side: its live state and helpers, then its real rows
let live = {}, rev = 0
const note = (k, v) => { live = Object.assign({}, live, { [k]: v }); rev++ }
const sh = () => {}
%s
%s
%s
%s
%s
%s
const settings = { get rev() { return rev }, get live() { return live }, soundRows: soundRows }
// GameMenu's side
%s
%s
const soundTile = %s
const show = () => soundPage().map(r => [r.title, r.sub])
const out = {}
out.loading = show()
const base = { speaker: "thor", headphones: "thor", headphones_name: "", saved: ["HD 600"],
               tone: { speaker: [0, 0, 0], headphones: [2, 0, -1] }, game: {}, output: "speaker" }
live.eq = base
out.speaker = show(); out.speakerNote = soundTile.note
runs.length = 0
soundPage()[0].step(1); soundPage()[1].step(1); soundPage()[3].step(-1)
out.speakerRuns = runs.slice()
live.eq = Object.assign({}, base, { output: "headphones" })
out.headphones = show()
runs.length = 0
soundPage()[0].step(1); soundPage()[0].step(-1); soundPage()[1].step(1)
out.headphonesRuns = runs.slice()
live.eq = Object.assign({}, base, { tone: { speaker: [6, 0, -6], headphones: [0, 0, 0] } })
runs.length = 0
soundPage()[1].step(1); soundPage()[3].step(-1); soundPage()[1].step(-1)
out.edgeRuns = runs.slice()
live.eq = Object.assign({}, base, { output: "bluetooth" })
out.bluetooth = show(); out.bluetoothNote = soundTile.note
live.eq = Object.assign({}, base, { game: { speaker: "joey" } })
runs.length = 0
out.game = show(); soundPage()[0].step(1)
out.gameRuns = runs.slice()
console.log(JSON.stringify(out))
""" % (function(panel, "q"), function(panel, "eqRun"), function(panel, "eqRefresh"), function(panel, "eqRow"),
       function(panel, "toneRow"), function(panel, "soundRows"),
       function(menu, "soundOut"), function(menu, "soundPage"), tile.group(1))

p = subprocess.run(["node", "-e", script], capture_output=True, text=True)
assert p.returncode == 0, p.stderr[-3000:]
r = json.loads(p.stdout)

assert r["loading"] == [["Loading…", ""]], r["loading"]
assert r["speaker"] == [["Speaker EQ", "‹  Thor tuning  ›"], ["Bass", "‹  0 dB  ›"], ["Mid", "‹  0 dB  ›"], ["Treble", "‹  0 dB  ›"]], r["speaker"]
assert len(r["speaker"]) + 1 <= 5, "the page and its Back don't fit 5 rows"
assert r["speakerNote"] == "Sound", r["speakerNote"]
assert r["speakerRuns"] == ["set speaker joey", "tone speaker 1 0 0", "tone speaker 0 0 -1"], r["speakerRuns"]
assert r["headphones"][0] == ["Headphone EQ", "‹  Thor tuning  ›"] and r["headphones"][1] == ["Bass", "‹  +2 dB  ›"], r["headphones"]
assert r["headphones"][3] == ["Treble", "‹  -1 dB  ›"], r["headphones"]
# Headphones: Thor tuning, Off, then each saved AutoEQ profile, wrapping around.
assert r["headphonesRuns"] == ["set headphones off", "use 'HD 600'", "tone headphones 3 0 -1"], r["headphonesRuns"]
assert r["edgeRuns"] == ["tone speaker 5 0 -6"], f"stepped past ±6 dB: {r['edgeRuns']}"
assert r["bluetooth"][0][0] == "Speaker EQ" and "Bluetooth" in r["bluetoothNote"], (r["bluetooth"], r["bluetoothNote"])
assert r["game"][0] == ["Speaker EQ", "‹  Joey (Retro Handhelds)  ›"] and r["gameRuns"] == [], (r["game"], r["gameRuns"])
print("ok")
