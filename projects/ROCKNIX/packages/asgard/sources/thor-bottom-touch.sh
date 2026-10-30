#!/bin/sh
# Bottom touchscreen only while the bottom panel is on. Single-screen games (every RetroArch core, PSP, PS2, ...)
# run with DSI-1 powered off but its touchscreen left enabled: a touch on the dark panel moved sway's focus to the
# empty bottom workspace, RetroArch paused (pause_nonactive) and other emulators lost input focus. Follows every
# `output DSI-1 power on/off`, whoever sends it (sway emits an output event for each). Its evdev events still reach
# thor-idle-blank.py (it reads the devices directly), so a touch still wakes blanked screens.
export SWAYSOCK=${SWAYSOCK:-/var/run/0-runtime-dir/sway-ipc.0.sock}
sync_touch() {
  on=$(swaymsg -t get_outputs | python3 -c 'import json, sys
print(any(o["name"] == "DSI-1" and o.get("power") for o in json.load(sys.stdin)))')
  swaymsg input 0:0:bottom_touchscreen events "$([ "$on" = True ] && echo enabled || echo disabled)" >/dev/null
}
sync_touch
swaymsg -t subscribe -m '["output"]' | while read -r _; do sync_touch; done
