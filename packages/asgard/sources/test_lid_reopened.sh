#!/bin/sh
# spec: PWR-13
# requires: cmd:bash
# A lid opened while the Thor is still going to sleep cancels the sleep. Copies of the SM8550 power-handler, the
# lid-reopened helper and the 001-suspend-grace / 999-lid-reopened / post 000-lid-reopened hooks, their paths
# rewritten, busctl and the clocks stubbed: power-handler notes a lid close and forgets it on an open outside a sleep;
# with the close noted and the lid open again, the grace hold ends early and the last hook arms wakeup_count and an
# RTC alarm 2 s out; a sleep from the menu with the lid open, or a close noted over a minute ago, leaves both alone.
# That the kernel then cancels the suspend or wakes right after is a device check.
set -e
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
H=$(dirname "$(readlink -f "$0")")/../..
Q=$H/hardware/quirks/platforms/SM8550
mkdir -p "$T/bin" "$T/q" "$T/run" "$T/sys/power" "$T/sys/class/rtc/rtc0"
printf 'get_setting() { echo 1; }\nlog() { echo "$*" >> %s/log; }\n' "$T" > "$T/profile"
# busctl: LidClosed from $T/lid, PreparingForSleep from $T/preparing
cat > "$T/bin/busctl" <<S
#!/bin/sh
case "\$*" in
  *LidClosed) echo "b \$(cat $T/lid)" ;;
  *PreparingForSleep) echo "b \$(cat $T/preparing)" ;;
esac
S
printf '#!/bin/sh\nexit 0\n' > "$T/bin/pactl"
printf '#!/bin/sh\n' > "$T/bin/sleep"   # the grace hold counts loops through the fake clock instead
chmod +x "$T/bin"/*
rw() { sed -e "s#^\. /etc/profile#. $T/profile#" -e "s#/run/#$T/run/#g" -e "s#/proc/uptime#$T/uptime#g" \
           -e "s#/proc/timer_list#$T/timer_list#g" "$1" > "$2"; chmod +x "$2"; }
rw "$Q/bin/power-handler" "$T/handler"
rw "$Q/bin/lid-reopened" "$T/q/lid-reopened"
rw "$Q/sleep.d/pre/001-suspend-grace" "$T/grace"
rw "$Q/sleep.d/pre/999-lid-reopened" "$T/last"
rw "$Q/sleep.d/post/000-lid-reopened" "$T/post"
env() { PATH="$T/bin:$PATH" SYS="$T/sys" RUN="$T/run" UPTIME="$T/uptime" QUIRK_BIN="$T/q" "$@"; }
reset() { echo 3558 > "$T/sys/power/wakeup_count"; : > "$T/sys/class/rtc/rtc0/wakealarm"; rm -f "$T/run/.lid-reopened-alarm"; }
armed() { [ "$(cat "$T/sys/class/rtc/rtc0/wakealarm")" = +2 ] && [ -e "$T/run/.lid-reopened-alarm" ]; }

# power-handler notes a close; an open outside a sleep forgets it, an open while logind prepares one keeps it
echo 100.42 > "$T/uptime"; echo false > "$T/preparing"
env bash "$T/handler" lid close
[ "$(cat "$T/run/.lid-closed-at")" = 100 ] || { echo "FAIL: the close wasn't noted"; exit 1; }
env bash "$T/handler" lid open
[ ! -e "$T/run/.lid-closed-at" ] || { echo "FAIL: an open outside a sleep kept the close"; exit 1; }
env bash "$T/handler" lid close; echo true > "$T/preparing"
env bash "$T/handler" lid open
[ -e "$T/run/.lid-closed-at" ] || { echo "FAIL: an open during a sleep forgot the close"; exit 1; }

# the sleep began with the lid closing, and it's open again: armed, and the alarm set
echo 105 > "$T/uptime"; echo false > "$T/lid"; reset
env sh "$T/last"
armed || { echo "FAIL: the lid open again didn't set the alarm"; cat "$T/sys/class/rtc/rtc0/wakealarm"; exit 1; }
[ "$(cat "$T/sys/power/wakeup_count")" = 3558 ] || { echo "FAIL: wakeup_count not armed"; exit 1; }
grep -q 'cancelling the sleep' "$T/log" || { echo "FAIL: not logged"; exit 1; }

# after the wake the post hook clears the alarm and the note
env sh "$T/post"
[ "$(cat "$T/sys/class/rtc/rtc0/wakealarm")" = 0 ] && [ ! -e "$T/run/.lid-closed-at" ] && [ ! -e "$T/run/.lid-reopened-alarm" ] ||
  { echo "FAIL: post left the alarm or the note"; exit 1; }

# still closed: nothing to cancel
echo 100 > "$T/run/.lid-closed-at"; echo true > "$T/lid"; reset
env sh "$T/last"
! armed || { echo "FAIL: armed with the lid closed"; exit 1; }

# no close noted (a sleep from the menu with the lid open), or one over a minute ago: left alone
rm -f "$T/run/.lid-closed-at"; echo false > "$T/lid"; reset
env sh "$T/last"
! armed || { echo "FAIL: a sleep with no lid close was cancelled"; exit 1; }
echo 30 > "$T/run/.lid-closed-at"; reset
env sh "$T/last"
! armed || { echo "FAIL: a stale lid close cancelled the sleep"; exit 1; }

# the grace hold: 15 s left on the fake clock; it would loop 15 times, but the lid open again ends it at once
cat > "$T/bin/awk" <<S
#!/bin/sh
n=\$(cat $T/ticks 2>/dev/null || echo 0); echo \$((n + 1)) > $T/ticks; echo \$((1000 + n))
S
chmod +x "$T/bin/awk"
echo 1000 > "$T/run/.last_resume_monotonic"; : > "$T/timer_list"
echo 100 > "$T/run/.lid-closed-at"; echo false > "$T/lid"; rm -f "$T/ticks"
env timeout 10 sh "$T/grace"
[ "$(cat "$T/ticks")" -le 3 ] || { echo "FAIL: the grace hold didn't end on the lid open ($(cat "$T/ticks") clock reads)"; exit 1; }
echo true > "$T/lid"; rm -f "$T/ticks"
env timeout 10 sh "$T/grace"
[ "$(cat "$T/ticks")" -ge 15 ] || { echo "FAIL: the grace hold ended with the lid closed"; exit 1; }
echo "PASS"
