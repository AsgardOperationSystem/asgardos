#!/bin/sh
# spec: XFER-3 PWR-10
# requires: cmd:bash
# A copy of the SM8550 power-handler, its paths rewritten and systemctl, swaymsg and asgard-transfers.py stubbed: with transfers
# running, the power key and a lid close ask asgard-transfers.py for a sleep (its standby) instead of suspending; during a
# standby the key and the lid opening end it; screens that X turned off still just wake (PWR-10); nothing running, the key
# suspends as before. The standby itself is test_asgard_transfers.py.
set -e
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
H=$(dirname "$(readlink -f "$0")")/../..
Q=$H/hardware/quirks/platforms/SM8550
mkdir -p "$T/bin" "$T/run"
printf 'get_setting() { echo mem; }\nlog() { :; }\n' > "$T/profile"
printf '#!/bin/sh\necho "$*" >> %s/suspend.log\n' "$T" > "$T/bin/systemctl"
printf '#!/bin/sh\necho "$*" >> %s/transfers.log\n' "$T" > "$T/bin/transfers"
printf '#!/bin/sh\n[ "$*" = busctl ] || true\n' > "$T/bin/busctl"
cat > "$T/bin/swaymsg" <<S
#!/bin/sh
if [ -e $T/screens-off ]; then echo '[{"name":"DSI-2","power": false}]'; else echo '[{"name":"DSI-2","power": true}]'; fi
S
chmod +x "$T/bin"/*
sed -e "s#^\. /etc/profile#. $T/profile#" -e "s#/run/#$T/run/#g" -e "s#/sys/class/#$T/sys/class/#g" \
    -e "s#python3 /usr/share/asgard/asgard-transfers.py#$T/bin/transfers#" "$Q/bin/power-handler" > "$T/handler"
grep -q "$T/bin/transfers" "$T/handler" || { echo "FAIL: the handler doesn't call asgard-transfers.py"; exit 1; }
press() { rm -f "$T/suspend.log" "$T/transfers.log"; PATH="$T/bin:$PATH" bash "$T/handler" "$@"; }
said() { [ "$(cat "$T/transfers.log" 2>/dev/null)" = "$1" ] || { echo "FAIL: $2: transfers got '$(cat "$T/transfers.log" 2>/dev/null)'"; exit 1; }; }
nosuspend() { [ ! -e "$T/suspend.log" ] || { echo "FAIL: $1: suspended"; exit 1; }; }

# nothing running: the key suspends, a lid close is logind's
press power
[ "$(cat "$T/suspend.log")" = suspend ] || { echo "FAIL: idle, the key didn't suspend"; exit 1; }
said "" "idle key"
press lid close
said "" "idle lid"; nosuspend "idle lid"

# transfers running: the key and a close are a standby
: > "$T/run/asgard-transfers.busy"
press power
said sleep "busy key"; nosuspend "busy key"
press lid close
said sleep "busy lid close"; nosuspend "busy lid close"
[ -e "$T/run/.lid-closed-at" ] || { echo "FAIL: the close wasn't noted for PWR-13"; exit 1; }
press lid open
said "" "lid open with no standby"

# screens X turned off: the key wakes them, as always, and doesn't start a standby
: > "$T/screens-off"
press power
said "" "key on screens that are off"; nosuspend "key on screens that are off"
rm "$T/screens-off"

# in a standby: the key and the lid opening end it; a close doesn't
: > "$T/run/asgard-standby"
press power
said wake "standby key"; nosuspend "standby key"
press lid open
said wake "standby lid open"
press lid close
said sleep "standby lid close (busy)"
echo ok
