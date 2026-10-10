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

# Off the A510s by default: NCE runs the Switch's 4 cores as host threads, plus the GPU and shader threads.
CORES=$(get_setting "cores" "${PLATFORM}" "${GAME}")
EMUPERF="${FAST_CORES}"
[ "${CORES}" = "little" ] && EMUPERF="${SLOW_CORES}"
[ "${CORES}" = "all" ] && EMUPERF=""

# Eden's docs: Wayland is slower and buggier than X11 for it.
export QT_QPA_PLATFORM=xcb

sway_fullscreen "eden" &
${EMUPERF} /usr/bin/eden -f -g "${1}"
