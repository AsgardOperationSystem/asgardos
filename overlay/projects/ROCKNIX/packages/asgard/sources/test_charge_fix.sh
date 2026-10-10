#!/bin/sh
# Fake-sysfs check for sleep.d/asgard-charge-fix: rebinds when discharging with no partner or with a charger online.
set -e
T=$(mktemp -d); trap 'rm -rf $T' EXIT
D=$(dirname "$(readlink -f "$0")")/../sleep.d/asgard-charge-fix
mkdir -p $T/class/power_supply/battery $T/class/power_supply/qcom-battmgr-usb \
  $T/bus/auxiliary/drivers/ucsi_glink.pmic_glink_ucsi/pmic_glink.ucsi.0
run() { SYS=$T LOG=$T/log WAIT=0 sh "$D" check 2>/dev/null; }
set_state() { echo $1 > $T/class/power_supply/battery/status; echo $2 > $T/class/power_supply/qcom-battmgr-usb/online; }
U=$T/bus/auxiliary/drivers/ucsi_glink.pmic_glink_ucsi/unbind

set_state Charging 1;    run; [ ! -e $U ] || { echo "FAIL: rebound while charging"; exit 1; }
mkdir -p $T/class/typec/port0-partner
set_state Discharging 0; run; [ ! -e $U ] || { echo "FAIL: rebound with a USB device we power"; exit 1; }
rmdir $T/class/typec/port0-partner
set_state Discharging 0; run; [ "$(cat $U)" = pmic_glink.ucsi.0 ] || { echo "FAIL: no rebind when stuck"; exit 1; }
grep -q "stuck" $T/log && grep -q "after" $T/log || { echo "FAIL: log"; exit 1; }
echo OK
