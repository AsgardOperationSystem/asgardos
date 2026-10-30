#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026-present Asgard OS

# Firefox (Tools > Firefox): the page on the top screen (DSI-2, 1920x1080, touch), Asgard Keyboard (asgard-osk) filling
# the bottom one (DSI-1). One page across two differently sized panels reads badly, so the bottom is input only. Not
# wvkbd: its layer surface never gets a touch on the Thor.
. /etc/profile
set_kill set "firefox"
OSK=${ASGARD_OSK:-/usr/bin/asgard-osk}   # a dev build: ASGARD_OSK=/storage/asgard-dev/...

MOZ_ENABLE_WAYLAND=1 /usr/lib/firefox/firefox --name firefox "$@" &
FF=$!
"$OSK" --osk firefox &
KB=$!
echo $KB > /run/asgard-osk.pid   # Home hides it while its in-game menu (bottom screen) is open
# Each window where it belongs (they map on whichever screen has focus), then the page gets the keys.
(for i in $(seq 60); do
  sleep 0.25
  swaymsg -q '[app_id="^firefox$"] move container to output DSI-2, fullscreen enable' 2>/dev/null || continue
  swaymsg -q '[title="^Asgard Keyboard$"] move container to output DSI-1, fullscreen enable' 2>/dev/null && break
done
swaymsg -q '[app_id="^firefox$"] focus') &
wait $FF
kill $KB
rm -f /run/asgard-osk.pid
