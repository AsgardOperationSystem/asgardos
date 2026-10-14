#!/bin/sh
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
run() { PATH=$T/bin:$PATH KILL=$T/bin/kill SYS=$T/sys RUN=$T/run LOG=$T/log sh "$H" $1; }
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
echo OK
