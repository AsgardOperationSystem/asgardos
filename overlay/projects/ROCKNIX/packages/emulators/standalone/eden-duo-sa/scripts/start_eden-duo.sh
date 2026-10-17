#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026-present Asgard OS

# Eden Duo (eden-cli, SDL3): Switch games with a live companion on the bottom screen, for games that have a
# .dsmod package in load/<title id>/. Shares Eden's data (keys, firmware, saves, mods) with eden-sa; its own config
# is sdl2-config.ini, seeded once from Eden's qt-config.ini (same frontend_common format: controls, paths, renderer).
. /etc/profile
set_kill set "eden-duo-cli"

CONF_DIR="/storage/.config/eden"
DATA_DIR="/storage/.local/share/eden"
BIOS_DIR="/storage/roms/bios/NSO"   # prod.keys, title.keys, Firmware.<version>.zip (own console)
CFG="${CONF_DIR}/sdl2-config.ini"

[ ! -d "${CONF_DIR}" ] && cp -r /usr/config/eden /storage/.config
[ -f "${CFG}" ] || cp "${CONF_DIR}/qt-config.ini" "${CFG}"
# The Thor's pad (InputPlumber's DualSense) has another GUID under SDL3 (Eden Duo) than under SDL2 (eden-sa, whose
# config seeded this one), so no binding matched; and player 1 was marked disconnected. Both fixed on every start.
sed -i -e "s/guid:030000004c050000e60c000011810000/guid:030000004c050000e60c000000006800/g" \
       -e "s/^player_0_connected=false/player_0_connected=true/" \
       -e "s/^player_0_connected\\\\default=true/player_0_connected\\\\default=false/" "${CFG}"
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
# Flush GPU caches: Turnip flushes before every draw (Luminescent Platinum's stray "fireworks", see start_eden.sh).
[ "$(get_setting flush_gpu_caches "${PLATFORM}" "${GAME}")" = 1 ] && export TU_DEBUG=flushall

CORES=$(get_setting "cores" "${PLATFORM}" "${GAME}")
EMUPERF="${FAST_CORES}"
[ "${CORES}" = "little" ] && EMUPERF="${SLOW_CORES}"
[ "${CORES}" = "all" ] && EMUPERF=""

# The companion window ("Eden - Screen 2 (DSMod aux)") goes to the bottom screen by ROCKNIX's "Screen 2" rules.
${EMUPERF} /usr/bin/eden-duo-cli -f --aux-window -g "${1}"
