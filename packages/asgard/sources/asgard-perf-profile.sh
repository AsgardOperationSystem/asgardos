#!/bin/bash
# Per-system / per-game profile, from the emulator options (thor_settings.py adds them to every emulator). Games start
# at stock (every core on, full clocks) whatever the Asgard menu's own profile is (Settings > Hardware > Performance,
# asgard-cpu-cap.sh, only while in Home), then these override it:
#   cpu_cap_<type>     clock cap, % of the cluster's top clock (25-100), "off": that cluster's cores offline
#                      (at least one type stays on; CPU0 always does), or "autotune": asgard-autotune.py holds it at
#                      the lowest clock that keeps the game's FPS          type: little | mid | prime
#   gpu_cap            the GPU's clock cap, % of its top clock (25-100), or "autotune"; unset = uncapped. Home has
#                      its own, asgard.gpu_cap (asgard-cpu-cap.sh).
#   fan_mode           as Settings > Performance > Fan: quiet|moderate|aggressive, or a fixed 0-255 speed
#   motion             "on": the gyro (asgard-motiond, a DSU server) while the game runs; unset/"off" = stopped.
#                      Outside games the menu's asgard.motion=1 (Settings > Hardware > Performance > Gyro) decides.
#   eq_speaker         thor|joey|off, eq_headphones thor|autoeq|off: the sound EQ while the game runs (asgard-eq.py
#                      game); unset = Settings > Hardware > Audio's. PipeWire restarts (~2 s) only if that changes it.
#   top_* / bottom_*   each screen's refresh, brightness, warmth, tint and contrast, and the top's ultra_black, while the
#                      game runs: screens(). Unset = Settings > Hardware > Display's, which they never change.
#   sleep_mode         "screen": the lid and the power key turn the screens off and keep the game running (music on
#                      the headphone jack) instead of suspending: asgard-screens-off.sh, with a sleep inhibitor held
#                      meanwhile; sleep_wifi / sleep_bt "off" also take those radios down while the screens are off
# runemu.sh calls "apply <platform> <rom file>" before the emulator and "restore" after it; restore re-runs
# asgard-cpu-cap.sh (the menu's profile again) and puts the fan back.
#   asgard-perf-profile.sh apply|restore [platform rom]
#   asgard-perf-profile.sh cpu <platform> <rom>   only the caps and cores (asgard-screens-off.sh, screens back on)
#   asgard-perf-profile.sh motion [platform rom]   only the gyro: the game's, or without one the menu's (boot, Settings)
#   asgard-perf-profile.sh screens <platform> <rom>   only the screens (the in-game menu); no game: Settings' values
#   asgard-perf-profile.sh home           Back to Home: the menu's caps, cores, fan and screens while the game waits frozen
#   asgard-perf-profile.sh game <platform> <rom>   Return to the game: its caps, cores, fan and screens again
. /etc/profile.d/001-functions
. /usr/share/asgard/asgard-cpu-lib.sh
SAVED=/run/asgard-perf.saved    # present while a profile is applied; .fan holds the fan settings to restore
KEEP=/run/asgard-keep-running   # "<platform>\t<rom>" while sleep_mode=screen; power-handler checks it
IN_HOME=/run/asgard-perf.home   # present while a game waits in the background and Home has the menu's profile
OVERRIDE=/run/asgard-screen-override.cfg   # what the game overrides, under Settings' keys; asgard-gamma reads it too
# <the game's key> <Settings' key> <its default>
SCREEN_KEYS="top_refresh asgard.refresh 120
top_brightness display.brightness2 50
top_warmth asgard.warmth.top 0
top_tint asgard.tint.top 0
top_contrast asgard.contrast.top 0
top_ultra_black asgard.ultra_black 1
bottom_refresh asgard.refresh_bottom 60
bottom_brightness display.brightness 50
bottom_warmth asgard.warmth.bottom 0
bottom_tint asgard.tint.bottom 3
bottom_contrast asgard.contrast.bottom 3"

# system.cfg key=value; an empty value removes the key (set_setting "" leaves the old line, which still wins).
setkey() { local cfg=/storage/.config/system/configs/system.cfg; sed -i "/^${1//./\\.}=/d" $cfg; [ -n "$2" ] && echo "$1=$2" >> $cfg; }

# Stock, then the game's caps (CPU and GPU) and cores, and autotune for those set to it.
cpu() {
  local platform=$1 game=$2 t pct off="" auto=""
  autotune_stop
  for t in $TYPES; do online_type "$t" 1; done
  for t in $TYPES; do
    pct=$(get_setting "cpu_cap_$t" "$platform" "$game")
    case "$pct" in
      off) off="$off $t" ;;
      autotune) auto="$auto $t"; set_cap "$t" 100 ;;
      *) set_cap "$t" "${pct:-100}" ;;
    esac
  done
  pct=$(get_setting gpu_cap "$platform" "$game")
  [ "$pct" = autotune ] && { auto="$auto gpu"; pct=100; }
  set_gpu_cap "${pct:-100}"
  offline_types "$off"
  write_affinity
  [ -n "$auto" ] && autotune_start $auto
}

# The gyro streams only when asked for: while asgard-motiond runs the ADSP wakes ~185 times a second (~10 without).
motion() {
  local on
  if [ -n "$1" ]; then on=$(get_setting motion "$1" "$2"); else on=$(get_setting asgard.motion); fi
  if [ "$on" = on ] || [ "$on" = 1 ]; then systemctl start asgard-motiond; else systemctl stop asgard-motiond; fi
}

