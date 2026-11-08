#!/bin/bash
# Asgard OS: run the host tests (docs/testing.md, levels 1 and 2). No Thor, no build, no root.
#   ./test.sh            run them all
#   ./test.sh <text>     run only the tests whose name contains <text>
#   ./test.sh -j <n> ...  run at most <n> at once (default: $TEST_JOBS, else 8); -j 1 runs them one at a time
# Results print in file order however the tests finish. Each test gets its own folder, <run>/<name>/, holding output.log and
# the tmp/ that is its TMPDIR, so tests and simultaneous runs can't collide. <run> is under $TEST_PREFIX, by default
# build/test/runs (DEV-11). It's deleted unless something failed, and then it's kept, and named at the end.
# Exit code: 1 if anything failed, else 0. A skipped test isn't a pass: it's listed with the reason.
#
# A test is packages/asgard/sources/test_*. Its first lines say what it checks and what it needs:
#   # spec: PWR-5                  the SPEC.md rules it checks
#   # requires: cmd:cc lib:libX.so a program on PATH, a library ldconfig knows, or file:<path from the repo root>;
#                                  without them it's skipped
#   # gap: <why>                   it fails today because of a row in SPEC.md's known gaps: reported, doesn't fail the
#                                  run, and fails the run once it passes, so the header and the row get removed
# It ends by counting the spec's rules against test_*, test-device.sh and docs/human-checks.md; a rule in none is a failure.
set -uo pipefail
cd "$(dirname "$0")"
SOURCES=packages/asgard/sources
JOBS=${TEST_JOBS:-8}
case ${1:-} in
  -j) JOBS=${2:-}; shift; [ $# = 0 ] || shift ;;
  -j*) JOBS=${1#-j}; shift ;;
esac
[[ $JOBS =~ ^[1-9][0-9]*$ ]] || { echo "test.sh: -j needs a number above 0, not '$JOBS'" >&2; exit 2; }
FILTER=${1:-}
TIMEOUT=300  # the first Asgard Home test builds it
PREFIX=${TEST_PREFIX:-build/test/runs}
mkdir -p "$PREFIX"
find "$PREFIX" -mindepth 1 -maxdepth 1 -type d -name 'run.*' -mtime +1 -exec rm -rf {} +  # kept by old failures
RUN=$(realpath "$(mktemp -d "$PREFIX/run.XXXXXX")")
interrupted() {  # timeout puts a test in its own process group, so Ctrl-C doesn't reach it
  local worker
  for worker in $(jobs -p); do pkill -TERM -P "$worker"; kill "$worker" 2>/dev/null; done
  rm -rf "$RUN"
  exit 130
}
trap interrupted INT TERM
export PYTHONDONTWRITEBYTECODE=1

pass=0 fail=0 skip=0 gaps=0
failed=() skipped=() uncited=() badlinks=() gapped=()

known_id() { command grep -qE "^- \*\*$1\*\* " SPEC.md; }

header() {  # header <file> <key>: the value of its "# key: ..." line, in the first lines
  sed -n "1,5s/^# $2: //p" "$1"
}

missing_needs() {  # missing_needs <needs...>: prints the ones this machine lacks
  local need libs
  libs=$(ldconfig -p 2>/dev/null)
  for need in "$@"; do
    case $need in
      cmd:*) command -v "${need#cmd:}" >/dev/null || printf '%s ' "$need" ;;
      lib:*) case $libs in *"${need#lib:} "*) ;; *) printf '%s ' "$need" ;; esac ;;
      file:*) [ -e "${need#file:}" ] || printf '%s ' "$need" ;;
      *) printf '%s ' "$need" ;;
    esac
  done
}

queue=() shown=0

start() {  # start <name> <spec ids> <command...>: runs it in the background, once a place is free
  local name=$1 ids=$2 dir="$RUN/$1"; shift 2
  queue+=("run|$name|$ids")
  while [ "$(jobs -rp | wc -l)" -ge "$JOBS" ]; do wait -n 2>/dev/null; show; done
  mkdir -p "$dir/tmp"
  {
    (cd "$SOURCES" && TMPDIR="$dir/tmp" timeout "$TIMEOUT" "$@") >"$dir/output.log" 2>&1 </dev/null
    echo $? >"$dir/rc.part"; mv "$dir/rc.part" "$dir/rc"
  } &
}

report() {  # report <name> <spec ids> <exit code> <its output>
  local name=$1 ids=$2 rc=$3 out=$4 gap
  gap=$(header "$SOURCES/$name" gap 2>/dev/null)
  if [ -n "$gap" ] && [ "$rc" != 0 ]; then
    gaps=$((gaps + 1)); gapped+=("$name: $gap")
    printf 'GAP   %-28s %s\n' "$name" "$ids"
  elif [ -n "$gap" ]; then
    fail=$((fail + 1)); failed+=("$name")
    printf 'FAIL  %-28s %s (passes now: remove its gap header and the row in SPEC.md)\n' "$name" "$ids"
  elif [ "$rc" = 0 ]; then
    pass=$((pass + 1)); printf 'PASS  %-28s %s\n' "$name" "$ids"
  else
    fail=$((fail + 1)); failed+=("$name")
    [ "$rc" = 124 ] && echo "timed out after ${TIMEOUT}s" >>"$out"
    printf 'FAIL  %-28s %s (exit %s)\n' "$name" "$ids" "$rc"
    tail -n 15 "$out" | sed 's/^/      /'
  fi
}

