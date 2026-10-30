#!/bin/sh
# Copies the RAM journal (/run/log/journal, the newest 8 MB) to /storage, replacing the last copy: run before sleep,
# at each game's launch and exit, and at shutdown, so a freeze leaves the boot's log up to the last of those.
# asgard-lastboot.sh files it as a freeze report if the boot never shut down. SNAP overrides the path (the test).
SNAP="${SNAP:-/storage/.cache/asgard-journal}"
journalctl --sync 2>/dev/null
rm -rf "${SNAP}.new"
cp -r /run/log/journal "${SNAP}.new" && sync -f "${SNAP}.new" || exit 0
rm -rf "${SNAP}"
mv "${SNAP}.new" "${SNAP}"
