#!/bin/bash
# spec: CAL-4
# ./test_thor_stickcal.sh: stick calibration runs with InputPlumber stopped, which is restarted however it ends.
set -e
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
mkdir -p "$T/bin"
cat > "$T/bin/systemctl" <<'S'
#!/bin/sh
echo "systemctl $*" >> "$LOG"
S
cat > "$T/bin/python3" <<'S'
#!/bin/sh
echo "python3 $(basename "$1")" >> "$LOG"
[ "$STICKCAL_TEST" = fail ] && exit 1
[ "$STICKCAL_TEST" = term ] && { : > "$T/running"; sleep 2; }
exit 0
S
: > "$T/profile"
chmod +x "$T/bin/"*
run() {  # run <case>: thor-stickcal.sh with the stubs, its calls in $T/log
  : > "$T/log"; rm -f "$T/running"
  LOG="$T/log" T="$T" STICKCAL_TEST=$1 STICKCAL_PROFILE="$T/profile" PATH="$T/bin:$PATH" \
    bash "$(dirname "$0")/thor-stickcal.sh" &
  pid=$!
  if [ "$1" = term ]; then
    for _ in $(seq 50); do [ -e "$T/running" ] && break; sleep .1; done
    kill -TERM "$pid"
  fi
  wait "$pid" || true
}
want="systemctl stop inputplumber
python3 thor_stickcal.py
systemctl restart inputplumber"
for c in ok fail term; do
  run $c
  [ "$(cat "$T/log")" = "$want" ] || { echo "case $c:"; cat "$T/log"; exit 1; }
done
echo ok
