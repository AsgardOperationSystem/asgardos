#!/bin/sh
# spec: PWR-4
# Stub check for sleep.d/asgard-charge-fix's game freeze: the game's process tree is stopped before sleep,
# continued on a normal wake, and kept stopped (re-suspend timer armed) on a cable wake with the lid shut.
set -e
T=$(mktemp -d); trap 'rm -rf $T' EXIT
H=$(dirname "$(readlink -f "$0")")/../sleep.d/asgard-charge-fix
mkdir -p $T/bin $T/run $T/sys/bus/auxiliary/devices/pmic_glink.ucsi.0/power
W=$T/sys/bus/auxiliary/devices/pmic_glink.ucsi.0/power/wakeup_active_count
# 100 = launching shell, 101 runemu.sh, 102 emulator (child of 101), 200 unrelated, 1 init
printf '#!/bin/sh\nprintf "1 0\\n100 1\\n101 100\\n102 101\\n200 1\\n"\n' > $T/bin/ps
printf '#!/bin/sh\necho "$@" >> %s/kill.log\n' $T > $T/bin/kill
printf '#!/bin/sh\necho "$@" >> %s/run.log\n' $T > $T/bin/systemd-run
printf '#!/bin/sh\necho "b $(cat %s/lid)"\n' $T > $T/bin/busctl
chmod +x $T/bin/*
mkdir -p $T/sys/class/power_supply/battery $T/sys/class/power_supply/qcom-battmgr-usb $T/sys/class/rtc/rtc0
P=$T/sys/class/power_supply; A=$T/sys/class/rtc/rtc0/wakealarm
echo 6000000 > $P/battery/charge_full; echo 3000000 > $P/battery/charge_counter; echo 0 > $P/qcom-battmgr-usb/online
echo 50 > $P/battery/capacity; : > $A
run() { PATH=$T/bin:$PATH KILL=$T/bin/kill SYS=$T/sys RUN=$T/run LOG=$T/log CFG=$T/cfg RATE=$T/rate sh "$H" $1; }
printf 'gb|retroarch|gambatte|100|Zelda\n' > $T/run/thor-playing.txt

echo 1 > $W; echo false > $T/lid
run pre
[ "$(sort $T/run/.asgard-frozen | tr '\n' ' ')" = "101 102 " ] || { echo "FAIL: tree"; cat $T/run/.asgard-frozen; exit 1; }
grep -q '^-STOP 101 102$\|^-STOP 102 101$' $T/kill.log || { echo "FAIL: stop"; cat $T/kill.log; exit 1; }
run post   # normal wake (no cable): continued
grep -q '^-CONT' $T/kill.log && [ ! -e $T/run/.asgard-frozen ] || { echo "FAIL: cont"; cat $T/kill.log; exit 1; }

: > $T/kill.log; run pre; echo 2 > $W; echo true > $T/lid
run post   # cable wake, lid shut: still stopped, re-suspend armed
! grep -q CONT $T/kill.log && grep -q 'systemctl suspend' $T/run.log || { echo "FAIL: cable wake"; cat $T/kill.log $T/run.log; exit 1; }

# Charge limit asleep: on the charger at 50 % (limit 80), 2000 mA -> 30 % of 6000 mAh = 1800 mAh = 3240 s, halved
: > $T/run.log; rm -f $T/run/thor-playing.txt; echo 1 > $P/qcom-battmgr-usb/online; echo false > $T/lid
printf 'asgard.charge_limit=80\n' > $T/cfg
run pre
[ "$(cat $A)" = +1620 ] || { echo "FAIL: alarm"; cat $A; exit 1; }
# the alarm fired (reads back empty) after 3600 s and 1000 mAh, lid shut: rate learnt (1000 mA), re-suspend armed
: > $A; read t0 c0 < $T/run/.asgard-charge-alarm; echo "$((t0 - 3600)) $c0" > $T/run/.asgard-charge-alarm
echo 4000000 > $P/battery/charge_counter; echo true > $T/lid
run post
[ "$(cat $T/rate)" = 1000 ] && grep -q 'systemctl suspend' $T/run.log || { echo "FAIL: alarm wake"; cat $T/rate $T/run.log; exit 1; }
# a learnt rate below 2000 mA doesn't stretch the alarm
echo 3000000 > $P/battery/charge_counter; run pre; [ "$(cat $A)" = +1620 ] || { echo "FAIL: rate floor"; cat $A; exit 1; }
# limit off ("full", 100) or unplugged: no alarm
printf 'asgard.charge_limit=full\n' > $T/cfg; echo x > $A; run pre; [ "$(cat $A)" = x ] || { echo "FAIL: full"; exit 1; }
printf 'asgard.charge_limit=80\n' > $T/cfg; echo 0 > $P/qcom-battmgr-usb/online; run pre; [ "$(cat $A)" = x ] || { echo "FAIL: unplugged"; exit 1; }
echo OK
