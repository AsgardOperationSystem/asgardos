#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026-present Asgard OS

# Tools > Moonlight: moonlight-qt (pair with a PC running Sunshine or GeForce Experience, pick an app, stream) on the
# top screen. runemu.sh runs it like the other Tools, so its emulator options apply (cores, fan, sleep).
. /etc/profile
set_kill set "moonlight-qt"

# The window maps on whichever screen has focus (the bottom one after a tap): top screen, fullscreen, as Asgard Music.
(for i in $(seq 40); do
  sleep 0.25
  swaymsg -q '[app_id="^com.moonlight_stream.Moonlight$"] move container to output DSI-2, fullscreen enable' 2>/dev/null && break
done) &
QT_QPA_PLATFORM=wayland exec /usr/bin/moonlight-qt "$@"
