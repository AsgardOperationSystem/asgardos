#!/bin/sh
# spec: CAL-2
# ./test_gpcal_apply.sh: GPcal's autostart file is moved out of autostart, only its rsinput lines are applied.
set -e
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
mkdir -p "$T/autostart" "$T/params"
for p in axis_leftx_min axis_leftx_center update_params; do : > "$T/params/$p"; done
cat > "$T/autostart/GPcal.sh" <<'G'
#!/usr/bin/env bash
echo -1002 > /sys/module/rsinput/parameters/axis_leftx_min
echo 109 > /sys/module/rsinput/parameters/axis_leftx_center
echo 5 > /sys/module/rsinput/parameters/not_in_this_driver
echo 1 > /sys/module/rsinput/parameters/update_params
touch /tmp/should-not-run; systemctl restart inputplumber
G
ASGARD_CONFIG=true GPCAL_AUTOSTART="$T/autostart/GPcal.sh" GPCAL_SAVED="$T/asgard/gpcal.sh" RSINPUT_PARAMS="$T/params" \
  sh "$(dirname "$0")/asgard-gpcal-apply.sh"
[ ! -e "$T/autostart/GPcal.sh" ] && [ -f "$T/asgard/gpcal.sh" ]
[ "$(cat "$T/params/axis_leftx_min")" = -1002 ] && [ "$(cat "$T/params/axis_leftx_center")" = 109 ]
[ "$(cat "$T/params/update_params")" = 1 ] && [ ! -e "$T/params/not_in_this_driver" ]
echo ok
