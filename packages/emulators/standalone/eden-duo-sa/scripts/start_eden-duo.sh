#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026-present Asgard OS

# Eden Duo (eden-cli, SDL3): Switch games with a live companion on the bottom screen, for games that have a
# .dsmod package in load/<title id>/. Shares Eden's data (keys, firmware, saves, mods) with eden-sa; its own config
# is sdl2-config.ini, seeded once from Eden's qt-config.ini (same frontend_common format: controls, paths, renderer).
. /etc/profile
# Quit with -9, as Azahar/Dolphin/melonDS: on SIGTERM eden-cli shuts down for longer than Home's 4 s grace (it
# rewrites the Vulkan pipeline cache, which it also flushes during play), so every quit waited 4 s and got -KILL anyway.
set_kill set "-9 eden-duo-cli"

CONF_DIR="/storage/.config/eden"
DATA_DIR="/storage/.local/share/eden"
BIOS_DIR="/storage/roms/bios/NSO"   # prod.keys, title.keys, Firmware.<version>.zip (own console)
CFG="${CONF_DIR}/sdl2-config.ini"

[ ! -d "${CONF_DIR}" ] && cp -r /usr/config/eden /storage/.config
[ -f "${CFG}" ] || cp "${CONF_DIR}/qt-config.ini" "${CFG}"
# The Thor's pad (InputPlumber's DualSense) has another GUID under SDL3 (Eden Duo) than under SDL2 (eden-sa, whose
# config seeded this one), so no binding matched; and player 1 was marked disconnected. Both fixed on every start.
# The handheld slot (player 8, eden-sa's only pad) stays disconnected: it's the same pad again, still in SDL2's
# button order, and Brilliant Diamond reads every connected pad (each d-pad press came with a phantom up/down).
sed -i -e "s/guid:030000004c050000e60c000011810000/guid:030000004c050000e60c000000006800/g" \
       -e "s/^player_0_connected=false/player_0_connected=true/" \
       -e "s/^player_0_connected\\\\default=true/player_0_connected\\\\default=false/" \
       -e "s/^player_8_connected=true/player_8_connected=false/" "${CFG}"
# And SDL3 numbers that pad in its own order (HIDAPI: south east west north back guide start lstick rstick l r; axes
# lx ly rx ry l2 r2), not evdev's (SDL2: south east north west l r l2 r2 select start mode lstick rstick; lx ly l2
# rx ry r2): X/Y, L/R, -/+, the stick clicks, ZL and the right stick pointed at other inputs. Player 1, set every start.
PAD="engine:sdl,port:0,guid:030000004c050000e60c000000006800"
for b in a:button:1 b:button:0 x:button:3 y:button:2 l:button:9 r:button:10 minus:button:4 plus:button:6 \
         lstick:button:7 rstick:button:8 zl:axis:4,threshold:0.5,invert:+ zr:axis:5,threshold:0.5,invert:+; do
  sed -i -e "s|^player_0_button_${b%%:*}=.*|player_0_button_${b%%:*}=\"${PAD},${b#*:}\"|" \
         -e "s|^player_0_button_${b%%:*}\\\\default=.*|player_0_button_${b%%:*}\\\\default=false|" "${CFG}"
done
sed -i -e "s|^player_0_rstick=.*|player_0_rstick=\"${PAD},axis_x:2,axis_y:3,offset_x:0,offset_y:0,invert_x:+,invert_y:+,deadzone:0.1,range:1\"|" "${CFG}"
mkdir -p "${DATA_DIR}/keys"

# Keys and firmware: as start_eden.sh (a new dump only needs copying to the card).
for k in prod.keys title.keys; do
  [ -f "${BIOS_DIR}/${k}" ] && ! cmp -s "${BIOS_DIR}/${k}" "${DATA_DIR}/keys/${k}" && cp "${BIOS_DIR}/${k}" "${DATA_DIR}/keys/"
done
FW_ZIP=$(ls -1 "${BIOS_DIR}"/Firmware*.zip 2>/dev/null | sort -V | tail -1)
FW_DIR="${DATA_DIR}/nand/system/Contents/registered"
if [ -n "${FW_ZIP}" ] && [ "$(cat "${FW_DIR}/.asgard-firmware" 2>/dev/null)" != "$(basename "${FW_ZIP}")" ]; then
  rm -rf "${FW_DIR}" && mkdir -p "${FW_DIR}"
  unzip -o -q "${FW_ZIP}" -d "${FW_DIR}" && basename "${FW_ZIP}" > "${FW_DIR}/.asgard-firmware"
fi

GAME=$(echo "${1}" | sed "s#^/.*/##")
PLATFORM=$(echo "${2}" | sed "s#^/.*/##")

# Emulator options (eden-duo-sa in es_features.cfg, the same as Eden's), written into the config on every start.
eden_set() {   # key value: the value, and \default=false so Eden reads it
  sed -i -e "s|^${1}=.*|${1}=${2}|" -e "s|^${1}\\\\default=.*|${1}\\\\default=false|" "${CFG}"
}
GPU_ACC=$(get_setting gpu_accuracy "${PLATFORM}" "${GAME}")
ASTC=$(get_setting astc_decoding "${PLATFORM}" "${GAME}")
ASYNC_GPU=$(get_setting async_gpu_emulation "${PLATFORM}" "${GAME}")
case "${GPU_ACC}" in 0|2) ;; *) GPU_ACC=1;; esac
case "${ASTC}" in 0|2) ;; *) ASTC=1;; esac
[ "${ASYNC_GPU}" = 0 ] && ASYNC_GPU=false || ASYNC_GPU=true
eden_set gpu_accuracy "${GPU_ACC}"
eden_set accelerate_astc "${ASTC}"
eden_set use_asynchronous_gpu_emulation "${ASYNC_GPU}"
# Screen filter (VID-1): Eden Duo's own default is nearest neighbour, which stepped Brilliant Diamond's HP bar
/usr/share/asgard/asgard-screen-filter.sh apply eden-duo "${PLATFORM}" "${GAME}"
# Flush GPU caches: Turnip flushes before every draw (Luminescent Platinum's stray "fireworks", see start_eden.sh).
[ "$(get_setting flush_gpu_caches "${PLATFORM}" "${GAME}")" = 1 ] && export TU_DEBUG=flushall

CORES=$(get_setting "cores" "${PLATFORM}" "${GAME}")
EMUPERF="${FAST_CORES}"
[ "${CORES}" = "little" ] && EMUPERF="${SLOW_CORES}"
[ "${CORES}" = "all" ] && EMUPERF=""

# The companion window ("Eden - Screen 2 (DSMod aux)") goes to the bottom screen by AsgardOS's "Screen 2" rules.
${EMUPERF} /usr/bin/eden-duo-cli -f --aux-window -g "${1}"
