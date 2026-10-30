#!/bin/sh
# Steam keeps a controller's settings (button layout, A/B swap...) per serial number, in
# Steam Controller Configs/<user>/config/{preferences,configset}_DS<mac>.vdf. InputPlumber's virtual DualSense gets
# a new MAC on every boot, so Steam saw a new pad each time and its settings were gone. Before Steam starts, the
# newest saved DualSense settings are copied to today's serial (start_steam_arm64.sh).
D="/storage/.local/share/Steam/steamapps/common/Steam Controller Configs"
U=$(grep -l "DualSense" /sys/class/hidraw/hidraw*/device/uevent 2>/dev/null | head -1)
MAC=$(sed -n 's/^HID_UNIQ=//p' "$U" 2>/dev/null | tr -d ':')
[ -n "$MAC" ] || exit 0
for dir in "$D"/*/config; do
  for kind in preferences configset; do
    newest=$(ls -t "$dir"/${kind}_DS*.vdf 2>/dev/null | head -1)
    [ -n "$newest" ] && [ "$newest" != "$dir/${kind}_DS$MAC.vdf" ] && cp "$newest" "$dir/${kind}_DS$MAC.vdf"
  done
done
exit 0
