#!/bin/sh
# spec: LOG-2
# The marker says the last boot never shut down, and there is no snapshot of it (start moved the one before it to .prev).
set -e
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
mkdir -p "$T/base"; : > "$T/base/asgard-running"
BASE="$T/base" FREEZES="$T/freezes" sh "$(dirname "$(readlink -f "$0")")/asgard-lastboot.sh" start
ls "$T/freezes"/*.log >/dev/null 2>&1 || { echo "FAIL: no report for a boot with no snapshot"; exit 1; }
echo OK
