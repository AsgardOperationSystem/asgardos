#!/bin/bash
# Stick calibration (GPcal) for Settings > Controls. Not ROCKNIX's GPcal.sh: that one sets the quit target to "python3",
# so Quit in Asgard Home's game menu would killall every Python daemon (Home button, idle blank). Exit with GPcal's Quit.
# GPcal reads the raw pad (/dev/input/eventN), which InputPlumber hides (moves to /dev/inputplumber/sources) and grabs:
# InputPlumber is stopped while GPcal runs and restarted however it ends, which also gives the virtual pad the new
# calibration (CAL-4). ROCKNIX's GPcal.sh stops it only on SM8250.
. "${GPCAL_PROFILE:-/etc/profile}"
trap 'systemctl restart inputplumber' EXIT
trap 'exit 143' HUP INT TERM   # the EXIT trap runs on these too
systemctl stop inputplumber
cd "${GPCAL_PATH:-/usr/local/share/gpcal}" || exit 1
[ -f pyxel/bin/activate ] && source pyxel/bin/activate   # ROCKNIX's venv, if any (activate relies on the CWD)
sway_fullscreen python3 &
PYTHONDONTWRITEBYTECODE=1 python3 main.py
