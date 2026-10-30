#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026-present Asgard OS

# Tools > Terminal: QTerminal fullscreen on the top screen, Asgard Keyboard (asgard-osk: Ctrl, Alt, arrows, a symbols
# layer) filling the bottom one. Not wvkbd (ROCKNIX's qterminal.sh): its layer surface never gets a touch on the Thor.
. /etc/profile
set_kill set "qterminal"
OSK=${ASGARD_OSK:-/usr/bin/asgard-osk}   # a dev build: ASGARD_OSK=/storage/asgard-dev/...

[ -d /storage/.config/qterminal.org ] || cp -r /usr/config/qterminal.org /storage/.config/

cd ~/
/usr/bin/qterminal &
TERM_PID=$!
"$OSK" --osk qterminal &
KB=$!
echo $KB > /run/asgard-osk.pid   # Home hides it while its in-game menu (bottom screen) is open
# Each window where it belongs (they map on whichever screen has focus), then the terminal gets the keys.
(for i in $(seq 40); do
  sleep 0.25
  swaymsg -q '[app_id="^qterminal$"] move container to output DSI-2, fullscreen enable' 2>/dev/null || continue
  swaymsg -q '[title="^Asgard Keyboard$"] move container to output DSI-1, fullscreen enable' 2>/dev/null && break
done
swaymsg -q '[app_id="^qterminal$"] focus') &
wait $TERM_PID
kill $KB
rm -f /run/asgard-osk.pid
