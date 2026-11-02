#!/bin/sh
# spec: LOG-4
# Fake-sysfs check for sleep.d/asgard-sleep-audit: one CSV line per sleep with the right deltas.
set -e
T=$(mktemp -d); trap 'rm -rf $T' EXIT
H=$(dirname "$(readlink -f "$0")")/../sleep.d/asgard-sleep-audit
B=$T/class/power_supply/battery; Q=$T/kernel/debug/qcom_stats; C=$T/kernel/debug/pm_genpd/power-domain-cluster
mkdir -p $B $Q $C
mkdir -p $T/class/rfkill/rfkill0 $T/class/rfkill/rfkill1
echo wlan > $T/class/rfkill/rfkill0/type; echo 0 > $T/class/rfkill/rfkill0/soft
echo bluetooth > $T/class/rfkill/rfkill1/type; echo 0 > $T/class/rfkill/rfkill1/soft
state() {  # charge_uah apss_count apss_acc s1_s2idle_count [ddr ticks at 547 1555 4224]
  echo $1 > $B/charge_counter; echo 4000000 > $B/voltage_now; echo $(($1 / 1000 + 3000000)) > $B/voltage_ocv
  printf 'DDR LPM Stat Name:0xd0\tcount:1\tDuration (ticks):5\n' > $Q/ddr_stats
  for f in "547 ${5:-0}" "1555 ${6:-0}" "4224 ${7:-0}"; do
    printf 'DDR Freq %sMhz:\tCP IDX:1\tcount:1\tDuration (ticks):%s\n' ${f% *} ${f#* } >> $Q/ddr_stats; done
  printf 'Count: %s\nLast Entered At: 0\nLast Exited At: 0\nAccumulated Duration: %s\n' $2 $3 > $Q/apss
  printf 'State Time(ms) Usage Rejected Above Below S2idle\nS0 0 0 0 0 0 0\nS1 513 2 0 0 0 %s\n' $4 > $C/idle_states
}
mkdir -p $T/proc; P=$T/proc/interrupts
irqs() {  # ipcc count, uart count
  printf '           CPU0       CPU1\n 13:  %s  1  GICv3  261 Level  ipcc_0\n186:  %s  0  GICv3  494 Level  qcom_geni_serial_uart2\nIPI0:  7  7  Rescheduling interrupts\n' $1 $2 > $P
  printf 'name\t\tactive_count\tevent_count\twakeup_count\nalarmtimer\t\t3\t\t%s\t\t0\n' $1 > $T/kernel/debug/wakeup_sources
}
run() { PROC=$T/proc TR=$T/tr SYS=$T OUT=$T/out.csv CFG=$T/cfg SNAP=$T/snap DUMPS=$T/dumps PLAYING=$T/playing sh "$H" $1; }
printf 'asgard.sleep_audit=0\n' > $T/cfg
state 5000000 10 100 99; run pre; run post
[ ! -e $T/out.csv ] || { echo "FAIL: logged while off"; exit 1; }
printf 'asgard.sleep_audit=0\nasgard.sleep_audit=1\nasgard.sleep_experiment=wifi\n' > $T/cfg
echo 'start,old,header' > $T/out.csv                                         # an old-format log is rotated
printf '3ds|azahar||100|Zelda "OoT" | 3D\n' > $T/playing
state 5000000 10 100 99 0 1000 0; irqs 100 50; run pre
state 4900000 12 400 100 50 1100 900; irqs 218 50; run post
[ "$(wc -l < $T/out.csv)" = 2 ] || { echo "FAIL: lines"; cat $T/out.csv; exit 1; }
L=$(tail -1 $T/out.csv)
echo "$L" | grep -q ',100,' || { echo "FAIL: mah"; echo "$L"; exit 1; }       # 100 mAh used
echo "$L" | grep -q ',4000000,4000000,3005000,3004900,' || { echo "FAIL: uv/ocv"; echo "$L"; exit 1; }
echo "$L" | grep -q ',2,300,' || { echo "FAIL: apss delta"; echo "$L"; exit 1; }
echo "$L" | grep -q ',1,wifi,4224,85,azahar,"Zelda ""OoT"" | 3D"$' || { echo "FAIL: s1/exp/ddr/game"; echo "$L"; exit 1; }
[ "$(cat $T/out.csv.1)" = start,old,header ] || { echo "FAIL: rotate"; exit 1; }
ls $T/dumps/*.txt >/dev/null || { echo "FAIL: dump"; exit 1; }
ls $T/dumps/*.trace >/dev/null || { echo "FAIL: trace"; exit 1; }
I=$(ls $T/dumps/*.irq)
grep -qx "$(printf "118\tirq 13: GICv3 261 Level ipcc_0")" $I || { echo "FAIL: irq delta"; cat $I; exit 1; }
grep -q "$(printf '^118\tws alarmtimer$')" $I || { echo "FAIL: ws delta"; cat $I; exit 1; }
! grep -q uart2 $I || { echo "FAIL: unchanged irq listed"; cat $I; exit 1; }
[ "$(cat $T/tr/tracing_on)" = 0 ] || { echo "FAIL: trace left on"; exit 1; }
# alt:wifi: on every other sleep
printf 'asgard.sleep_audit=1\nasgard.sleep_experiment=alt:wifi\n' > $T/cfg; rm $T/playing
for i in 1 2; do state 5000000 10 100 99; run pre; state 4900000 12 400 100; run post; done
[ "$(tail -2 $T/out.csv | cut -d, -f22 | sort | tr '\n' ' ')" = " wifi " ] || { echo "FAIL: alt"; tail -2 $T/out.csv; exit 1; }
head -1 $T/out.csv | grep -q '^start,secs,mah,avg_ma' || { echo "FAIL: header"; exit 1; }
# A radio that's already off (airplane mode, Wi-Fi toggle) isn't part of the experiment: never unblocked after.
echo 1 > $T/class/rfkill/rfkill0/soft
printf 'asgard.sleep_audit=1\nasgard.sleep_experiment=wifi bt\n' > $T/cfg
state 5000000 10 100 99; run pre; state 4900000 12 400 100; run post
[ "$(tail -1 $T/out.csv | cut -d, -f22)" = bt ] || { echo "FAIL: blocked radio in exp"; tail -1 $T/out.csv; exit 1; }
echo OK
