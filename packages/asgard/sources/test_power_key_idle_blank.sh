#!/bin/sh
# spec: PWR-10
# requires: cmd:bash
# The power key wakes screens that are off, instead of suspending: all of them off in sway (Home's X), or blanked by
# thor-idle-blank.py, which also wakes on this press, so sway may already show them lit. When sway can't answer, it suspends.
set -e
T=$(mktemp -d); trap 'kill $R 2>/dev/null || true; rm -rf "$T"' EXIT
Q=$(dirname "$(readlink -f "$0")")/../../hardware/quirks/platforms/SM8550
mkdir -p "$T/bin" "$T/run"
printf 'get_setting() { echo mem; }\nlog() { :; }\n' > "$T/profile"
printf '#!/bin/sh\necho "$*" >> %s/suspend.log\n' "$T" > "$T/bin/systemctl"
cat > "$T/bin/swaymsg" <<S
#!/bin/sh
case "\$*" in *get_outputs*) exec cat $T/outputs ;; esac
echo "\$*" >> $T/sway.log
S
chmod +x "$T/bin"/*
sed -e "s#^\. /etc/profile#. $T/profile#" -e "s#/run/#$T/run/#g" -e "s#/usr/bin/external-display#$T/bin/none#" \
    -e "s#/sys/class/#$T/sys/class/#g" "$Q/bin/power-handler" > "$T/handler"
press() { rm -f "$T/suspend.log" "$T/sway.log"; PATH="$T/bin:$PATH" bash "$T/handler" power; }
suspended() { [ -e "$T/suspend.log" ]; }
OFF='[{"name":"DSI-1","power":false},{"name":"DSI-2","power": false}]'
LIT='[{"name":"DSI-1","power":false},{"name":"DSI-2","power": true}]'

# Every output off: wakes them, and tells Home, whose X state has to follow.
mkfifo "$T/run/asgard-home.cmd"
cat "$T/run/asgard-home.cmd" > "$T/home.log" & R=$!
echo "$OFF" > "$T/outputs"; press
suspended && { echo "FAIL: the press suspended with the screens off"; exit 1; }
command grep -q 'power on' "$T/sway.log" || { echo "FAIL: the screens weren't woken"; exit 1; }
wait $R; command grep -qx screens-on "$T/home.log" || { echo "FAIL: Home wasn't told"; exit 1; }
rm "$T/run/asgard-home.cmd"

# Home isn't there to read the command: it still wakes the screens, and doesn't hang.
press
command grep -q 'power on' "$T/sway.log" || { echo "FAIL: no Home, no wake"; exit 1; }

# The idle blanker has already woken them for this press: its marker says so, once.
echo "$LIT" > "$T/outputs"; touch "$T/run/asgard-idle-blanked"; press
suspended && { echo "FAIL: suspended on the press that woke the idle blank"; exit 1; }
[ ! -e "$T/run/asgard-idle-blanked" ] || { echo "FAIL: the marker was left"; exit 1; }
press
suspended || { echo "FAIL: the next press, with the screens lit, didn't suspend"; exit 1; }

# A game keeping the screens off for itself is still the blanker's marker first, and the setting off doesn't get in the way.
touch "$T/run/asgard-idle-blanked"; touch "$T/run/asgard-keep-running"; press
suspended && { echo "FAIL: keep-running suspended"; exit 1; }
rm -f "$T/run/asgard-keep-running"

# sway can't answer: not proof the screens are off, so the key still sleeps the Thor.
: > "$T/outputs"; press
suspended || { echo "FAIL: no answer from sway must not stop the key suspending"; exit 1; }
echo OK
