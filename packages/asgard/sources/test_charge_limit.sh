#!/bin/sh
# spec: PWR-5
# Fake-sysfs check for asgard-charge-limit.sh: holds at the limit, resumes 5 % below it, off at 100, held at 100 with "full".
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
step 100 4680000 "limit off held at 100"
echo asgard.charge_limit=full > $T/cfg; step 99 4680000 "full: held below 100"
step 100 0 "full: not held at 100"
step 96 0 "full: resumed above 95"
step 95 4680000 "full: not resumed at 95"
kill $P; wait $P 2>/dev/null

# Recalibration: with charge_full readable, no anchor yet counts as drifted. Under the limit, one charge goes to 100 %,
# which records the anchor; then the limit holds again. 5 % of drift above the anchor brings it back; bypass and
# limit-off never do.
flag() { if [ "$1" = on ]; then [ -e $T/recal ] || { echo "FAIL: $2"; exit 1; }; else [ ! -e $T/recal ] || { echo "FAIL: $2"; exit 1; }; fi; }
echo asgard.charge_limit=80 > $T/cfg; echo 7000000 > $T/charge_full; echo 4680000 > $T/constant_charge_current
BAT=$T CFG=$T/cfg ANCHOR=$T/state/anchor RECAL_FLAG=$T/recal INTERVAL=0.05 sh "$(dirname "$0")/asgard-charge-limit.sh" & P=$!
step 80 4680000 "no anchor: not charging on past the limit"; flag on "no anchor: no flag"
step 99 4680000 "recalibrating: held before 100"
step 100 0 "recalibrated: not held at 100"; flag off "recalibrated: flag left"
[ "$(cat $T/state/anchor)" = 7000000 ] || { echo "FAIL: anchor not recorded at 100"; exit 1; }
step 90 0 "after the full charge: the limit doesn't hold"
step 75 4680000 "after the full charge: not resumed at limit - 5"
step 80 0 "after the full charge: not held at the limit"
echo 7340000 > $T/charge_full; step 80 0 "4.9 % drift: recalibrated already"; flag off "4.9 % drift: flag"
echo 7350000 > $T/charge_full; step 80 4680000 "5 % drift: not charging on"; flag on "5 % drift: no flag"
echo asgard.bypass_charging=1 >> $T/cfg; step 80 0 "bypass: recalibrated"; flag off "bypass: flag"
echo asgard.charge_limit=100 > $T/cfg; step 80 4680000 "limit off: not charging"; flag off "limit off: flag"
echo asgard.charge_limit=80 > $T/cfg; echo junk > $T/state/anchor; step 80 4680000 "unreadable anchor: not recalibrating"
echo OK
