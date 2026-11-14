#!/bin/sh
# thor-bottom-idle-off.sh [delay]: after a game starts, power the bottom panel off unless something opened there.
# Asgard Home used to power it off at once, and a dual-screen game (lowerdeck, melonDS, Azahar) powered it straight
# back on: two modesets within a second while the game's top window commits, which can time the top panel out.
# A visible window on another output that reaches into the bottom panel counts too: RetroArch's DS cores span both
# panels with one floating window that belongs to the top screen's workspace (vertical-check, COMP-5).
sleep "${1:-3}"
swaymsg -t get_tree | python3 -c 'import json, sys
tree = json.load(sys.stdin)
bottom = next((o.get("rect") for o in tree.get("nodes", []) if o.get("name") == "DSI-1"), None)
def reaches(r):
    return bool(bottom and r) and r["x"] < bottom["x"] + bottom["width"] and bottom["x"] < r["x"] + r["width"] \
        and r["y"] < bottom["y"] + bottom["height"] and bottom["y"] < r["y"] + r["height"]
def busy(n, o=None):
    if n.get("type") == "output":
        o = n.get("name")
    if n.get("pid") and (o == "DSI-1" or (o != "__i3" and n.get("visible") and reaches(n.get("rect")))):
        return True
    return any(busy(c, o) for c in n.get("nodes", []) + n.get("floating_nodes", []))
sys.exit(0 if busy(tree) else 1)' || swaymsg output DSI-1 power off
