#!/bin/sh
# thor-bottom-rotate.sh [delay]: turn the bottom panel (DSI-1) landscape, only when it isn't already.
# Every output change is a modeset on the display controller both panels share; one racing the top panel's commit
# timed the top panel out (frame done timeout, garbled until reboot: 2026-10-09, 2026-10-10). The window rules used
# to re-rotate on every bottom window that mapped, almost always for nothing.
[ -n "$1" ] && sleep "$1"
T=$(swaymsg -t get_outputs | python3 -c 'import json, sys
print(next((o["transform"] for o in json.load(sys.stdin) if o["name"] == "DSI-1"), ""))')
[ "$T" = 90 ] || swaymsg output DSI-1 transform 90
