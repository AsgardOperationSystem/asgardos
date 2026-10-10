#!/bin/bash
# Stick calibration (GPcal) for Settings > Controls. Not ROCKNIX's GPcal.sh: that one sets the quit target to "python3",
# so Quit in Asgard Home's game menu would killall every Python daemon (Home button, idle blank). Exit with GPcal's Quit.
. /etc/profile
cd /usr/local/share/gpcal && source pyxel/bin/activate   # activate relies on the CWD
sway_fullscreen python3 &
PYTHONDONTWRITEBYTECODE=1 python3 main.py
systemctl restart inputplumber   # the virtual pad picks up the new calibration
