#!/bin/sh
# spec: PWR-10
# requires: cmd:bash
# A copy of the SM8550 power-handler, its paths rewritten and systemctl stubbed: the power key suspends; with an external
# display it blanks instead; a press ends that blank. The lid stays with logind, configured to suspend after a 10 s holdoff.
# The power key on screens the idle timer blanked is test_power_key_idle_blank.sh. That logind reads this config is a device check.
set -e
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
H=$(dirname "$(readlink -f "$0")")/../..
Q=$H/hardware/quirks/platforms/SM8550
mkdir -p "$T/bin" "$T/run"
printf 'get_setting() { echo mem; }\nlog() { :; }\n' > "$T/profile"
printf '#!/bin/sh\necho "$*" >> %s/suspend.log\n' "$T" > "$T/bin/systemctl"
cat > "$T/bin/external-display" <<S
#!/bin/sh
echo "\$*" >> $T/display.log
[ "\$1" != connected ] || [ -e $T/attached ]
S
chmod +x "$T/bin"/*
sed -e "s#^\. /etc/profile#. $T/profile#" -e "s#/run/#$T/run/#g" -e "s#/usr/bin/external-display#$T/bin/external-display#" \
    -e "s#/sys/class/#$T/sys/class/#g" "$Q/bin/power-handler" > "$T/handler"
press() { rm -f "$T/suspend.log" "$T/display.log"; PATH="$T/bin:$PATH" bash "$T/handler" "$@"; }

press power
[ "$(cat "$T/suspend.log")" = suspend ] || { echo "FAIL: the power key didn't suspend"; exit 1; }

: > "$T/attached"
press power
[ ! -e "$T/suspend.log" ] || { echo "FAIL: suspended with an external display"; exit 1; }
grep -qx blank "$T/display.log" || { echo "FAIL: internal panel not blanked"; cat "$T/display.log"; exit 1; }

press power
[ ! -e "$T/suspend.log" ] || { echo "FAIL: suspended instead of ending the blank"; exit 1; }
grep -qx unblank "$T/display.log" || { echo "FAIL: not unblanked"; cat "$T/display.log"; exit 1; }
rm "$T/attached"

press lid close
[ ! -e "$T/suspend.log" ] || { echo "FAIL: the handler suspended on the lid: that's logind's"; exit 1; }

# logind owns the lid and the handler the key; the holdoff is 10 s.
C=$Q/030-suspend_mode
grep -qx 'HandleLidSwitch=suspend' "$C" && grep -qx 'HandleLidSwitchExternalPower=suspend' "$C" && grep -qx 'HandlePowerKey=ignore' "$C" ||
  { echo "FAIL: logind config"; exit 1; }
grep -qx 'HoldoffTimeoutSec=10' "$H/asgard/logind.conf.d/thor-holdoff.conf" || { echo "FAIL: holdoff"; exit 1; }
echo OK
