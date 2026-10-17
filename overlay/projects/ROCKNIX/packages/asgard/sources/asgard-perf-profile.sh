#!/bin/bash
# Per-system / per-game profile, from the emulator options (thor_settings.py adds them to every emulator); unset ones
# keep the global values (Settings > Hardware > Performance, asgard-cpu-cap.sh):
#   cpu_cap_<type>     clock cap, % of the cluster's top clock (25-100)      type: little | mid | prime
#   cpu_cores_<type>   "on" / "off": that cluster's cores (at least one type stays on; CPU0 always does)
#   fan_mode           as Settings > Performance > Fan: quiet|moderate|aggressive, or a fixed 0-255 speed
#   sleep_mode         "screen": the lid and the power key turn the screens off and keep the game running (music on
#                      the headphone jack) instead of suspending: asgard-screens-off.sh, with a sleep inhibitor held
#                      meanwhile; sleep_wifi / sleep_bt "off" also take those radios down while the screens are off
# runemu.sh calls "apply <platform> <rom file>" before the emulator and "restore" after it; restore re-runs
# asgard-cpu-cap.sh (all cores online, then the global settings) and puts the fan back.
#   asgard-perf-profile.sh apply|restore [platform rom]
#   asgard-perf-profile.sh cpu <platform> <rom>   only the caps and cores (asgard-screens-off.sh, screens back on)
. /etc/profile.d/001-functions
. /usr/share/asgard/asgard-cpu-lib.sh
SAVED=/run/asgard-perf.saved    # present while a profile is applied; .fan holds the fan settings to restore
KEEP=/run/asgard-keep-running   # "<platform>\t<rom>" while sleep_mode=screen; power-handler checks it

# system.cfg key=value; an empty value removes the key (set_setting "" leaves the old line, which still wins).
setkey() { local cfg=/storage/.config/system/configs/system.cfg; sed -i "/^${1//./\\.}=/d" $cfg; [ -n "$2" ] && echo "$1=$2" >> $cfg; }

# The game's caps and cores over the global ones; prints "set" if it changed anything.
cpu() {
  local platform=$1 game=$2 t pct cores off=""
  for t in $TYPES; do
    pct=$(get_setting "cpu_cap_$t" "$platform" "$game")
    cores=$(get_setting "cpu_cores_$t" "$platform" "$game")
    [ -n "$pct$cores" ] && echo set
    [ "$cores" = on ] && online_type "$t" 1
    [ -n "$pct" ] && set_cap "$t" "$pct"
    { [ "$cores" = off ] || { [ -z "$cores" ] && [ "$(get_setting "asgard.cpu_cores.$t")" = off ]; }; } && off="$off $t"
  done
  offline_types "$off"
  write_affinity
}

apply() {
  local platform=$1 game=$2 changed fan
  [ -f "$SAVED" ] && restore   # a profile left over from a game that didn't get to restore (crash, kill -9)
  changed=$(cpu "$platform" "$game")
  if [ "$(get_setting sleep_mode "$platform" "$game")" = screen ]; then
    printf '%s\t%s\n' "$platform" "$game" > $KEEP
    setsid systemd-inhibit --what=sleep:handle-lid-switch --who=Asgard --why="screens off, keep running" \
      --mode=block sleep infinity >/dev/null 2>&1 &
    echo $! > $KEEP.pid
    changed=set
  fi
  fan=$(get_setting fan_mode "$platform" "$game")
  if [ -n "$fan" ]; then
    printf 'fan_manual=%s\ncooling_profile=%s\n' "$(get_setting asgard.fan_manual)" "$(get_setting cooling.profile)" > $SAVED.fan
    if [[ "$fan" =~ ^[0-9]+$ ]]; then setkey asgard.fan_manual "$fan"
    else setkey asgard.fan_manual ""; setkey cooling.profile "$fan"; fi
    systemctl restart fancontrol
    changed=set
  fi
  [ -n "$changed" ] && touch $SAVED
}

restore() {
  [ -f "$SAVED" ] || return 0
  if [ -f $KEEP ]; then
    /usr/share/asgard/asgard-screens-off.sh lid open   # screens, radios and lights back first
    kill "$(cat $KEEP.pid 2>/dev/null)" 2>/dev/null
    rm -f $KEEP $KEEP.pid
  fi
  /usr/share/asgard/asgard-cpu-cap.sh
  if [ -f $SAVED.fan ]; then
    setkey asgard.fan_manual "$(sed -n 's/^fan_manual=//p' $SAVED.fan)"
    local profile; profile=$(sed -n 's/^cooling_profile=//p' $SAVED.fan)
    [ -n "$profile" ] && setkey cooling.profile "$profile"
    systemctl restart fancontrol
    rm -f $SAVED.fan
  fi
  rm -f $SAVED
}

case "$1" in
  apply) apply "$2" "$3" ;;
  restore) restore ;;
  cpu) cpu "$2" "$3" >/dev/null ;;
esac
