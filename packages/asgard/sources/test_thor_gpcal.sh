#!/bin/bash
# spec: CAL-4
# ./test_thor_gpcal.sh: GPcal runs with InputPlumber stopped, and InputPlumber is restarted however GPcal ends.
set -e
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
mkdir -p "$T/bin" "$T/gpcal"
cat > "$T/bin/systemctl" <<'S'
#!/bin/sh
echo "systemctl $*" >> "$LOG"
S
cat > "$T/bin/python3" <<'S'
#!/bin/sh
echo "python3 $* in $(basename "$PWD")" >> "$LOG"
[ "$GPCAL_TEST" = fail ] && exit 1
[ "$GPCAL_TEST" = term ] && { : > "$T/running"; sleep 2; }
exit 0
S
echo 'sway_fullscreen() { :; }' > "$T/profile"
chmod +x "$T/bin/"*
run() {  # run <case>: thor-gpcal.sh with the stubs, its calls in $T/log
  : > "$T/log"
  LOG="$T/log" T="$T" GPCAL_TEST=$1 GPCAL_PROFILE="$T/profile" GPCAL_PATH="$T/gpcal" PATH="$T/bin:$PATH" \
    bash "$(dirname "$0")/thor-gpcal.sh" &
  pid=$!
  if [ "$1" = term ]; then
    for _ in $(seq 50); do [ -e "$T/running" ] && break; sleep .1; done
    kill -TERM "$pid"
  fi
  wait "$pid" || true
}
want="systemctl stop inputplumber
python3 main.py in gpcal
systemctl restart inputplumber"
for c in ok fail term; do
  run $c
  [ "$(cat "$T/log")" = "$want" ] || { echo "case $c:"; cat "$T/log"; exit 1; }
done
echo ok
