#!/bin/bash

# SPDX-License-Identifier: GPL-2.0
# Copyright (C) 2026-present Asgard OS (https://github.com/AsgardOperationSystem)

# GBA DS: the game on the top screen, its map or HUD in a second window ("GBA DS map") that Asgard's sway rule puts
# on the bottom screen (thor-sway-rotate.sh). Games without map support play on the top screen alone.

. /etc/profile

# SIGTERM: GBA DS saves a state on the way out (save_on_quit) and exits 0.
set_kill set "gba-ds"

# Its own files (gba-ds.cfg, states/, cheats/, patches/, overlays/): /usr/bin is read-only.
GBADS_HOME="/storage/.config/gba-ds"
mkdir -p "${GBADS_HOME}"
export GBADS_HOME

# The pad's Home alone is Asgard's in-game menu (MENU-1, GAME-11); it stays GBA DS's hotkey button, and the in-game
# menu opens GBA DS's own with F1.
export GBADS_PAD_HOME_MENU=0

GAME=$(echo "${1}" | sed "s#^/.*/##")
PLATFORM=$(echo "${2}" | sed "s#^/.*/##")

# On the command line, so they win over gba-ds.cfg and the choices GBA DS keeps:
# - a window per screen, touches as the bottom window's own;
# - no self-update (the image ships the binary; Asgard's updates bring new versions);
# - battery saves as RetroArch's .srm beside the ROM, so a game carries on in either.
OPTS=("--layout=dual" "--touch-map=screen" "--update-check=0" "--save-ext=srm")

CORES=$(get_setting "cores" "${PLATFORM}" "${GAME}")
unset EMUPERF
[ "${CORES}" = "little" ] && EMUPERF="${SLOW_CORES}"
[ "${CORES}" = "big" ] && EMUPERF="${FAST_CORES}"

${EMUPERF} /usr/bin/gba-ds "${OPTS[@]}" "${1}"
