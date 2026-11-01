#!/bin/bash
# Asgard OS: run the host tests (docs/testing.md, levels 1 and 2). No Thor, no build, no root.
#   ./test.sh            run them all
#   ./test.sh <text>     run only the tests whose name contains <text>
# Exit code: 1 if anything failed, else 0. A skipped test isn't a pass: it's listed with the reason.
#
# A test is packages/asgard/sources/test_*. Its first lines say what it checks and what it needs:
#   # spec: PWR-5                  the SPEC.md rules it checks
#   # requires: cmd:cc lib:libX.so a program on PATH, or a library ldconfig knows; without them it's skipped
set -uo pipefail
cd "$(dirname "$0")"
SOURCES=packages/asgard/sources
FILTER=${1:-}
TIMEOUT=120
OUT=$(mktemp); trap 'rm -f "$OUT"' EXIT
export PYTHONDONTWRITEBYTECODE=1

pass=0 fail=0 skip=0
failed=() skipped=() uncited=() badlinks=()

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
      *) printf '%s ' "$need" ;;
    esac
  done
}

run() {  # run <name> <spec ids> <command...>
  local name=$1 ids=$2 rc; shift 2
  (cd "$SOURCES" && timeout "$TIMEOUT" "$@") >"$OUT" 2>&1; rc=$?
  if [ $rc = 0 ]; then
    pass=$((pass + 1)); printf 'PASS  %-28s %s\n' "$name" "$ids"
  else
    fail=$((fail + 1)); failed+=("$name")
    [ $rc = 124 ] && echo "timed out after ${TIMEOUT}s" >>"$OUT"
    printf 'FAIL  %-28s %s (exit %s)\n' "$name" "$ids" "$rc"
    tail -n 15 "$OUT" | sed 's/^/      /'
  fi
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
    printf 'SKIP  %-28s %s\n' "$name" "$ids"
    continue
  fi
  case $name in
    *.py) run "$name" "$ids" python3 "$name" ;;
    *.sh) run "$name" "$ids" sh "$name" ;;
    *) fail=$((fail + 1)); failed+=("$name"); echo "FAIL  $name: not .py or .sh, can't run it" ;;
  esac
done

# Self-checks built into a script instead of a test_ file.
if selected asgard_config; then
  run "asgard_config.py --test" "CFG-1 CFG-3" python3 asgard_config.py --test
fi

echo
[ ${#skipped[@]} = 0 ] || { echo "Skipped, not tested:"; printf '  %s\n' "${skipped[@]}"; }
[ ${#uncited[@]} = 0 ] || { echo "No spec rule cited:"; printf '  %s\n' "${uncited[@]}"; }
[ ${#badlinks[@]} = 0 ] || { echo "Broken links to the spec:"; printf '  %s\n' "${badlinks[@]}"; }
echo "$pass passed, $fail failed, $skip skipped"
[ "$fail" = 0 ] && [ ${#badlinks[@]} = 0 ]
