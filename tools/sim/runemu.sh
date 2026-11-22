#!/bin/bash
# The simulated Thor's runemu.sh (ASGARD_RUNEMU), started by Asgard Home with runemu.sh's arguments:
#   <rom> -P<system> --core=<core> --emulator=<emulator> --controllers=...
# It plays the game the way a screenshot needs: the core (build/sim/cores/<core>_libretro.so, tools/sim/build-core.sh)
# runs the ROM headless through libretro_frame.py for the frames and button presses the root's sim/play.tsv gives it,
# and the last frame is the top screen, ${ASGARD_SHOT}Game.png. Without the core or a real ROM the game's scraped
# screenshot stands in. Then, as RetroArch, it asks Home for the in-game menu and waits there until Home quits.
rom=$1 sys=${2#-P} core=${3#--core=}
here=$(cd "$(dirname "$0")" && pwd)
file=$ASGARD_ROOT$rom
out=${ASGARD_SHOT:-/tmp/asgard-sim-}Game.png
play=$(awk -F'\t' -v s="$sys" -v f="${rom##*/}" '$1 == s && $2 == f { $1 = $2 = ""; print; exit }' "$ASGARD_ROOT/sim/play.tsv" 2>/dev/null)
so=$here/../../build/sim/cores/${core}_libretro.so
if [ -n "$play" ] && [ -s "$file" ] && [ -f "$so" ]; then
  read -r frames presses <<<"$play"   # "<frames> button@first-last ..."
  # shellcheck disable=SC2086
  python3 -I "$here/libretro_frame.py" "$so" "$file" "$frames" "$out" $presses >&2 || rm -f "$out"
else
  stem=${rom##*/}; stem=${stem%.*}
  shot=$(ls "$ASGARD_ROOT/storage/ES-DE/downloaded_media/$sys/screenshots/$stem".* 2>/dev/null | head -1)
  [ -z "$shot" ] || cp "$shot" "$out"
  echo "sim runemu: no core run for $rom (play line, ROM data or ${core}_libretro.so missing)" >&2
fi
echo retroarch >"${ASGARD_KILL_DATA:-/tmp/.process-kill-data}"
echo menu >"$ASGARD_CMD_FIFO"
for _ in $(seq 600); do kill -0 "$PPID" 2>/dev/null || exit 0; sleep 0.1; done
