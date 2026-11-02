#!/bin/bash
# "Screens off, keep running" (emulator option Sleep = sleep_mode=screen, e.g. the Music Player): while that game runs,
# asgard-perf-profile.sh holds a sleep inhibitor and power-handler sends the power key and the lid here instead of
# suspending. Lid closed / a press: both screens and touch off, the A715/A710/X3 offline and the A510s capped, stick
# lights off, Wi-Fi / Bluetooth off when the game's sleep_wifi / sleep_bt, else asgard.sleep_*, is "off". The game keeps running (music keeps
# playing on the headphone jack). Lid open / another press: all back, and the game's own CPU profile again.
#   asgard-screens-off.sh power | lid close | lid open | release
#   asgard-screens-off.sh reconnect <address>...   started by "on": see reconnect()
. /etc/profile.d/001-functions
. /usr/share/asgard/asgard-cpu-lib.sh
STATE=/run/asgard-screens-off.active   # what was changed, for "on"
KEEP=/run/asgard-keep-running          # "<platform>\t<rom>" of the running game (asgard-perf-profile.sh)
LITTLE_CAP=50                          # ponytail: A510 share while off, enough for music decoding; tune if it stutters
export SWAYSOCK=${SWAYSOCK:-$(ls /run/0-runtime-dir/sway-ipc.* 2>/dev/null | head -1)}

off() {
  [ -e $STATE ] && return
  local platform game wanted
  IFS=$'\t' read -r platform game < $KEEP 2>/dev/null
  # Lit outputs and enabled touch inputs, so "on" restores exactly those.
  swaymsg -t get_outputs -r | python3 -c 'import json,sys; [print("output="+o["name"]) for o in json.load(sys.stdin) if o.get("power")]' > $STATE
  swaymsg -t get_inputs -r | python3 -c 'import json,sys; [print("touch="+i["identifier"]) for i in json.load(sys.stdin) if i.get("type")=="touch" and i.get("libinput",{}).get("send_events")=="enabled"]' >> $STATE
  for o in $(sed -n 's/^output=//p' $STATE); do swaymsg -q output "$o" power off; done
  for i in $(sed -n 's/^touch=//p' $STATE); do swaymsg -q input "$i" events disabled; done
  autotune_stop   # "on" restarts it with the game's profile
  online_type mid 0; online_type prime 0; set_cap little $LITTLE_CAP; write_affinity
  echo "led=$(get_setting led.color)" >> $STATE
  ledcontrol off >/dev/null 2>&1 9>&-
  for r in wifi:wlan bt:bluetooth; do
    wanted=$(get_setting "sleep_${r%%:*}" "$platform" "$game")   # the game's or system's, else Settings > Performance
    [ "${wanted:-$(get_setting "asgard.sleep_${r%%:*}")}" = off ] || continue
    rfkill list "${r#*:}" | grep -q "Soft blocked: yes" && continue   # already off: leave it so on "on"
    # Noted first: "on" unblocks what's noted, and a block that fails or is cut short mustn't leave the radio off for
    # good (2026-11-02: Bluetooth stayed blocked after the lid opened, with headphones connected). Unblocking a radio
    # that was on anyway does nothing.
    # What's connected now, for "on": bluez doesn't reconnect a device by itself when the radio comes back.
    [ "${r#*:}" = bluetooth ] && timeout 5 bluetoothctl devices Connected 2>/dev/null |
      sed -n 's/^Device \([0-9A-F:]*\) .*/bt=\1/p' >> $STATE
    echo "rfkill=${r#*:}" >> $STATE
    rfkill block "${r#*:}"
  done
}

on() {
  [ -e $STATE ] || return
  local platform game led devices
  IFS=$'\t' read -r platform game < $KEEP 2>/dev/null
  /usr/share/asgard/asgard-cpu-cap.sh 9>&-                                    # all cores, global settings
  # and the game's, unless it's waiting in the background and this is Home
  [ -n "$platform" ] && [ ! -e /run/asgard-perf.home ] && /usr/share/asgard/asgard-perf-profile.sh cpu "$platform" "$game" 9>&-
  for r in $(sed -n 's/^rfkill=//p' $STATE); do rfkill unblock "$r"; done
  led=$(sed -n 's/^led=//p' $STATE)
  [ -n "$led" ] && [ "$led" != off ] && ledcontrol "$led" >/dev/null 2>&1 9>&-
  for o in $(sed -n 's/^output=//p' $STATE); do swaymsg -q output "$o" power on, output "$o" dpms on; done
  for i in $(sed -n 's/^touch=//p' $STATE); do swaymsg -q input "$i" events enabled; done
  devices=$(sed -n 's/^bt=//p' $STATE)
  rm -f $STATE
  # Not here: it can take a while, and holds nothing the next lid or power press should wait for
  [ -n "$devices" ] && setsid "$0" reconnect $devices >/dev/null 2>&1 9>&- &
}

# Once the radio is up, connect what was connected when it went off. A device that's been turned off since just fails.
# Screens going off again ends it: that turn's "on" starts its own.
reconnect() {
  local device n
  for n in $(seq 1 20); do
    [ -e $STATE ] && return
    timeout 3 bluetoothctl show 2>/dev/null | grep -q "Powered: yes" && break
    sleep 1
  done
  for device; do
    for n in 1 2 3; do
      [ -e $STATE ] && return
      timeout 20 bluetoothctl -- connect "$device" >/dev/null 2>&1 && break
      sleep 2
    done
  done
}

if [ "$1" = reconnect ]; then   # before the lock: it mustn't hold up the next press
  shift
  reconnect "$@"
  exit
fi

# One at a time: a lid opened while "off" is still working would restore only what it had noted so far. The lock goes
# with this script, so what it starts has fd 9 closed (autotune outlives it). A stuck holder mustn't keep the screens
# off for good, so wait a bounded time and go on (BusyBox flock has no -w).
exec 9>/run/asgard-screens-off.lock
timeout 30 flock 9 || true

case "$1" in
  power) if [ -e $STATE ]; then on; else off; fi ;;
  lid) if [ "$2" = close ]; then off; else on; fi ;;
  release) ;;   # power-handler's pre-suspend call: nothing of ours can be suspended under (the inhibitor holds)
esac
