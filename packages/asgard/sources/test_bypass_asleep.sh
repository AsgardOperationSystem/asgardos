#!/bin/sh
# spec: BAT-2
# The charge loop is frozen asleep, and below the floor it left the charge current on. Nothing else can stop it: it needs the wake.
set -e
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
S=$T/sys/class; mkdir -p "$T/run" "$S/power_supply/battery" "$S/power_supply/qcom-battmgr-usb" "$S/rtc/rtc0"
echo 1 > "$S/power_supply/qcom-battmgr-usb/online"; echo 15 > "$S/power_supply/battery/capacity"
echo 6000000 > "$S/power_supply/battery/charge_full"; echo 900000 > "$S/power_supply/battery/charge_counter"
printf 'asgard.bypass_charging=1\n' > "$T/cfg"
SYS="$T/sys" RUN="$T/run" LOG="$T/log" CFG="$T/cfg" RATE="$T/rate" KILL=true sh "$(dirname "$(readlink -f "$0")")/../sleep.d/asgard-charge-fix" pre
[ -s "$S/rtc/rtc0/wakealarm" ] && grep -q '^+' "$S/rtc/rtc0/wakealarm" || { echo "FAIL: no wake to stop at the floor"; exit 1; }
echo OK
