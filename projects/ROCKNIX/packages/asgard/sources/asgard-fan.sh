#!/bin/sh
# fancontrol.service ExecCondition. A fixed fan speed (asgard.fan_manual = PWM 0-255, from Thor Panel or Settings)
# replaces fancontrol's curve: set the PWM and skip starting fancontrol (exit 1). Living in the unit means every
# restart keeps it: runemu.sh restarts fancontrol on each game launch, which used to drop the fan back to its curve.
M=$(sed -n 's/^asgard\.fan_manual=//p' /storage/.config/system/configs/system.cfg | tail -1)
[ -z "$M" ] && exit 0
P=$(ls /sys/class/hwmon/hwmon*/pwm1 2>/dev/null | head -1)
[ -n "$P" ] && { echo 1 > "${P}_enable"; echo "$M" > "$P"; }
exit 1
