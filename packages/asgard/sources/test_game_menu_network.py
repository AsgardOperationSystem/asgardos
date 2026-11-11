# spec: MENU-6
# requires: cmd:node
"""Run: python -I test_game_menu_network.py  (no Thor, no Qt): the in-game menu's Wi-Fi and Bluetooth, by running those
functions from GameMenu.qml and Settings.qml in node with a stub backend. Every menu, a tool's too, gets the tile; its
two tiles open Settings' own Network pages (Wi-Fi scanning, as when picked in Settings) with Back closing them; while one
is open it takes the buttons, so B doesn't resume the game; back from it, the tiles show what was switched there; and the
menu closing closes it. That the page shows on the
menu's screen and pairs or joins there is a device check."""
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


# The menu has its own Settings (it may be in the other window from Home's), and closing the menu closes it.
assert re.search(r"Loader \{ id: network;.*sourceComponent: Settings \{ menuStyle: true \}", menu), \
    "the menu has no Settings of its own, or it isn't drawn as the menu"
assert re.search(r"if \(networkOpen\) network\.item\.close\(\)", menu), "closing the menu leaves the network page open"

script = """
const cfg = { "wifi.enabled": "1", "bluetooth.enabled": "0" }
const backend = { getSetting: (k, d) => k in cfg ? cfg[k] : d }
const Loader = { Ready: 1 }

// Settings: showNetwork with its openRow, the Network section's two links stubbed
const wifiPage = () => [], btPage = () => []
let stack = [], row = 0, zone = "side", cat = 0, opened = 0, scanned = 0, btScan = 0, rev = 0
const categories = [{ title: "General" }, { title: "Hardware" }, { title: "Power" }]
const show = () => { opened++; stack = []; zone = "side" }
const scan = () => { scanned++ }, btScanStart = () => { btScan++ }, sh = () => {}, note = () => {}
const btScanPage = () => [], batteryPage = () => []
const section = t => t === "Network" ? [[{ kind: "link", title: "Wi-Fi", page: wifiPage },
                                         { kind: "link", title: "Bluetooth", page: btPage }], [{ kind: "choice", title: "USB connection" }]] : []
%s
%s
const out = {}
showNetwork("Wi-Fi")
out.wifi = { n: stack.length, wifi: stack[0].build === wifiPage, back: !!stack[0].closeOnBack, scanned, zone, cat: categories[cat].title }
showNetwork("Bluetooth")
out.bt = { n: stack.length, bt: stack[0].build === btPage, back: !!stack[0].closeOnBack, scanned }

// GameMenu: the tile in every menu, its tiles, and who gets the buttons
const nets = [], navs = []
let resumed = 0, settingsOpen = false
const network = { active: false, status: 1, item: { get open() { return settingsOpen },
                  showNetwork: t => { nets.push(t); settingsOpen = true }, nav: b => navs.push(b) } }
Object.defineProperty(globalThis, "networkOpen", { get: () => network.status === Loader.Ready && network.item.open })
let open = true, game = [], openedAt = 0, onPage = false, sel = 0, group = null, shown = []
const hasPerf = () => game.length > 0, perfTiles = () => [], resume = () => { resumed++ }
const settings = null, soundTile = { title: "Sound" }   // SND-7: test_game_menu_sound.py
const activate = () => {}, back = () => {}
%s
%s
%s
const quit = { title: "Quit game" }
out.tool = withExit([{ title: "Resume" }], null, quit).map(t => t.title)
game = ["retroarch"]
out.game = withExit([{ title: "Resume" }], null, quit).map(t => t.title)
const tile = networkTile()
out.tiles = tile.items.map(t => [t.title, t.sub])
tile.items[1].run()
out.active = network.active
nav("b"); nav("a")
out.navs = navs.slice(); out.resumedWhileOpen = resumed
cfg["bluetooth.enabled"] = "1"   // switched on in the page
settingsOpen = false
out.tilesAfter = tile.items.map(t => [t.title, t.sub])
nav("b")
out.resumedAfter = resumed
out.nets = nets
console.log(JSON.stringify(out))
""" % (function(panel, "showNetwork"), function(panel, "openRow"),
       function(menu, "networkTile"), function(menu, "openNetwork"),
       function(menu, "withExit") + "\n" + function(menu, "nav"))

p = subprocess.run(["node", "-e", script], capture_output=True, text=True)
assert p.returncode == 0, p.stderr[-2000:]
r = json.loads(p.stdout)

assert r["wifi"] == {"n": 1, "wifi": True, "back": True, "scanned": 1, "zone": "list", "cat": "Hardware"}, r["wifi"]
assert r["bt"] == {"n": 1, "bt": True, "back": True, "scanned": 1}, r["bt"]   # Bluetooth doesn't start a Wi-Fi scan
assert "Wi-Fi and Bluetooth" in r["tool"], f"a tool's menu has no Wi-Fi and Bluetooth: {r['tool']}"
assert "Wi-Fi and Bluetooth" in r["game"], f"a game's menu has no Wi-Fi and Bluetooth: {r['game']}"
assert r["game"].index("Wi-Fi and Bluetooth") < len(r["game"]) - 1, "the tile came after Exit/Quit"
assert r["tiles"] == [["Wi-Fi", "On"], ["Bluetooth", "Off"]], r["tiles"]
assert r["active"] and r["nets"] == ["Bluetooth"], (r["active"], r["nets"])
assert r["navs"] == ["b", "a"] and r["resumedWhileOpen"] == 0, "the open network page didn't take the buttons"
assert r["tilesAfter"] == [["Wi-Fi", "On"], ["Bluetooth", "On"]], f"the tiles kept the menu's opening state: {r['tilesAfter']}"
assert r["resumedAfter"] == 1, "with the page closed, B no longer resumes"
print("ok")
