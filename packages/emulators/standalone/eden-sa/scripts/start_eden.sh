#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026-present Asgard OS

. /etc/profile
set_kill set "eden"

CONF_DIR="/storage/.config/eden"
DATA_DIR="/storage/.local/share/eden"
BIOS_DIR="/storage/roms/bios/NSO"   # prod.keys, title.keys, Firmware.<version>.zip (own console)

[ ! -d "${CONF_DIR}" ] && cp -r /usr/config/eden /storage/.config
mkdir -p "${DATA_DIR}/keys"

# Keys: refreshed from the card on every start, so a new dump only needs copying there.
for k in prod.keys title.keys; do
  [ -f "${BIOS_DIR}/${k}" ] && ! cmp -s "${BIOS_DIR}/${k}" "${DATA_DIR}/keys/${k}" && cp "${BIOS_DIR}/${k}" "${DATA_DIR}/keys/"
done

# Firmware: a dump zip is just the system NCAs, which is all Eden's own Install Firmware does too.
# Reinstalled when a different zip shows up on the card.
FW_ZIP=$(ls -1 "${BIOS_DIR}"/Firmware*.zip 2>/dev/null | sort -V | tail -1)
FW_DIR="${DATA_DIR}/nand/system/Contents/registered"
if [ -n "${FW_ZIP}" ] && [ "$(cat "${FW_DIR}/.asgard-firmware" 2>/dev/null)" != "$(basename "${FW_ZIP}")" ]; then
  rm -rf "${FW_DIR}" && mkdir -p "${FW_DIR}"
  unzip -o -q "${FW_ZIP}" -d "${FW_DIR}" && basename "${FW_ZIP}" > "${FW_DIR}/.asgard-firmware"
fi

GAME=$(echo "${1}" | sed "s#^/.*/##")
PLATFORM=$(echo "${2}" | sed "s#^/.*/##")

# Emulator options (Asgard Home > game or Switch settings > Emulator options, es_features.cfg's eden-sa), written into
# Eden's config on every start: Eden saves its whole config on exit, so a value set while it runs wouldn't stick.
# Unset = the defaults below (Eden's own).
eden_set() {   # key value: the value, and \default=false so Eden reads it
  sed -i -e "s|^${1}=.*|${1}=${2}|" -e "s|^${1}\\\\default=.*|${1}\\\\default=false|" "${CONF_DIR}/qt-config.ini"
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
# Screen filter (VID-1): the game's, the system's, Settings > Display's, else bilinear
/usr/share/asgard/asgard-screen-filter.sh apply eden "${PLATFORM}" "${GAME}"
# Turnip flushes and invalidates its caches before every draw: Luminescent Platinum (BD) drew stray red/green
# "fireworks" without it, on Mesa 26.2.4 + Eden master-58c1e20ee5 (2026-10-17; GPU accuracy, ASTC, async GPU,
# sysmem, nolrz and noubwc didn't help). Costs some speed, so per game.
[ "$(get_setting flush_gpu_caches "${PLATFORM}" "${GAME}")" = 1 ] && export TU_DEBUG=flushall

# Off the A510s by default: NCE runs the Switch's 4 cores as host threads, plus the GPU and shader threads.
CORES=$(get_setting "cores" "${PLATFORM}" "${GAME}")
EMUPERF="${FAST_CORES}"
[ "${CORES}" = "little" ] && EMUPERF="${SLOW_CORES}"
[ "${CORES}" = "all" ] && EMUPERF=""

# Eden's docs: Wayland is slower and buggier than X11 for it.
export QT_QPA_PLATFORM=xcb

sway_fullscreen "eden" &
${EMUPERF} /usr/bin/eden -f -g "${1}"