# Each screen setting to the game's value, else Settings'. Only what changes is touched, so a game with no overrides
# doesn't blink, and an override is never written to Settings' keys: they come back by themselves.
screens() {
  local platform=$1 game=$2 key os dflt value target was gamma="" ultra="" new=$OVERRIDE.new
  export SWAYSOCK=${SWAYSOCK:-$(ls /run/0-runtime-dir/sway-ipc.* 2>/dev/null | head -1)}
  : > "$new"
  while read -r key os dflt; do
    value=$(get_setting "$key" "$platform" "$game")
    target=$value
    [ -n "$target" ] || target=$(get_setting "$os")
    [ -n "$target" ] || target=$dflt
    was=$(sed -n "s/^$os=//p" $OVERRIDE 2>/dev/null | tail -1)
    [ -n "$was" ] || was=$(get_setting "$os")
    [ -n "$was" ] || was=$dflt
    [ -n "$value" ] && echo "$os=$value" >> "$new"
    [ "$target" = "$was" ] && continue
    case "$key" in
      top_refresh) swaymsg output DSI-2 mode "1080x1920@${target}Hz" >/dev/null ;;
      bottom_refresh) swaymsg output DSI-1 mode "1080x1240@${target}Hz" >/dev/null ;;
      top_brightness) brightness apply 2 "$target" ;;      # ROCKNIX's numbering: 2 is the top
      bottom_brightness) brightness apply 1 "$target" ;;
      top_ultra_black) ultra=$target ;;
      *) gamma=1 ;;
    esac
  done <<< "$SCREEN_KEYS"
  if [ -s "$new" ]; then mv "$new" $OVERRIDE; else rm -f "$new" $OVERRIDE; fi
  if [ -n "$ultra" ]; then
    # Sent at each panel power-on, so the top screen has to cycle. With the screens off the next power-on sends it.
    [ "$ultra" = 0 ] && ultra=N || ultra=Y
    echo $ultra > /sys/module/panel_chipone_icna35xx/parameters/ultra_black 2>/dev/null
    if [ ! -e /run/asgard-screens-off.active ]; then
      swaymsg output DSI-2 power off >/dev/null; sleep 0.5; swaymsg output DSI-2 power on >/dev/null
      gamma=1   # a power cycle drops the ramp
    fi
  fi
  [ -n "$gamma" ] && kill -HUP $(pidof asgard-gamma) 2>/dev/null
  return 0
}

eq() { python3 /usr/share/asgard/asgard-eq.py game "${1:-default}" "${2:-default}" >/dev/null; }

apply() {
  local platform=$1 game=$2 fan
  [ -f "$SAVED" ] && restore   # a profile left over from a game that didn't get to restore (crash, kill -9)
  cpu "$platform" "$game"   # always: the menu's profile may have cores off or capped
  motion "$platform" "$game"   # before the emulator starts: start_azahar.sh picks its motion source by it
  eq "$(get_setting eq_speaker "$platform" "$game")" "$(get_setting eq_headphones "$platform" "$game")"
  screens "$platform" "$game"
  touch $SAVED
  if [ "$(get_setting sleep_mode "$platform" "$game")" = screen ]; then
    printf '%s\t%s\n' "$platform" "$game" > $KEEP
    setsid systemd-inhibit --what=sleep:handle-lid-switch --who=Asgard --why="screens off, keep running" \
      --mode=block sleep infinity >/dev/null 2>&1 &
    echo $! > $KEEP.pid
  fi
  fan_apply "$platform" "$game"
}

fan_apply() {
  local fan
  fan=$(get_setting fan_mode "$1" "$2")
  if [ -n "$fan" ]; then
    printf 'fan_manual=%s\ncooling_profile=%s\n' "$(get_setting asgard.fan_manual)" "$(get_setting cooling.profile)" > $SAVED.fan
    if [[ "$fan" =~ ^[0-9]+$ ]]; then setkey asgard.fan_manual "$fan"
    else setkey asgard.fan_manual ""; setkey cooling.profile "$fan"; fi
    systemctl restart fancontrol
  fi
}

fan_restore() {
  if [ -f $SAVED.fan ]; then
    setkey asgard.fan_manual "$(sed -n 's/^fan_manual=//p' $SAVED.fan)"
    local profile; profile=$(sed -n 's/^cooling_profile=//p' $SAVED.fan)
    [ -n "$profile" ] && setkey cooling.profile "$profile"
    systemctl restart fancontrol
    rm -f $SAVED.fan
  fi
}

# Back to Home and back. Only with a game's profile on: one that ended meanwhile has had its restore. The gyro and EQ
# stay the game's: the EQ restarts PipeWire, and an emulator picks its motion source at launch.
# One at a time, so quickly going back and forth ends on the last one asked for; what they leave running (autotune)
# doesn't get the lock.
home() {
  [ -f "$SAVED" ] || return 0
  touch $IN_HOME
  /usr/share/asgard/asgard-cpu-cap.sh 9>&-
  fan_restore
  screens "" ""
}

game() {
  [ -f "$SAVED" ] || return 0
  rm -f $IN_HOME
  cpu "$1" "$2" 9>&-
  [ -f $SAVED.fan ] || fan_apply "$1" "$2"
  screens "$1" "$2"
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
  fan_restore
  screens "" ""
  rm -f $SAVED $IN_HOME
}

case "$1" in
  apply) apply "$2" "$3" ;;
  restore) restore ;;
  cpu) cpu "$2" "$3" ;;
  motion) motion "$2" "$3" ;;
  screens) screens "$2" "$3" ;;
  home|game)
    exec 9>/run/asgard-perf.lock
    timeout 30 flock 9 || true
    "$1" "$2" "$3"
    ;;
esac
