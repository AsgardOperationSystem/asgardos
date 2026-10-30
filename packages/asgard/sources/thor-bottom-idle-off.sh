#!/bin/sh
# thor-bottom-idle-off.sh [delay]: after a game starts, power the bottom panel off unless something opened there.
# Asgard Home used to power it off at once, and a dual-screen game (lowerdeck, melonDS, Azahar) powered it straight
# back on: two modesets within a second while the game's top window commits, which can time the top panel out.
sleep "${1:-3}"
swaymsg -t get_tree | python3 -c 'import json, sys
def busy(n, o=None):
    if n.get("type") == "output":
        o = n.get("name")
    return (o == "DSI-1" and bool(n.get("pid"))) or any(busy(c, o) for c in n.get("nodes", []) + n.get("floating_nodes", []))
sys.exit(0 if busy(json.load(sys.stdin)) else 1)' || swaymsg output DSI-1 power off
