#!/bin/sh
# Keeps a failed game launch's log in /storage, the newest 20: runemu.sh's exec.log (this launch only), which the
# next launch overwrites. A crash's core dump, if it left one, is in /storage/.cache/cores (coredumpctl).
# Usage: asgard-crashlog.sh <rom> <system> <exit code>   (CRASH_DIR and EXEC_LOG override the paths, for the test)
DIR="${CRASH_DIR:-/storage/.config/thor/crashes}"
LOG="${EXEC_LOG:-/var/log/exec.log}"
mkdir -p "${DIR}" || exit 0
name=$(printf %s "$(basename "${1%.*}")" | tr -c 'A-Za-z0-9._-' _ | cut -c1-60)
out="${DIR}/$(date +%Y%m%d-%H%M%S)-${2}-${name}.log"
{
  echo "exit code: ${3}"
  [ "${3}" -gt 128 ] 2>/dev/null && echo "signal: SIG$(kill -l $((${3} - 128)))"
  cat "${LOG}"
} >"${out}"
ls -1t "${DIR}"/*.log | tail -n +21 | while read -r f; do rm -f "${f}"; done
