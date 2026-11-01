#!/bin/sh
# spec: PWR-12
# A copy of sleep.d/asgard-pad-fix on fake /proc/interrupts and driver files, with sleep, systemctl and systemd-run stubbed:
# the wake hands the check to a timer, a healthy stream is left alone, a stalled one is re-probed with InputPlumber restarted,
# asgard.pad_fix=0 turns it off, asgard.pad_fix_log=0 turns its log off. That the real pad recovers is a device and human check.
set -e
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
H=$(dirname "$(readlink -f "$0")")/../sleep.d/asgard-pad-fix
mkdir -p "$T/bin" "$T/drv"
sed -e "s#^D=/sys/bus/serial/drivers/rsinput#D=$T/drv#" -e "s#/proc/interrupts#$T/interrupts#" -e "s#/dev/kmsg#$T/kmsg#" "$H" > "$T/hook"
irq() { printf '186:  %s  0  GICv3 494 Level qcom_geni_serial_uart2\n' "$1" > "$T/interrupts"; }
# sleep: time passing is the stream running, at its rate; once the driver has been bound, at the rate it recovers to.
cat > "$T/bin/sleep" <<S
#!/bin/sh
r=\$(cat $T/rate); [ -s $T/drv/bind ] && r=\$(cat $T/after)
n=\$(awk '{print \$2}' $T/interrupts)
printf '186:  %s  0  GICv3 494 Level qcom_geni_serial_uart2\n' \$((n + r)) > $T/interrupts
S
printf '#!/bin/sh\necho "$*" >> %s/systemctl.log\n' "$T" > "$T/bin/systemctl"
printf '#!/bin/sh\necho "$*" >> %s/run.log\n' "$T" > "$T/bin/systemd-run"
chmod +x "$T/bin"/*
PATH="$T/bin:$PATH"; export PATH
run() { LOG="$T/log" CFG="$T/cfg" sh "$T/hook" "$1"; }
reset() { : > "$T/cfg"; rm -f "$T/log" "$T/systemctl.log" "$T/run.log"; : > "$T/drv/bind"; : > "$T/drv/unbind"; irq 1000; }

# After a wake it hands the check to a timer, because systemd-suspend kills its children, and does nothing itself.
reset; echo 0 > "$T/rate"; echo 0 > "$T/after"
run post
grep -q "check$" "$T/run.log" && grep -q -- '--on-active=' "$T/run.log" || { echo "FAIL: no timer"; cat "$T/run.log"; exit 1; }
[ ! -s "$T/drv/unbind" ] || { echo "FAIL: re-probed inside the hook"; exit 1; }

# Healthy (~91 IRQ/s): left alone.
reset; echo 91 > "$T/rate"; echo 91 > "$T/after"
run check
[ ! -s "$T/drv/unbind" ] && [ ! -e "$T/systemctl.log" ] && [ ! -e "$T/log" ] || { echo "FAIL: touched a healthy pad"; exit 1; }

# Stalled, and the re-probe cures it: one unbind and bind of the pad, InputPlumber restarted, logged.
reset; echo 0 > "$T/rate"; echo 91 > "$T/after"
run check
[ "$(cat "$T/drv/unbind")" = serial1-0 ] && [ "$(cat "$T/drv/bind")" = serial1-0 ] || { echo "FAIL: re-probe"; exit 1; }
[ "$(cat "$T/systemctl.log")" = "restart inputplumber" ] || { echo "FAIL: InputPlumber"; cat "$T/systemctl.log"; exit 1; }
grep -q 'stalled (0 IRQ/s), re-probing rsinput (try 1)' "$T/log" && [ "$(wc -l < "$T/log")" = 1 ] || { echo "FAIL: log"; cat "$T/log"; exit 1; }

# Stays stalled: gives up after three tries, and says so.
reset; echo 0 > "$T/rate"; echo 0 > "$T/after"
run check
[ "$(wc -l < "$T/systemctl.log")" = 3 ] && grep -q 'still stalled after 3 re-probes' "$T/log" || { echo "FAIL: giving up"; cat "$T/log"; exit 1; }

# asgard.pad_fix_log=0: the fix runs, no log.
reset; printf 'asgard.pad_fix_log=0\n' > "$T/cfg"; echo 0 > "$T/rate"; echo 91 > "$T/after"
run check
[ -s "$T/drv/unbind" ] && [ ! -e "$T/log" ] || { echo "FAIL: pad_fix_log=0"; exit 1; }

# asgard.pad_fix=0: nothing at all, and the last line of the file wins.
reset; printf 'asgard.pad_fix=1\nasgard.pad_fix=0\n' > "$T/cfg"; echo 0 > "$T/rate"; echo 91 > "$T/after"
run post; run check
[ ! -e "$T/run.log" ] && [ ! -s "$T/drv/unbind" ] && [ ! -e "$T/log" ] || { echo "FAIL: pad_fix=0"; exit 1; }

# The default log is the one the spec names.
grep -q '^LOG=${LOG:-/storage/pad-fix.log}$' "$H" || { echo "FAIL: log path"; exit 1; }
echo OK
