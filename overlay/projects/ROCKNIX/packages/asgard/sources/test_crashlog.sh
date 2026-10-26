#!/bin/sh
# asgard-crashlog.sh: the log is kept with its exit code and signal, the name is safe, only the newest 20 stay.
set -e
T=$(mktemp -d)
trap 'rm -rf "${T}"' EXIT
export CRASH_DIR="${T}/crashes" EXEC_LOG="${T}/exec.log" SAVE_MARKER="${T}/save-log"
touch "${SAVE_MARKER}"
echo "emulator output" >"${EXEC_LOG}"
for i in $(seq 25); do touch -d "@$((1000 + i))" "${CRASH_DIR}/old${i}.log" 2>/dev/null || { mkdir -p "${CRASH_DIR}"; touch -d "@$((1000 + i))" "${CRASH_DIR}/old${i}.log"; }; done
sh "$(dirname "$0")/asgard-crashlog.sh" "/storage/roms/wii/Zelda: TP (USA).iso" wii 139
f=$(ls "${CRASH_DIR}"/*-wii-*.log)
case "${f}" in *-wii-Zelda__TP__USA_.log) ;; *) echo "bad name: ${f}"; exit 1 ;; esac
grep -q "^exit code: 139$" "${f}" && grep -q "^signal: SIGSEGV$" "${f}" && grep -q "emulator output" "${f}"
[ "$(ls "${CRASH_DIR}" | wc -l)" = 20 ] || { echo "kept $(ls "${CRASH_DIR}" | wc -l), want 20"; exit 1; }
[ -e "${CRASH_DIR}/old25.log" ] && [ ! -e "${CRASH_DIR}/old6.log" ]   # oldest dropped first
[ ! -e "${SAVE_MARKER}" ] || { echo "marker not used up"; exit 1; }
echo ok
