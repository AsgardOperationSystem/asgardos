#!/bin/bash
# Stick calibration for Settings > Hardware > Calibration (thor_stickcal.py). It reads rsinput's raw pad, which
# InputPlumber hides (moves to /dev/inputplumber/sources) and grabs: InputPlumber is stopped while it runs and
# restarted however it ends, which also gives the virtual pad the new calibration (CAL-4).
. "${STICKCAL_PROFILE:-/etc/profile}"
trap 'systemctl restart inputplumber' EXIT
trap 'exit 143' HUP INT TERM   # the EXIT trap runs on these too
systemctl stop inputplumber
python3 "${STICKCAL:-/usr/share/asgard/thor_stickcal.py}"
