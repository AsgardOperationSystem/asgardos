#!/bin/sh
# Fake-sysfs check for sleep.d/asgard-sleep-audit: one CSV line per sleep with the right deltas.
set -e
T=$(mktemp -d); trap 'rm -rf $T' EXIT
H=$(dirname "$(readlink -f "$0")")/../sleep.d/asgard-sleep-audit
B=$T/class/power_supply/battery; Q=$T/kernel/debug/qcom_stats; C=$T/kernel/debug/pm_genpd/power-domain-cluster
mkdir -p $B $Q $C
state() {  # charge_uah apss_count apss_acc s1_s2idle_count
  echo $1 > $B/charge_counter; echo 4000000 > $B/voltage_now
  printf 'Count: %s\nLast Entered At: 0\nLast Exited At: 0\nAccumulated Duration: %s\n' $2 $3 > $Q/apss
  printf 'State Time(ms) Usage Rejected Above Below S2idle\nS0 0 0 0 0 0 0\nS1 513 2 0 0 0 %s\n' $4 > $C/idle_states
}
run() { SYS=$T OUT=$T/out.csv CFG=$T/cfg SNAP=$T/snap sh "$H" $1; }
printf 'asgard.sleep_audit=0\n' > $T/cfg
state 5000000 10 100 99; run pre; run post
[ ! -e $T/out.csv ] || { echo "FAIL: logged while off"; exit 1; }
printf 'asgard.sleep_audit=0\nasgard.sleep_audit=1\nasgard.sleep_experiment=wifi\n' > $T/cfg
state 5000000 10 100 99; run pre
state 4900000 12 400 100; run post
[ "$(wc -l < $T/out.csv)" = 2 ] || { echo "FAIL: lines"; cat $T/out.csv; exit 1; }
L=$(tail -1 $T/out.csv)
echo "$L" | grep -q ',100,' || { echo "FAIL: mah"; echo "$L"; exit 1; }       # 100 mAh used
echo "$L" | grep -q ',2,300,' || { echo "FAIL: apss delta"; echo "$L"; exit 1; }
echo "$L" | grep -q ',1,wifi$' || { echo "FAIL: s1/exp"; echo "$L"; exit 1; }
head -1 $T/out.csv | grep -q '^start,secs,mah,avg_ma' || { echo "FAIL: header"; exit 1; }
echo OK
