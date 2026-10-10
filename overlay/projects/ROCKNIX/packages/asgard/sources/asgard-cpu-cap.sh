#!/bin/bash
# CPU clock cap per core type, in percent of each cluster's top clock (25-100): battery and a cooler shell.
#   asgard.cpu_cap.little  3x Cortex-A510 (policy0)        default 90
#   asgard.cpu_cap.mid     2x A715 + 2x A710 (policy3)     default 75
#   asgard.cpu_cap.prime   1x Cortex-X3 (policy7)          default 75
# The older on/off asgard.cpu_cap=0 means no cap (100 for all). The highest frequency the cluster supports at or
# under the cap is set as scaling_max_freq. Run at boot (090-asgard-tuning) and from Settings.
. /etc/profile.d/001-functions
OLD=$(get_setting asgard.cpu_cap)
for c in little:0:90 mid:3:75 prime:7:75; do
  IFS=: read -r name policy dflt <<< "$c"
  P=/sys/devices/system/cpu/cpufreq/policy$policy
  [ -d "$P" ] || continue
  [ "$OLD" = "0" ] && dflt=100
  pct=$(get_setting "asgard.cpu_cap.$name")
  pct=${pct:-$dflt}
  [ "$pct" -ge 25 ] 2>/dev/null || pct=25
  [ "$pct" -le 100 ] || pct=100
  top=$(cat $P/cpuinfo_max_freq)
  want=$((top * pct / 100))
  khz=$(tr ' ' '\n' < $P/scaling_available_frequencies | awk -v w="$want" '$1 && $1 <= w && $1 > best {best = $1} END {print best}')
  [ -n "$khz" ] || khz=$(cat $P/cpuinfo_min_freq)
  echo "$khz" > $P/scaling_max_freq
done
