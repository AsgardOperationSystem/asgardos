#!/bin/sh
# spec: LOG-2
# A copy of asgard-lastboot.sh and asgard-journal-snap.sh, journalctl stubbed: a boot that took a snapshot and never shut down
# leaves a report with its journal, only the newest 10 stay, and a clean shutdown leaves none.
# A boot that froze before its first snapshot is test_lastboot_no_snapshot.sh.
set -e
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
H=$(dirname "$(readlink -f "$0")")
mkdir -p "$T/bin" "$T/base" "$T/runlog"
printf '#!/bin/sh\n[ "$1" = --sync ] || echo "the journal: $*"\n' > "$T/bin/journalctl"; chmod +x "$T/bin/journalctl"
PATH="$T/bin:$PATH"; export PATH
sed "s#/run/log/journal#$T/runlog#" "$H/asgard-journal-snap.sh" > "$T/snap.sh"
sed "s#/usr/share/asgard/asgard-journal-snap.sh#sh $T/snap.sh#" "$H/asgard-lastboot.sh" > "$T/lastboot.sh"
export BASE="$T/base" FREEZES="$T/freezes"
SNAP="$T/base/asgard-journal"
lastboot() { sh "$T/lastboot.sh" "$1"; }
snap() { SNAP="$SNAP" sh "$T/snap.sh"; }
reports() { ls "$T/freezes" 2>/dev/null | wc -l; }

# A first boot, and a clean shutdown: no report, the marker comes and goes.
lastboot start
[ -e "$T/base/asgard-running" ] || { echo "FAIL: no marker while running"; exit 1; }
echo first > "$T/runlog/j"; snap
[ "$(cat "$SNAP/j")" = first ] || { echo "FAIL: snapshot"; exit 1; }
lastboot stop
[ ! -e "$T/base/asgard-running" ] || { echo "FAIL: marker left after a shutdown"; exit 1; }
[ -d "$SNAP" ] || { echo "FAIL: no last snapshot at shutdown"; exit 1; }
lastboot start
[ "$(reports)" = 0 ] || { echo "FAIL: a report after a clean shutdown"; exit 1; }
[ -e "$SNAP.prev/j" ] || { echo "FAIL: the previous boot's journal isn't kept"; exit 1; }

# A boot with a snapshot that never shut down: its journal is the report.
echo second > "$T/runlog/j"; snap
lastboot start
[ "$(reports)" = 1 ] || { echo "FAIL: no report after a boot that never shut down"; exit 1; }
R=$(ls "$T/freezes"/*.log)
grep -q "never shut down" "$R" && grep -q "the journal: -D $SNAP" "$R" || { echo "FAIL: report text"; cat "$R"; exit 1; }
[ -e "$T/base/asgard-running" ] || { echo "FAIL: no marker for this boot"; exit 1; }

# The newest 10 stay: this boot's report is one of them, the oldest go.
rm -f "$T/freezes"/*
i=10; while [ $i -lt 22 ]; do : > "$T/freezes/old$i.log"; touch -d "2026-01-$i 12:00" "$T/freezes/old$i.log"; i=$((i + 1)); done
snap
lastboot start
[ "$(reports)" = 10 ] || { echo "FAIL: $(reports) reports kept"; exit 1; }
[ ! -e "$T/freezes/old10.log" ] && [ -e "$T/freezes/old21.log" ] || { echo "FAIL: not the newest"; ls "$T/freezes"; exit 1; }
[ "$(ls -1t "$T/freezes" | head -1)" != old21.log ] || { echo "FAIL: this boot's report went"; exit 1; }

# A failed copy keeps the last snapshot.
echo third > "$T/runlog/j"; snap; rm -rf "$T/runlog"; snap
[ "$(cat "$SNAP/j")" = third ] || { echo "FAIL: a failed copy lost the snapshot"; exit 1; }

# The service runs this at boot and shutdown, and the sleep hook snapshots before a sleep.
U="$H/../system.d/asgard-lastboot.service"
grep -qx 'ExecStart=/usr/share/asgard/asgard-lastboot.sh start' "$U" && grep -qx 'ExecStop=/usr/share/asgard/asgard-lastboot.sh stop' "$U" ||
  { echo "FAIL: unit"; exit 1; }
grep -q '^\[ "$1" = pre \] && /usr/share/asgard/asgard-journal-snap.sh' "$H/../sleep.d/asgard-journal-snap" || { echo "FAIL: sleep hook"; exit 1; }
echo OK
