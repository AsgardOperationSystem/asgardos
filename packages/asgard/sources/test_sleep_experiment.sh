#!/bin/sh
# spec: LOG-5
# Fake sysfs and a stub rfkill for sleep.d/asgard-sleep-audit: the radio under test is blocked for the sleep and unblocked
# after, each suspect on its own, and nothing is touched with no experiment set or with the audit off.
# test_sleep_audit.sh (LOG-4) checks what the CSV records about it.
set -e
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
H=$(dirname "$(readlink -f "$0")")/../sleep.d/asgard-sleep-audit
mkdir -p "$T/bin" "$T/class/rfkill/rfkill0" "$T/class/rfkill/rfkill1"
echo wlan > "$T/class/rfkill/rfkill0/type"; echo bluetooth > "$T/class/rfkill/rfkill1/type"
printf '#!/bin/sh\necho "$*" >> %s/rfkill.log\n' "$T" > "$T/bin/rfkill"; chmod +x "$T/bin/rfkill"
PATH="$T/bin:$PATH"; export PATH
run() { SYS="$T" PROC="$T" OUT="$T/out.csv" CFG="$T/cfg" SNAP="$T/snap" DUMPS="$T/dumps" PLAYING="$T/playing" TR="$T/tr" sh "$H" "$1"; }
# case <cfg line> <what rfkill must have been told at pre> <... at post>
sleep_with() {
  printf 'asgard.sleep_audit=1\n%s\n' "$1" > "$T/cfg"; rm -f "$T/rfkill.log"
  run pre
  [ "$(cat "$T/rfkill.log" 2>/dev/null | tr '\n' ,)" = "$2" ] || { echo "FAIL: $1: at sleep: $(cat "$T/rfkill.log" 2>/dev/null)"; exit 1; }
  rm -f "$T/rfkill.log"
  run post
  [ "$(cat "$T/rfkill.log" 2>/dev/null | tr '\n' ,)" = "$3" ] || { echo "FAIL: $1: at wake: $(cat "$T/rfkill.log" 2>/dev/null)"; exit 1; }
}
echo 0 > "$T/class/rfkill/rfkill0/soft"; echo 0 > "$T/class/rfkill/rfkill1/soft"
sleep_with asgard.sleep_experiment=wifi "block wlan," "unblock wlan,"
sleep_with asgard.sleep_experiment=bt "block bluetooth," "unblock bluetooth,"
sleep_with asgard.sleep_experiment= "" ""
# Airplane mode had Wi-Fi off: the experiment leaves it off after the sleep.
echo 1 > "$T/class/rfkill/rfkill0/soft"
sleep_with asgard.sleep_experiment=wifi "" ""
echo 0 > "$T/class/rfkill/rfkill0/soft"
# The audit off means no experiment either.
printf 'asgard.sleep_audit=0\nasgard.sleep_experiment=wifi\n' > "$T/cfg"; rm -f "$T/rfkill.log"
run pre; run post
[ ! -e "$T/rfkill.log" ] || { echo "FAIL: radios touched with the audit off"; exit 1; }
echo OK
