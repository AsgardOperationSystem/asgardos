# spec: SET-2 CFG-14 SCR-1 SCR-2 SCR-3
# requires: cmd:node
"""Run: python -I test_settings_screens.py  (no Thor, no Qt): Settings > Hardware > Display's per-screen pages, by running
those functions from Settings.qml in node with stub rows. The moved rows must keep their flat keys, defaults and commands."""
import json
import os
import re
import subprocess

QML = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../asgard-home/src/qml/Settings.qml")
src = open(QML).read()


def function(name):
    """The text of `function name(...) {...}`, its closing brace being the first one at the function's own indent."""
    m = re.search(r"^( *)function " + name + r"\(.*?^\1}", src, re.M | re.S)
    assert m, name
    return m.group(0)


display = re.search(r'case "Display": return (\[.*?)^ *case "Performance"', src, re.M | re.S).group(1)
script = """
const shell = [], cfg = JSON.parse(process.argv[1])
const backend = { shell: c => shell.push(c) }
const get = (k, d) => k in cfg ? cfg[k] : (d === undefined ? "" : d)
const percents = [], ledPage = () => []
const row = (kind, title, key, dflt, after) => ({ kind, title, key, dflt, after })
const toggle = (icon, title, sub, key, dflt, after) => row("toggle", title, key, dflt, after)
const choice = (icon, title, sub, key, dflt, choices, after) => row("choice", title, key, dflt, after)
const link = (icon, title, sub, page) => ({ kind: "link", title, page })
%s
const show = page => page.flat().map(r => {
    if (r.after && r.title === "Brightness") r.after("70")
    return { title: r.title, key: r.key, dflt: r.dflt, page: r.page && r.title.endsWith(" screen") ? show(r.page()) : undefined }
})
console.log(JSON.stringify({ rows: show(%s), shell }))
""" % ("\n".join(function(f) for f in ("wbSteps", "wbRow", "brightnessRows", "topScreenPage", "bottomScreenPage")), display)


def run(cfg):
    return json.loads(subprocess.run(["node", "-e", script, json.dumps(cfg)], check=True, capture_output=True, text=True).stdout)


def keys(rows):
    return {r["title"]: (r.get("key"), r.get("dflt")) for r in rows}


def page(rows, title):
    return next(r["page"] for r in rows if r["title"] == title)


TOP = {"Refresh rate": ("asgard.refresh", "120"), "Warmth": ("asgard.warmth.top", "0"), "Tint": ("asgard.tint.top", "0"),
       "Contrast": ("asgard.contrast.top", "0"), "OLED Ultra Black": ("asgard.ultra_black", "1")}
BOTTOM = {"Refresh rate": ("asgard.refresh_bottom", "60"), "Warmth": ("asgard.warmth.bottom", "0"),
          "Tint": ("asgard.tint.bottom", "3"), "Contrast": ("asgard.contrast.bottom", "3"),
          "RetroArch games": ("asgardos.bottomscreen.type", "vc")}

# Linked brightness: one row on Display, none on the screens' pages
linked = run({})
assert keys(linked["rows"])["Brightness"] == ("display.brightness2", "50")
assert keys(page(linked["rows"], "Top screen")) == TOP
assert keys(page(linked["rows"], "Bottom screen")) == BOTTOM
assert "brightness set 70" in linked["shell"]

# Separate brightness: each screen's row is on its page, with ROCKNIX's screen number (1 = bottom, 2 = top)
split = run({"asgard.brightness_split": "1"})
assert "Brightness" not in keys(split["rows"])
assert keys(page(split["rows"], "Top screen")) == {"Brightness": ("display.brightness2", "50"), **TOP}
assert keys(page(split["rows"], "Bottom screen")) == {"Brightness": ("display.brightness", "50"), **BOTTOM}
assert split["shell"] == ["brightness set 2 70", "brightness set 1 70"]

# Nothing per-screen is left on Display itself
assert not [r["title"] for r in linked["rows"] if re.search(r"(?i)(top|bottom) screen .|warmth|tint|contrast|refresh", r["title"])]
print("ok")
