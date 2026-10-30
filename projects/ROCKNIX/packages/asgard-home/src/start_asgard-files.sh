#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026-present Asgard OS

# Asgard Files (Tools > Files): asgard-home --files. runemu.sh runs it like the other Tools.
. /etc/profile
set_kill set "asgard-files"

# The top window maps on whichever screen has focus (the bottom one after a tap): put both where they belong, as
# Asgard Music does.
(for i in $(seq 20); do
  sleep 0.25
  swaymsg -q '[title="^Asgard Files$"] move container to output DSI-2, fullscreen enable' 2>/dev/null || continue
  swaymsg -q '[title="^Asgard Files .Bottom.$"] move container to output DSI-1, fullscreen enable' && break
done) &
exec /usr/bin/asgard-files --files
