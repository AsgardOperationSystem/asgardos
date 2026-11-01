#!/bin/sh
# spec: BAT-2
# gap: asgard-charge-limit.sh charges at 20 % as well (-gt 20), though BAT-2 and its own comment say only below 20 %.
T=$(mktemp -d); trap 'kill $P 2>/dev/null; rm -rf "$T"' EXIT
echo 4680000 > "$T/constant_charge_current_max"; echo 4680000 > "$T/constant_charge_current"
printf 'asgard.bypass_charging=1\n' > "$T/cfg"; echo 20 > "$T/capacity"
BAT="$T" CFG="$T/cfg" INTERVAL=0.05 sh "$(dirname "$0")/asgard-charge-limit.sh" & P=$!
sleep 0.3
[ "$(cat "$T/constant_charge_current")" = 0 ] || { echo "FAIL: charging at exactly 20 %"; exit 1; }
echo OK
