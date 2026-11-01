#!/bin/bash
# Asgard OS: run the host tests (docs/testing.md, levels 1 and 2). No Thor, no build, no root.
#   ./test.sh            run them all
#   ./test.sh <text>     run only the tests whose name contains <text>
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
FILTER=${1:-}
TIMEOUT=300  # the first Asgard Home test builds it
OUT=$(mktemp); trap 'rm -f "$OUT"' EXIT
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

run() {  # run <name> <spec ids> <command...>
  local name=$1 ids=$2 gap rc; shift 2
  gap=$(header "$SOURCES/$name" gap 2>/dev/null)
  (cd "$SOURCES" && timeout "$TIMEOUT" "$@") >"$OUT" 2>&1; rc=$?
  if [ -n "$gap" ] && [ $rc != 0 ]; then
    gaps=$((gaps + 1)); gapped+=("$name: $gap")
    printf 'GAP   %-28s %s\n' "$name" "$ids"
  elif [ -n "$gap" ]; then
    fail=$((fail + 1)); failed+=("$name")
    printf 'FAIL  %-28s %s (passes now: remove its gap header and the row in SPEC.md)\n' "$name" "$ids"
  elif [ $rc = 0 ]; then
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
[ "$fail" = 0 ] && [ ${#badlinks[@]} = 0 ] && [ "$uncovered" = 0 ]
