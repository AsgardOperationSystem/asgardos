#!/bin/sh
# spec: BAT-2
# Fake-sysfs check for asgard-charge-limit.sh's bypass: charge current 0 above the floor, so the cable runs the Thor and the
# battery is left alone, whatever the limit; it charges below 20 %. That the charger really carries the load is a human check.
T=$(mktemp -d); trap 'kill $P 2>/dev/null; rm -rf "$T"' EXIT
echo 4680000 > "$T/constant_charge_current_max"; echo 4680000 > "$T/constant_charge_current"
printf 'asgard.bypass_charging=1\n' > "$T/cfg"; echo 50 > "$T/capacity"
BAT="$T" CFG="$T/cfg" INTERVAL=0.05 sh "$(dirname "$0")/asgard-charge-limit.sh" & P=$!
step() { echo "$1" > "$T/capacity"; sleep 0.3; [ "$(cat "$T/constant_charge_current")" = "$2" ] || { echo "FAIL: $3"; exit 1; }; }
step 50 0 "bypass charged at 50 %"
step 21 0 "bypass charged just above the floor"
step 19 4680000 "bypass didn't charge below the floor"
step 10 4680000 "bypass didn't charge at 10 %"
step 22 0 "bypass kept charging above the floor"
printf 'asgard.charge_limit=100\nasgard.bypass_charging=1\n' > "$T/cfg"; step 60 0 "bypass charged with the limit off"
printf 'asgard.charge_limit=full\nasgard.bypass_charging=1\n' > "$T/cfg"; step 70 0 "bypass charged with the limit at full"
printf 'asgard.bypass_charging=0\nasgard.charge_limit=100\n' > "$T/cfg"; step 70 4680000 "bypass off: still not charging"
echo OK
