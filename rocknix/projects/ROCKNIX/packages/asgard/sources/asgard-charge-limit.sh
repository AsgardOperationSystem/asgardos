#!/bin/sh
# Charge limit: asgard.charge_limit in system.cfg (%, default 80; 100 = off; "full" = hold at 100 %). The Thor's charger firmware ignores
# charge_control_end_threshold, but it takes a charge current (Kettle 1190, kernel patch 9020). At the limit the
# current goes to 0: the charger keeps powering the Thor and the battery sits idle. 5 % below it, the current comes
# back (Kettle's kettle-powerd does the same). Asleep this loop is frozen: a battery below the limit when it sleeps
# on the charger charges on to full (as on Kettle).
# Bypass charging (asgard.bypass_charging=1): current 0 at any level, so on the cable the charger runs the Thor and
# the battery is left alone; below BYPASS_FLOOR % it charges, since a load the charger can't cover drains it.
B=${BAT:-/sys/class/power_supply/battery}
C=$B/constant_charge_current
CFG=${CFG:-/storage/.config/system/configs/system.cfg}
# qcom_battmgr is a module and registers the supply seconds after this starts at boot: wait for it
while [ ! -w $C ]; do sleep 5; done
held=0
while :; do
  limit=$(sed -n 's/^asgard\.charge_limit=//p' $CFG | tail -1)
  limit=${limit:-80}
  hold_full=0; [ "$limit" = full ] && { limit=100; hold_full=1; }   # 100 alone stays "off" (older configs)
  bypass=$(sed -n 's/^asgard\.bypass_charging=//p' $CFG | tail -1)
  level=$(cat $B/capacity)
  if [ "$limit" -ge 100 ] && [ $hold_full = 0 ]; then held=0
  elif [ "$level" -ge "$limit" ]; then held=1
  elif [ "$level" -le $((limit - 5)) ]; then held=0
  fi
  if [ $held = 1 ] || { [ "$bypass" = 1 ] && [ "$level" -gt "${BYPASS_FLOOR:-20}" ]; }; then want=0; else want=$(cat ${C}_max); fi
  # read back rather than trust the last write: a firmware restart resets it
  [ "$(cat $C)" = "$want" ] || echo "$want" > $C
  sleep ${INTERVAL:-10}
done
