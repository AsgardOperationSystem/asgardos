#!/bin/sh
# spec: PWR-10
# requires: cmd:bash
# gap: power-handler only knows its own blank flag, so a press with the screens off from thor-idle-blank.py suspends, instead of waking them.
# sway says every output is off, as the idle timer leaves it; the press must not suspend.
set -e
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
Q=$(dirname "$(readlink -f "$0")")/../../hardware/quirks/platforms/SM8550
mkdir -p "$T/bin" "$T/run"
printf 'get_setting() { echo mem; }\nlog() { :; }\n' > "$T/profile"
printf '#!/bin/sh\necho "$*" >> %s/suspend.log\n' "$T" > "$T/bin/systemctl"
cat > "$T/bin/swaymsg" <<'S'
#!/bin/sh
case "$*" in *get_outputs*) echo '[{"name":"DSI-1","power":false,"dpms":false},{"name":"DSI-2","power":false,"dpms":false}]' ;; esac
S
chmod +x "$T/bin"/*
sed -e "s#^\. /etc/profile#. $T/profile#" -e "s#/run/#$T/run/#g" -e "s#/usr/bin/external-display#$T/bin/none#" \
    -e "s#/sys/class/#$T/sys/class/#g" "$Q/bin/power-handler" > "$T/handler"
PATH="$T/bin:$PATH" bash "$T/handler" power
[ ! -e "$T/suspend.log" ] || { echo "FAIL: the press suspended with the screens off"; exit 1; }
echo OK
