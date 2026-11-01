#!/bin/sh
# Freeze reports. start (boot): if the last boot never shut down (its marker is still there: a freeze, a crash
# reboot, a dead battery), its last journal snapshot becomes /storage/.config/thor/freezes/<time>.log (the newest
# 10); either way that snapshot is kept as the previous boot's journal (journalctl -D /storage/.cache/asgard-journal.prev).
# stop (clean shutdown): a last snapshot, and the marker goes. The warnings up to the freeze: logs/events.log.
# BASE and FREEZES override the paths (the test).
BASE="${BASE:-/storage/.cache}"
FREEZES="${FREEZES:-/storage/.config/thor/freezes}"
MARK="${BASE}/asgard-running" SNAP="${BASE}/asgard-journal"
case "$1" in
  start)
    if [ -e "${MARK}" ] && [ ! -d "${SNAP}" ]; then
      # It froze before its first sleep, game launch or shutdown, so it left no journal, but it still gets a report.
      mkdir -p "${FREEZES}"
      { echo "The boot before $(date '+%Y-%m-%d %H:%M') never shut down, and froze before its first journal snapshot."
        echo "Its warnings are in /storage/.config/thor/logs/events.log."; } >"${FREEZES}/$(date +%Y%m%d-%H%M%S).log"
      ls -1t "${FREEZES}"/*.log | tail -n +11 | while read -r f; do rm -f "${f}"; done
    fi
    if [ -e "${MARK}" ] && [ -d "${SNAP}" ]; then
      mkdir -p "${FREEZES}"
      out="${FREEZES}/$(date -r "${SNAP}" +%Y%m%d-%H%M%S).log"
      { echo "The boot before $(date '+%Y-%m-%d %H:%M') never shut down. Its journal up to the last snapshot"
        echo "($(date -r "${SNAP}" '+%Y-%m-%d %H:%M:%S')); the warnings after it are in /storage/.config/thor/logs/events.log."
        echo
        journalctl -D "${SNAP}" -o short-iso --no-pager 2>&1; } >"${out}"
      ls -1t "${FREEZES}"/*.log | tail -n +11 | while read -r f; do rm -f "${f}"; done
    fi
    if [ -d "${SNAP}" ]; then
      rm -rf "${SNAP}.prev"
      mv "${SNAP}" "${SNAP}.prev"
    fi
    touch "${MARK}"
    sync -f "${MARK}"
    ;;
  stop)
    SNAP="${SNAP}" /usr/share/asgard/asgard-journal-snap.sh
    rm -f "${MARK}"
    sync -f "${BASE}"
    ;;
esac
exit 0
