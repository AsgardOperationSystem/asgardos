#!/bin/bash
# Per-system / per-game profile, from the emulator options (thor_settings.py adds them to every emulator). Games start
# at stock (every core on, full clocks) whatever the Asgard menu's own profile is (Settings > Hardware > Performance,
# asgard-cpu-cap.sh, only while in Home), then these override it:
#   cpu_cap_<type>     clock cap, % of the cluster's top clock (25-100)      type: little | mid | prime
#   cpu_cores_<type>   "on" / "off": that cluster's cores (at least one type stays on; CPU0 always does)
#   fan_mode           as Settings > Performance > Fan: quiet|moderate|aggressive, or a fixed 0-255 speed
#   motion             "on": the gyro (asgard-motiond, a DSU server) while the game runs; unset/"off" = stopped.
#                      Outside games the menu's asgard.motion=1 (Settings > Hardware > Performance > Gyro) decides.
#   eq_speaker         thor|joey|off, eq_headphones thor|autoeq|off: the sound EQ while the game runs (asgard-eq.py
#                      game); unset = Settings > Hardware > Audio's. PipeWire restarts (~2 s) only if that changes it.
#   sleep_mode         "screen": the lid and the power key turn the screens off and keep the game running (music on
#                      the headphone jack) instead of suspending: asgard-screens-off.sh, with a sleep inhibitor held
#                      meanwhile; sleep_wifi / sleep_bt "off" also take those radios down while the screens are off
# runemu.sh calls "apply <platform> <rom file>" before the emulator and "restore" after it; restore re-runs
# asgard-cpu-cap.sh (the menu's profile again) and puts the fan back.
#   asgard-perf-profile.sh apply|restore [platform rom]
#   asgard-perf-profile.sh cpu <platform> <rom>   only the caps and cores (asgard-screens-off.sh, screens back on)
#   asgard-perf-profile.sh motion [platform rom]   only the gyro: the game's, or without one the menu's (boot, Settings)
. /etc/profile.d/001-functions
. /usr/share/asgard/asgard-cpu-lib.sh
SAVED=/run/asgard-perf.saved    # present while a profile is applied; .fan holds the fan settings to restore
KEEP=/run/asgard-keep-running   # "<platform>\t<rom>" while sleep_mode=screen; power-handler checks it

# system.cfg key=value; an empty value removes the key (set_setting "" leaves the old line, which still wins).
setkey() { local cfg=/storage/.config/system/configs/system.cfg; sed -i "/^${1//./\\.}=/d" $cfg; [ -n "$2" ] && echo "$1=$2" >> $cfg; }

# Stock, then the game's caps and cores.
cpu() {
  local platform=$1 game=$2 t pct off=""
  for t in $TYPES; do online_type "$t" 1; done
  for t in $TYPES; do
    pct=$(get_setting "cpu_cap_$t" "$platform" "$game")
    set_cap "$t" "${pct:-100}"
    [ "$(get_setting "cpu_cores_$t" "$platform" "$game")" = off ] && off="$off $t"
  done
  offline_types "$off"
  write_affinity
}

# The gyro streams only when asked for: while asgard-motiond runs the ADSP wakes ~185 times a second (~10 without).
motion() {
  local on
  if [ -n "$1" ]; then on=$(get_setting motion "$1" "$2"); else on=$(get_setting asgard.motion); fi
  if [ "$on" = on ] || [ "$on" = 1 ]; then systemctl start asgard-motiond; else systemctl stop asgard-motiond; fi
}

eq() { python3 /usr/share/asgard/asgard-eq.py game "${1:-default}" "${2:-default}" >/dev/null; }

apply() {
  local platform=$1 game=$2 fan
  [ -f "$SAVED" ] && restore   # a profile left over from a game that didn't get to restore (crash, kill -9)
  cpu "$platform" "$game"   # always: the menu's profile may have cores off or capped
  motion "$platform" "$game"   # before the emulator starts: start_azahar.sh picks its motion source by it
  eq "$(get_setting eq_speaker "$platform" "$game")" "$(get_setting eq_headphones "$platform" "$game")"
  touch $SAVED
  if [ "$(get_setting sleep_mode "$platform" "$game")" = screen ]; then
    printf '%s\t%s\n' "$platform" "$game" > $KEEP
    setsid systemd-inhibit --what=sleep:handle-lid-switch --who=Asgard --why="screens off, keep running" \
      --mode=block sleep infinity >/dev/null 2>&1 &
    echo $! > $KEEP.pid
  fi
  fan=$(get_setting fan_mode "$platform" "$game")
  if [ -n "$fan" ]; then
    printf 'fan_manual=%s\ncooling_profile=%s\n' "$(get_setting asgard.fan_manual)" "$(get_setting cooling.profile)" > $SAVED.fan
    if [[ "$fan" =~ ^[0-9]+$ ]]; then setkey asgard.fan_manual "$fan"
    else setkey asgard.fan_manual ""; setkey cooling.profile "$fan"; fi
    systemctl restart fancontrol
  fi
}

restore() {
  [ -f "$SAVED" ] || return 0
  if [ -f $KEEP ]; then
    /usr/share/asgard/asgard-screens-off.sh lid open   # screens, radios and lights back first
    kill "$(cat $KEEP.pid 2>/dev/null)" 2>/dev/null
    rm -f $KEEP $KEEP.pid
  fi
  /usr/share/asgard/asgard-cpu-cap.sh
  motion
  eq "" ""
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
  cpu) cpu "$2" "$3" ;;
  motion) motion "$2" "$3" ;;
esac
