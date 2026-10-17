#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026-present Asgard OS

# Asgard Music: the Music Player system's player (asgard-home --music). A playlist (.m3u) starts playing; anything else
# (ROCKNIX's "Start Music Player.sh") opens the playlist picker. runemu.sh runs it like an emulator, so its emulator
# options apply (Sleep > Screens off, keep running; cores; fan).
. /etc/profile
set_kill set "asgard-music"

PLAYLIST=()
case "${1}" in
  *.m3u) PLAYLIST=("${1}") ;;
esac
exec /usr/bin/asgard-music --music "${PLAYLIST[@]}"
