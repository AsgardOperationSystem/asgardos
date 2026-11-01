#!/bin/sh
# spec: PWR-6
# Fake-sysfs check for sleep.d/asgard-fan-sleep: mode 1 becomes 3 for the sleep and comes back; other modes untouched.
set -e
T=$(mktemp -d); trap 'rm -rf $T' EXIT
H=$(dirname "$(readlink -f "$0")")/../sleep.d/asgard-fan-sleep
E=$T/class/hwmon/hwmon3/pwm1_enable; mkdir -p ${E%/*}
r() { SYS=$T MARK=$T/mark sh $H $1; }
echo 1 > $E; r pre; [ "$(cat $E)" = 3 ]; r post; [ "$(cat $E)" = 1 ]
echo 0 > $E; r pre; [ "$(cat $E)" = 0 ]; r post; [ "$(cat $E)" = 0 ]
echo 2 > $E; r pre; [ "$(cat $E)" = 2 ]
echo ok
