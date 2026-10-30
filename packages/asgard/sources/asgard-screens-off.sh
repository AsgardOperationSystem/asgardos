#!/bin/bash
# "Screens off, keep running" (emulator option Sleep = sleep_mode=screen, e.g. the Music Player): while that game runs,
# asgard-perf-profile.sh holds a sleep inhibitor and power-handler sends the power key and the lid here instead of
# suspending. Lid closed / a press: both screens and touch off, the A715/A710/X3 offline and the A510s capped, stick
# lights off, Wi-Fi / Bluetooth off when the game's sleep_wifi / sleep_bt is "off". The game keeps running (music keeps
# playing on the headphone jack). Lid open / another press: all back, and the game's own CPU profile again.
#   asgard-screens-off.sh power | lid close | lid open | release
. /etc/profile.d/001-functions
. /usr/share/asgard/asgard-cpu-lib.sh
STATE=/run/asgard-screens-off.active   # what was changed, for "on"
KEEP=/run/asgard-keep-running          # "<platform>\t<rom>" of the running game (asgard-perf-profile.sh)
LITTLE_CAP=50                          # ponytail: A510 share while off, enough for music decoding; tune if it stutters
export SWAYSOCK=${SWAYSOCK:-$(ls /run/0-runtime-dir/sway-ipc.* 2>/dev/null | head -1)}

off() {
  [ -e $STATE ] && return
  local platform game
  IFS=$'\t' read -r platform game < $KEEP 2>/dev/null
  # Lit outputs and enabled touch inputs, so "on" restores exactly those.
  swaymsg -t get_outputs -r | python3 -c 'import json,sys; [print("output="+o["name"]) for o in json.load(sys.stdin) if o.get("power")]' > $STATE
  swaymsg -t get_inputs -r | python3 -c 'import json,sys; [print("touch="+i["identifier"]) for i in json.load(sys.stdin) if i.get("type")=="touch" and i.get("libinput",{}).get("send_events")=="enabled"]' >> $STATE
  for o in $(sed -n 's/^output=//p' $STATE); do swaymsg -q output "$o" power off; done
  for i in $(sed -n 's/^touch=//p' $STATE); do swaymsg -q input "$i" events disabled; done
  autotune_stop   # "on" restarts it with the game's profile
  online_type mid 0; online_type prime 0; set_cap little $LITTLE_CAP; write_affinity
  echo "led=$(get_setting led.color)" >> $STATE
  ledcontrol off >/dev/null 2>&1
  for r in wifi:wlan bt:bluetooth; do
    [ "$(get_setting "sleep_${r%%:*}" "$platform" "$game")" = off ] || continue
    rfkill list "${r#*:}" | grep -q "Soft blocked: yes" && continue   # already off: leave it so on "on"
    rfkill block "${r#*:}" && echo "rfkill=${r#*:}" >> $STATE
  done
}

on() {
  [ -e $STATE ] || return
  local platform game led
  IFS=$'\t' read -r platform game < $KEEP 2>/dev/null
  /usr/share/asgard/asgard-cpu-cap.sh                                         # all cores, global settings
  [ -n "$platform" ] && /usr/share/asgard/asgard-perf-profile.sh cpu "$platform" "$game"   # and the game's
  for r in $(sed -n 's/^rfkill=//p' $STATE); do rfkill unblock "$r"; done
  led=$(sed -n 's/^led=//p' $STATE)
  [ -n "$led" ] && [ "$led" != off ] && ledcontrol "$led" >/dev/null 2>&1
  for o in $(sed -n 's/^output=//p' $STATE); do swaymsg -q output "$o" power on, output "$o" dpms on; done
  for i in $(sed -n 's/^touch=//p' $STATE); do swaymsg -q input "$i" events enabled; done
  rm -f $STATE
}

case "$1" in
  power) if [ -e $STATE ]; then on; else off; fi ;;
  lid) if [ "$2" = close ]; then off; else on; fi ;;
  release) ;;   # power-handler's pre-suspend call: nothing of ours can be suspended under (the inhibitor holds)
esac
