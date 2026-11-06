#!/bin/bash
# Screen filter (VID-1): how a game's picture is scaled to the screens, one option for every emulator that has one.
# A game's own choice, else its system's (Emulator settings), else Settings > Display (asgard.screen_filter), else
# bilinear. Nearest neighbour scales unevenly to the Thor's 1080p panels from the 720p and smaller pictures most
# systems draw: Eden Duo's default drew a 1 px step across Brilliant Diamond's HP bar (2026-11-06).
#   asgard-screen-filter.sh get <system> <game>               nearest | bilinear | sharp | fsr
#   asgard-screen-filter.sh apply <emulator> <system> <game>  writes it into that emulator's config
# A choice the emulator doesn't have (sharp, fsr) falls back to bilinear. ROOT prefixes the paths, for the host test.
. "${FUNCTIONS:-/etc/profile.d/001-functions}"
ROOT=${ROOT:-}

get() {   # get <system> <game>
  local v
  v=$(get_setting screen_filter "$1" "$2")
  [ -z "$v" ] && v=$(get_setting asgard.screen_filter)
  case "$v" in
    nearest|bilinear|sharp|fsr) echo "$v" ;;
    *) echo bilinear ;;
  esac
}

# ini_set <file> <section> <key> <value> [separator]: replaces the key in its section, or adds it (and the section)
# when it's missing: a fresh config only gets most keys when the emulator first saves it. The separator keeps the
# file's style ("=", or " = " for PCSX2, Dolphin, Flycast and TOML).
ini_set() {
  python3 - "$@" <<'PY'
import os
import sys
path, section, key, value = sys.argv[1:5]
sep = sys.argv[5] if len(sys.argv) > 5 else "="
try:
    lines = open(path, encoding="utf-8", errors="replace").read().splitlines()
except FileNotFoundError:
    lines = []
head = "[" + section + "]"
start = next((i for i, l in enumerate(lines) if l.strip() == head), None)
if start is None:
    lines += ([""] if lines and lines[-1].strip() else []) + [head, f"{key}{sep}{value}"]
else:
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("[")), len(lines))
    hit = next((i for i in range(start + 1, end) if lines[i].split("=", 1)[0].strip() == key), None)
    if hit is None:
        lines.insert(start + 1, f"{key}{sep}{value}")
    else:
        lines[hit] = f"{key}{sep}{value}"
os.makedirs(os.path.dirname(path), exist_ok=True)
open(path, "w", encoding="utf-8").write("\n".join(lines) + "\n")
PY
}

apply() {   # apply <emulator> <system> <game>
  local f
  f=$(get "$2" "$3")
  case "$1" in
    eden|eden-duo)   # frontend_common ini, [Renderer]: 0 nearest, 1 bilinear, 6 FSR; \default=false or Eden ignores it
      local ini=qt-config.ini
      [ "$1" = eden-duo ] && ini=sdl2-config.ini
      local n=1
      case "$f" in nearest) n=0 ;; fsr) n=6 ;; esac
      ini_set "${ROOT}/storage/.config/eden/${ini}" Renderer 'scaling_filter\default' false
      ini_set "${ROOT}/storage/.config/eden/${ini}" Renderer scaling_filter "$n"
      ;;
    armsx2)   # PCSX2 fork: present filter 0 off (nearest), 1 bilinear smooth, 2 bilinear sharp. Not "filter =": textures
      local n=1
      case "$f" in nearest) n=0 ;; sharp) n=2 ;; esac
      ini_set "${ROOT}/storage/.config/ARMSX2/inis/PCSX2.ini" EmuCore/GS linear_present_mode "$n" " = "
      ;;
    aethersx2)   # the older PCSX2: a bool
      local b=true
      [ "$f" = nearest ] && b=false
      ini_set "${ROOT}/storage/.config/aethersx2/inis/PCSX2.ini" EmuCore/GS linear_present "$b" " = "
      ;;
    flycast)
      local b=yes
      [ "$f" = nearest ] && b=no
      ini_set "${ROOT}/storage/.config/flycast/emu.cfg" config rend.LinearInterpolation "$b" " = "
      ;;
    dolphin)   # output resampling: 0 default (Dolphin has no nearest), 1 bilinear, 5 sharp bilinear
      local n=1
      case "$f" in nearest) n=0 ;; sharp) n=5 ;; esac
      ini_set "${ROOT}/storage/.config/dolphin-emu/GFX.ini" Enhancements OutputResampling "$n" " = "
      ;;
    azahar)   # [Layout] filter_mode: linear or nearest, for the screens' layout (texture_filter is the game's)
      local b=true
      [ "$f" = nearest ] && b=false
      ini_set "${ROOT}/storage/.config/azahar/qt-config.ini" Layout 'filter_mode\default' false
      ini_set "${ROOT}/storage/.config/azahar/qt-config.ini" Layout filter_mode "$b"
      ;;
    rpcs3)   # YAML, under Video: the line ships in its config
      local m=Bilinear
      case "$f" in nearest) m=Nearest ;; fsr) m="FidelityFX Super Resolution" ;; esac
      [ -f "${ROOT}/storage/.config/rpcs3/config.yml" ] &&
        sed -i "s/^\(\s*Output Scaling Mode:\).*/\1 ${m}/" "${ROOT}/storage/.config/rpcs3/config.yml"
      ;;
    xemu)   # TOML [display]
      local m=linear
      [ "$f" = nearest ] && m=nearest
      ini_set "${ROOT}/storage/.config/xemu/xemu.toml" display filtering "'${m}'" " = "
      ;;
    ppsspp)   # 1 linear, 2 nearest; per screen layout, landscape and portrait (sway rotates the Thor's panels)
      local n=1
      [ "$f" = nearest ] && n=2
      ini_set "${ROOT}/storage/.config/ppsspp/PSP/SYSTEM/ppsspp.ini" DisplayLayout.Landscape BufferFiltering "$n" " = "
      ini_set "${ROOT}/storage/.config/ppsspp/PSP/SYSTEM/ppsspp.ini" DisplayLayout.Portrait BufferFiltering "$n" " = "
      ;;
    nanoboyadvance)   # TOML [video]: missing means nearest
      local m=linear
      [ "$f" = nearest ] && m=nearest
      ini_set "${ROOT}/storage/.config/nanoboyadvance/config.toml" video filter "\"${m}\"" " = "
      ;;
    *) return 1 ;;
  esac
}

case "$1" in
  get) get "$2" "$3" ;;
  apply) shift; apply "$@" ;;
  *) echo "usage: $0 get <system> <game> | apply <emulator> <system> <game>" >&2; exit 2 ;;
esac
