# spec: LOOK-3
# requires: cmd:python3
# gap: the grid's scroll (Main.qml) and the card's settle (HeroCard.qml) follow the selection with fixed durations: 260 ms, and still moving with Animations off
"""Run: python -I test_look_motion.py  (no Thor, no Qt): what moves when the selection moves must take its time from Theme, so
the Animations setting stops it. Theme's own values and the tiles and backdrop are in test_home_settings.py."""
import os
import re

QML = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../asgard-home/src/qml")
main = open(f"{QML}/Main.qml").read()
card = open(f"{QML}/HeroCard.qml").read()
settle = re.search(r"id: settle.*?\n    }\n", card, re.S).group(0)

assert re.search(r"Behavior on contentY \{ NumberAnimation \{ duration: Theme\.anim", main), "the grid's scroll"
assert not re.search(r"duration: \d", settle), "the card's settle"
print("ok")
