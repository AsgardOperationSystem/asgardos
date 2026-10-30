#!/bin/bash
# SPDX-License-Identifier: GPL-2.0
# Copyright (C) 2023 JELOS (https://github.com/JustEnoughLinuxOS)

. /etc/profile

set_kill set "-HUP gmu.bin"

GMUPATH="/storage/.config/gmu"
GMUCONFIG="${GMUPATH}/gmu.conf"
GMUINPUT="${GMUPATH}/gmuinput.conf"

if [ -d "/storage/.local/share/gmu" ]
then
  rm -rf /storage/.local/share/gmu
fi


FBHEIGHT="$(fbheight)"
FBWIDTH="$(fbwidth)"
# Asgard: on dual-screen devices fb0 can be the bottom panel (the Thor: 1240x1080) while sway shows gmu fullscreen on
# the top one (DSI-2, 1920x1080), so the skin was laid out for the wrong size. Use the top output's size from sway.
TOP=$(swaymsg -t get_outputs -r 2>/dev/null | jq -r '.[] | select(.name == "DSI-2") | "\(.rect.width) \(.rect.height)"')
[ -n "${TOP}" ] && read -r FBWIDTH FBHEIGHT <<< "${TOP}"

if [ ! -d "${GMUPATH}" ]
then
  mkdir -p ${GMUPATH}
fi

cp -rf /usr/config/gmu/* ${GMUPATH}
ln -sf ${GMUPATH}/playlists /storage/.local/share/gmu

sed -i "s~SDL.Height=.*\$~SDL.Height=${FBHEIGHT}~g" ${GMUCONFIG}
sed -i "s~SDL.Width=.*\$~SDL.Width=${FBWIDTH}~g" ${GMUCONFIG}

if (( ${FBWIDTH} <= 1024 ))
then
  sed -i "s~default-modern-large~default-modern~g" ${GMUCONFIG}
  sed -i "s~SDL.Fullscreen=.*\$~SDL.Fullscreen=no~g" ${GMUCONFIG}
else
  sed -i "s~default-modern.*\$~default-modern-large~g" ${GMUCONFIG}
  sed -i "s~SDL.Fullscreen=.*\$~SDL.Fullscreen=yes~g" ${GMUCONFIG}
fi

# Asgard: an array, not -l "\"<path>\"" expanded unquoted: that passed the quote characters (and split names with
# spaces), so gmu never loaded the playlist.
PLAYLIST=()
if [ "${1}" ]
then
  PLAYLIST=(-l "${1}")
fi

### Set up controls
for CONTROL in DEVICE_BTN_SOUTH DEVICE_BTN_EAST DEVICE_BTN_NORTH         \
               DEVICE_BTN_WEST DEVICE_BTN_TL DEVICE_BTN_TR               \
               DEVICE_BTN_TL2 DEVICE_BTN_TR2 DEVICE_BTN_SELECT           \
               DEVICE_BTN_START DEVICE_BTN_MODE DEVICE_BTN_THUMBL        \
               DEVICE_BTN_THUMBR DEVICE_BTN_DPAD_UP DEVICE_BTN_DPAD_DOWN \
               DEVICE_BTN_DPAD_LEFT DEVICE_BTN_DPAD_RIGHT
do
  sed -i "s~@${CONTROL}@~${!CONTROL}~g" ${GMUINPUT}
done

cd /usr/local/share/gmu
/usr/local/bin/gmu.bin -d /usr/local/etc/gmu -c /storage/.config/gmu/gmu.conf "${PLAYLIST[@]}"
