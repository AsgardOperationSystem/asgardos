#!/bin/bash
# Thor battery logger: one CSV line every 30 s to /storage/battery-log.csv.
# Suspend shows up as a gap in ts (the loop is frozen while asleep), so sleep drain = capacity/charge delta across the gap.
# Cost: one wakeup per 30 s, a handful of sysfs reads, one ps. Rotates at 5 MB (keeps one .1).
LOG=/storage/battery-log.csv
B=/sys/class/power_supply/battery
C=/sys/devices/system/cpu/cpufreq
G=$(ls -d /sys/class/devfreq/*gpu* 2>/dev/null | head -1)
BL=(/sys/class/backlight/*)
U=/sys/class/power_supply/qcom-battmgr-usb
# usb_online/bat_status: catches "plugged in but not charging" (2026-10-09: drained at -500 mA on the charger
# after a 4 h sleep; a reboot fixed it, and the RAM journal lost the why).
# game/core: what Home launched (playlog.py's /run/thor-playing.txt), so a native port or PC app isn't "menu".
# ocv_uv/charge_full_uah: the gauge's resting-voltage estimate and capacity. Above ~65 % capacity and charge_uah run behind
# the measured current (2026-11-02: 2.6x at "80 %"), so these show how full the battery really is, and how far the capacity drifts.
HDR="ts,capacity,current_ua,voltage_uv,charge_uah,bat_temp,cpu0_khz,cpu3_khz,cpu7_khz,gpu_hz,bl_top,bl_bottom,suspends,app,usb_online,usb_ua,bat_status,game,core,ocv_uv,charge_full_uah"
[ "$(head -1 "$LOG" 2>/dev/null)" = "$HDR" ] || { [ -s "$LOG" ] && mv "$LOG" "$LOG.1"; echo "$HDR" > "$LOG"; }
while :; do
  [ "$(stat -c %s "$LOG")" -gt 5242880 ] && mv "$LOG" "$LOG.1" && echo "$HDR" > "$LOG"
  procs=$(ps -eo comm=,args=)
  p_sys= p_emu= p_core= p_game=
  [ -r /run/thor-playing.txt ] && IFS='|' read -r p_sys p_emu p_core _ p_game < /run/thor-playing.txt
  app=$p_emu
  [ -z "$app" ] && app=$(echo "$procs" | awk '{print $1}' | grep -m1 -E "^(azahar|retroarch|dolphin-emu|ppsspp|PPSSPP|melonDS|pcsx2|aethersx2|armsx2|drastic|mupen64plus|flycast|duckstation|ryujinx|citron|eden|moonlight|portmaster)")
  # A game with no known emulator process (PC apps, native ports): its system.
  [ -z "$app" ] && app=$p_sys
  # Thor's own UIs and the frontend, so idle/menu time is attributed too (panel = bottom screen on).
  if [ -z "$app" ]; then
    case "$procs" in
      *thor_panel.py*) app=panel ;;
      *thor_settings.py*) app=settings ;;
    esac
  fi
  echo "$(date +%s),$(<$B/capacity),$(<$B/current_now),$(<$B/voltage_now),$(<$B/charge_counter),$(<$B/temp),$(<$C/policy0/scaling_cur_freq),$(<$C/policy3/scaling_cur_freq),$(<$C/policy7/scaling_cur_freq),$(<$G/cur_freq),$(<${BL[0]}/brightness),$(<${BL[1]}/brightness),$(</sys/power/suspend_stats/success),${app:-menu},$(<$U/online),$(<$U/current_now),$(<$B/status),\"${p_game//\"/\"\"}\",$p_core,$(<$B/voltage_ocv),$(<$B/charge_full)" >> "$LOG"
  sleep 30
done