show() {  # Prints what's ready, in queue order: it stops at the first test still running.
  local kind name ids
  while [ "$shown" -lt "${#queue[@]}" ]; do
    IFS='|' read -r kind name ids <<<"${queue[$shown]}"
    case $kind in
      run) [ -e "$RUN/$name/rc" ] || return 0; report "$name" "$ids" "$(cat "$RUN/$name/rc")" "$RUN/$name/output.log" ;;
      skip) printf 'SKIP  %-28s %s\n' "$name" "$ids" ;;
      bad) fail=$((fail + 1)); failed+=("$name"); echo "FAIL  $name: not .py or .sh, can't run it" ;;
    esac
    shown=$((shown + 1))
  done
}

selected() { [ -z "$FILTER" ] || [[ $1 == *"$FILTER"* ]]; }

for file in "$SOURCES"/test_*; do
  name=$(basename "$file")
  selected "$name" || continue
  ids=$(header "$file" spec)
  # shellcheck disable=SC2046  # needs are space-separated words
  lacking=$(missing_needs $(header "$file" requires))
  [ -n "$ids" ] || uncited+=("$name")
  for id in $ids; do known_id "$id" || badlinks+=("$name cites $id, which isn't in SPEC.md"); done
  if [ -n "$lacking" ]; then
    skip=$((skip + 1)); skipped+=("$name: missing ${lacking% }")
    queue+=("skip|$name|$ids")
    continue
  fi
  case $name in
    *.py) start "$name" "$ids" python3 "$name" ;;
    *.sh) start "$name" "$ids" sh "$name" ;;
    *) queue+=("bad|$name|") ;;
  esac
done

# Self-checks built into a script instead of a test_ file.
if selected asgard_config; then
  start "asgard_config.py --test" "CFG-1 CFG-3" python3 asgard_config.py --test
fi
while [ "$(jobs -rp | wc -l)" -gt 0 ]; do wait -n 2>/dev/null; show; done
wait
show

echo
[ ${#skipped[@]} = 0 ] || { echo "Skipped, not tested:"; printf '  %s\n' "${skipped[@]}"; }
[ ${#gapped[@]} = 0 ] || { echo "Known gaps, failing as expected:"; printf '  %s\n' "${gapped[@]}"; }
[ ${#uncited[@]} = 0 ] || { echo "No spec rule cited:"; printf '  %s\n' "${uncited[@]}"; }
[ ${#badlinks[@]} = 0 ] || { echo "Broken links to the spec:"; printf '  %s\n' "${badlinks[@]}"; }
echo "$pass passed, $fail failed, $gaps known gaps, $skip skipped"

# Which rules have a check, and at what level. A device or human check is only written down here: it counts as run only
# when someone has run it on a Thor (docs/testing.md).
uncovered=0
if [ -z "$FILTER" ]; then
  rules=$(command grep -oE '^- \*\*[A-Z]+-[0-9]+\*\*' SPEC.md | command grep -oE '[A-Z]+-[0-9]+' | sort -u)
  in_host=$( { for file in "$SOURCES"/test_*; do header "$file" spec; done; echo CFG-1 CFG-3; } | tr ' ' '\n' | sort -u)
  in_device=$(sed -n 's/^check "\([^"]*\)".*/\1/p' test-device.sh 2>/dev/null | tr ' ' '\n' | sort -u)
  in_human=$(sed -n 's/^| \([A-Z][-A-Z0-9 ]*[0-9]\) |.*/\1/p' docs/human-checks.md 2>/dev/null | tr ' ' '\n' | sort -u)
  host_only=0 device_only=0 human_only=0 none=()
  for rule in $rules; do
    if command grep -qx "$rule" <<<"$in_host"; then host_only=$((host_only + 1))
    elif command grep -qx "$rule" <<<"$in_device"; then device_only=$((device_only + 1))
    elif command grep -qx "$rule" <<<"$in_human"; then human_only=$((human_only + 1))
    else none+=("$rule"); fi
  done
  uncovered=${#none[@]}
  echo "Spec: $(wc -w <<<"$rules") rules: $host_only with a host test, $device_only with only a device check, $human_only with only a human check, $uncovered with none"
  [ "$uncovered" = 0 ] || echo "  no check: ${none[*]}"
fi
if [ "$fail" = 0 ]; then rm -rf "$RUN"; else echo "Each test's output and temp files: $RUN"; fi
[ "$fail" = 0 ] && [ ${#badlinks[@]} = 0 ] && [ "$uncovered" = 0 ]
