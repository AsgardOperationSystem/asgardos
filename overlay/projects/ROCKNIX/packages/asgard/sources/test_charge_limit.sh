#!/bin/sh
# Fake-sysfs check for asgard-charge-limit.sh: holds at the limit, resumes 5 % below it, off at 100.
T=$(mktemp -d); trap 'kill $P 2>/dev/null; rm -rf $T' EXIT
echo 4680000 > $T/constant_charge_current_max; echo 4680000 > $T/constant_charge_current
echo asgard.charge_limit=80 > $T/cfg
BAT=$T CFG=$T/cfg INTERVAL=0.05 sh "$(dirname "$0")/asgard-charge-limit.sh" & P=$!
step() { echo $1 > $T/capacity; sleep 0.3; [ "$(cat $T/constant_charge_current)" = $2 ] || { echo "FAIL: $3"; exit 1; }; }
step 70 4680000 "charging below the limit"
step 80 0 "not held at the limit"
step 77 0 "resumed above limit - 5"
step 75 4680000 "not resumed at limit - 5"
step 79 4680000 "held again before the limit"
step 85 0 "not held above the limit"
echo asgard.charge_limit=100 > $T/cfg; step 85 4680000 "limit off didn't resume"
echo OK
