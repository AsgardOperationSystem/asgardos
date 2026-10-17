#!/bin/bash
# Per-system / per-game performance profile, from the emulator options (thor_settings.py adds them to every emulator):
#   cpu_cap_little|mid|prime     clock cap, % of the cluster's top clock (25-100); unset = the global caps
#   cpu_cores_little|mid|prime   "off" takes the cluster's cores offline (CPU0 stays: the kernel can't offline it)
#   fan_mode                     as Settings > Performance > Fan: quiet|moderate|aggressive, or a fixed 0-255 speed
# runemu.sh calls "apply <platform> <rom file>" before the emulator and "restore" after it. apply saves what it changes
# in $SAVED; restore brings every core back online, re-runs asgard-cpu-cap.sh (the global caps) and puts the fan back.
#   asgard-perf-profile.sh apply|restore [platform rom]
. /etc/profile.d/001-functions
SAVED=/run/asgard-perf.saved
CPU=/sys/devices/system/cpu
CLUSTERS="little:0:1-2 mid:3:3-6 prime:7:7"   # name:cpufreq policy:CPUs that can go offline

cpus() { local a=${1%-*} b=${1#*-}; seq "$a" "$b"; }
# system.cfg key=value; an empty value removes the key (set_setting "" leaves the old line, which still wins).
setkey() { local cfg=/storage/.config/system/configs/system.cfg; sed -i "/^${1//./\\.}=/d" $cfg; [ -n "$2" ] && echo "$1=$2" >> $cfg; }

apply() {
  local platform=$1 game=$2 changed=0
  [ -f "$SAVED" ] && restore   # a profile left over from a game that didn't get to restore (crash, kill -9)
  for c in $CLUSTERS; do
    IFS=: read -r name policy offline <<< "$c"
    pct=$(get_setting "cpu_cap_$name" "$platform" "$game")
    P=$CPU/cpufreq/policy$policy
    if [ -n "$pct" ] && [ -d "$P" ]; then
      [ "$pct" -ge 25 ] 2>/dev/null || pct=25
      [ "$pct" -le 100 ] || pct=100
      want=$(( $(cat $P/cpuinfo_max_freq) * pct / 100 ))
      khz=$(tr ' ' '\n' < $P/scaling_available_frequencies | awk -v w="$want" '$1 && $1 <= w && $1 > b {b = $1} END {print b}')
      echo "${khz:-$(cat $P/cpuinfo_min_freq)}" > $P/scaling_max_freq
      changed=1
    fi
  done
  # Cores last: a cluster's policy directory goes away with its cores. Never mid and prime together, or the
  # emulator would be left on the A510s alone (and big-core taskset masks with no online CPU): prime stays.
  local mid_off prime_off
  mid_off=$(get_setting cpu_cores_mid "$platform" "$game"); prime_off=$(get_setting cpu_cores_prime "$platform" "$game")
  for c in $CLUSTERS; do
    IFS=: read -r name policy offline <<< "$c"
    [ "$(get_setting "cpu_cores_$name" "$platform" "$game")" = off ] || continue
    [ "$name" = prime ] && [ "$mid_off" = off ] && continue
    for n in $(cpus "$offline"); do echo 0 > $CPU/cpu$n/online; done
    changed=1
  done
  fan=$(get_setting fan_mode "$platform" "$game")
  if [ -n "$fan" ]; then
    printf 'fan_manual=%s\ncooling_profile=%s\n' "$(get_setting asgard.fan_manual)" "$(get_setting cooling.profile)" >> $SAVED.fan
    if [[ "$fan" =~ ^[0-9]+$ ]]; then setkey asgard.fan_manual "$fan"
    else setkey asgard.fan_manual ""; setkey cooling.profile "$fan"; fi
    systemctl restart fancontrol
    changed=1
  fi
  [ $changed = 1 ] && touch $SAVED
}

restore() {
  [ -f "$SAVED" ] || return 0
  for c in $CLUSTERS; do
    IFS=: read -r name policy offline <<< "$c"
    for n in $(cpus "$offline"); do echo 1 > $CPU/cpu$n/online; done
  done
  /usr/share/asgard/asgard-cpu-cap.sh
  if [ -f $SAVED.fan ]; then
    fan_manual=$(sed -n 's/^fan_manual=//p' $SAVED.fan | head -1)
    cooling_profile=$(sed -n 's/^cooling_profile=//p' $SAVED.fan | head -1)
    setkey asgard.fan_manual "$fan_manual"
    [ -n "$cooling_profile" ] && setkey cooling.profile "$cooling_profile"
    systemctl restart fancontrol
    rm -f $SAVED.fan
  fi
  rm -f $SAVED
}

case "$1" in
  apply) apply "$2" "$3" ;;
  restore) restore ;;
esac
