#!/bin/sh
# spec: CFG-4
# requires: cmd:g++
# Home's writer of system.cfg (asgard-home/src/settings_file.h), compiled as it ships: replaces in place, keeps comments
# and blank lines, leaves a per-game key alone, removes on empty, and refuses to write if it can't read the old file.
set -e
T=$(mktemp -d); trap 'chmod -R u+rwx "$T" 2>/dev/null; rm -rf "$T"' EXIT
HERE=$(cd "$(dirname "$0")" && pwd)
cat > "$T/main.cpp" <<'CPP'
#include "settings_file.h"
int main(int, char **a) { return writeSetting(a[1], a[2], a[3], a[4]) ? 0 : 1; }
CPP
g++ -std=c++17 -I"$HERE/../../asgard-home/src" "$T/main.cpp" -o "$T/w"
C="$T/system.cfg"; L="$T/lock"
same() { [ "$(cat "$C")" = "$1" ] || { echo "FAIL: $2"; cat "$C"; exit 1; }; }

printf '# my comment\n\na=1\n3ds["X.3ds"].a=9\n3ds.a=8\nb=2\n' > "$C"; chmod 640 "$C"
"$T/w" "$C" "$L" a 5
same '# my comment

a=5
3ds["X.3ds"].a=9
3ds.a=8
b=2' "not replaced in place"
[ "$(stat -c %a "$C")" = 640 ] || { echo "FAIL: the file's mode changed"; exit 1; }
"$T/w" "$C" "$L" new 1
[ "$(tail -n1 "$C")" = new=1 ] || { echo "FAIL: a new key isn't added"; exit 1; }
"$T/w" "$C" "$L" new ""
"$T/w" "$C" "$L" 3ds.a ""
same '# my comment

a=5
3ds["X.3ds"].a=9
b=2' "empty doesn't remove only that key"
printf 'dup=1\nx=1\ndup=2\n' > "$C"; "$T/w" "$C" "$L" dup 3
same 'dup=3
x=1' "a duplicate key survived"
ls "$T" | command grep -q asgard-tmp && { echo "FAIL: temp file left behind"; exit 1; }

# A missing file is a fresh install. An unreadable one must not be replaced by this one key. Root reads anything, so
# only test that as a normal user.
rm "$C"; "$T/w" "$C" "$L" a 1; same 'a=1' "a missing file isn't created"
if [ "$(id -u)" != 0 ]; then
  printf 'keep=1\n' > "$C"; chmod 000 "$C"
  if "$T/w" "$C" "$L" a 2; then echo "FAIL: reported success on an unreadable file"; exit 1; fi
  chmod 600 "$C"; same 'keep=1' "an unreadable file was replaced"
else
  echo "root: unreadable-file case not run"
fi

# The lock is the shell's: it waits while a set_setting holds it.
exec 9>"$L"; flock -x 9
"$T/w" "$C" "$L" locked 1 & P=$!
sleep 0.3
command grep -q '^locked=' "$C" && { echo "FAIL: wrote while the shell held the lock"; exit 1; }
flock -u 9; wait $P
command grep -q '^locked=1$' "$C" || { echo "FAIL: not written after the lock was released"; exit 1; }
echo OK
