# spec: HOME-7 LOOK-1
# requires: cmd:python3
"""Run: python -I test_home_tree.py  (no Thor, no Qt): what the source shows. HOME-7: no translations in Home, and the frontend's
start script sets the UTF-8 locale; that Home and a game really run in it is a device check. LOOK-1: Theme.qml is where the font
comes from and every text uses it, and its tokens exist. Not colours: existing screens still carry literals of their own, so
those and the rest of the look are a human check."""
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
HOME = os.path.join(HERE, "../../asgard-home/src")
sources = {}
for folder in (HOME, f"{HOME}/qml"):
    for name in os.listdir(folder):
        if name.endswith((".cpp", ".h", ".qml")):
            sources[name] = open(f"{folder}/{name}").read()

# HOME-7: English only
for name, text in sources.items():
    assert not re.search(r"\bQTranslator\b|\bqsTr\w*\(|\btr\(\"", text), name
cmake = open(f"{HOME}/CMakeLists.txt").read()
assert "LinguistTools" not in cmake and "qt_add_translations" not in cmake

# HOME-7: UTF-8, before the frontend starts
start = open(os.path.join(HERE, "start_frontend.sh")).read()
locale = re.search(r"^export .*\bLANG=C\.UTF-8\b", start, re.M)
assert locale, "start_frontend.sh must set the locale"
assert locale.start() < start.index("exec /usr/bin/asgard-home")

# LOOK-1: one typeface, from Theme
theme = sources["Theme.qml"]
assert re.search(r'readonly property string font: \w+\.name', theme)
fonts = os.listdir(f"{HOME}/qml/fonts")
assert fonts and all(f.startswith("Nunito") for f in fonts if f.endswith(".ttf"))
for weight in re.findall(r'FontLoader \{ source: "fonts/([^"]+)"', theme):
    assert weight.startswith("Nunito"), weight
for name, text in sources.items():
    if name.endswith(".qml"):
        for family in re.findall(r"font\.family:\s*([^;\n}]+)", text):
            assert family.strip() == "Theme.font", (name, family)
        assert not re.search(r'FontLoader', text) or name == "Theme.qml", name
# The named pieces it promises exist: pills, their rim, panels, the selection glow, timing
for token in ("pill", "pillRim", "panel", "panelRim", "selA", "selB", "font", "anim", "fade"):
    assert re.search(r"(readonly )?property \w+ " + token + r"\b", theme), token
print("ok")
