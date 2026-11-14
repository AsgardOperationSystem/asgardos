#!/bin/sh
# Stick calibration (GPcal) applied before InputPlumber starts (its unit's ExecStartPre). GPcal saves it as
# /storage/.config/autostart/GPcal.sh, which ends with "systemctl restart inputplumber": run from ROCKNIX's autostart,
# late in boot, that restart took the virtual pad away from Asgard Home for ~3 s (d-pad dead after every boot).
# rsinput's update_params changes the axis ranges, which InputPlumber reads when it opens the pad, so applying the
# values before it starts is enough. Only the rsinput parameter lines are run, never the rest of the file.
SRC=${GPCAL_AUTOSTART:-/storage/.config/autostart/GPcal.sh}
SAVED=${GPCAL_SAVED:-/storage/.config/asgard/gpcal.sh}
PARAMS=${RSINPUT_PARAMS:-/sys/module/rsinput/parameters}

if [ -f "$SRC" ]; then              # a new calibration (or the one from before Asgard did this)
  mkdir -p "$(dirname "$SAVED")" && mv -f "$SRC" "$SAVED"
fi
# No calibration made on the device: asgard.yml's asgard.stick_calibration, if any, becomes $SAVED (CAL-3).
${ASGARD_CONFIG:-python3 /usr/share/asgard/asgard_config.py} --stick-calibration "$SAVED" || true
[ -f "$SAVED" ] || exit 0

sed -n "s#^echo \(-\{0,1\}[0-9]\{1,\}\) > /sys/module/rsinput/parameters/\([a-z_]\{1,\}\)\$#\1 \2#p" "$SAVED" |
  while read -r value name; do
    [ -e "$PARAMS/$name" ] && echo "$value" > "$PARAMS/$name"
  done
exit 0
