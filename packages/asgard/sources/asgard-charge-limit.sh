#!/bin/sh
# Charge limit: asgard.charge_limit in system.cfg (%, default 80; 100 = off; "full" = hold at 100 %). The Thor's charger firmware ignores
# charge_control_end_threshold, but it takes a charge current (Kettle 1190, kernel patch 9020). At the limit the
# current goes to 0: the charger keeps powering the Thor and the battery sits idle. 5 % below it, the current comes
# back (Kettle's kettle-powerd does the same). Asleep this loop is frozen: a battery below the limit when it sleeps
# on the charger charges on to full (as on Kettle).
# Bypass charging (asgard.bypass_charging=1): current 0 at any level, so on the cable the charger runs the Thor and
# the battery is left alone; below BYPASS_FLOOR % it charges, since a load the charger can't cover drains it.
# Recalibration: under a limit the gauge never sees a full charge, and its charge_full climbs (Thor, 2026-11: 6680 mAh
# after a full charge on 11-05, 7091 by 11-13, about 50 mAh a day), so the limit's percentage holds more and more
# charge (78 % was about 84 % of the 11-05 full) and the shown level reads low. A full charge re-anchors it. So when
# charge_full has risen RECAL_DRIFT % above its value at the last 100 % (ANCHOR; none yet counts as drifted), the next
# charge goes to 100 % once; the limit applies again from there. RECAL_FLAG says so while it's on, for Settings.
B=${BAT:-/sys/class/power_supply/battery}
C=$B/constant_charge_current
CFG=${CFG:-/storage/.config/system/configs/system.cfg}
ANCHOR=${ANCHOR:-/storage/.config/asgard/charge-anchor}
RECAL_FLAG=${RECAL_FLAG:-/run/asgard-charge-recal}
# qcom_battmgr is a module and registers the supply seconds after this starts at boot: wait for it
while [ ! -w $C ]; do sleep 5; done
held=0
while :; do
  limit=$(sed -n 's/^asgard\.charge_limit=//p' $CFG | tail -1)
  limit=${limit:-80}
  hold_full=0; [ "$limit" = full ] && { limit=100; hold_full=1; }   # 100 alone stays "off" (older configs)
  bypass=$(sed -n 's/^asgard\.bypass_charging=//p' $CFG | tail -1)
  level=$(cat $B/capacity)
  full=$(cat $B/charge_full 2>/dev/null)
  if [ -n "$full" ]; then
    # at 100 % the gauge has its anchor: remember it (the value settles while it sits there)
    [ "$level" -ge 100 ] && { mkdir -p "$(dirname "$ANCHOR")"; echo "$full" > "$ANCHOR"; }
    anchor=$(cat "$ANCHOR" 2>/dev/null)
    case "$anchor" in *[!0-9]*) anchor="" ;; esac     # unreadable counts as none: recalibrate
    if [ "$limit" -lt 100 ] && [ "$bypass" != 1 ] && { [ -z "$anchor" ] || [ $((full * 100)) -ge $((anchor * (100 + ${RECAL_DRIFT:-5}))) ]; }; then
      [ -e "$RECAL_FLAG" ] || echo "$anchor $full" > "$RECAL_FLAG"
      limit=100; hold_full=1               # this charge goes to 100 %; reaching it re-anchors, and the limit is back
    else
      rm -f "$RECAL_FLAG"
    fi
  fi
  if [ "$limit" -ge 100 ] && [ $hold_full = 0 ]; then held=0
  elif [ "$level" -ge "$limit" ]; then held=1
  elif [ "$level" -le $((limit - 5)) ]; then held=0
  fi
  if [ $held = 1 ] || { [ "$bypass" = 1 ] && [ "$level" -ge "${BYPASS_FLOOR:-20}" ]; }; then want=0; else want=$(cat ${C}_max); fi
  # read back rather than trust the last write: a firmware restart resets it
  [ "$(cat $C)" = "$want" ] || echo "$want" > $C
  sleep ${INTERVAL:-10}
done
