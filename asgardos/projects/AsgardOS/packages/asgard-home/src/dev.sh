#!/bin/bash
# Asgard Home development loop. Screenshots are rendered offscreen (no window opens) at the Thor's panel sizes.
#   ./dev.sh shot ["right a"]   desktop build on the fixture ($REPO/frontend-dev/root) -> /tmp/asgard-shot-*.png
#   THOR=user@host ./dev.sh thor ["right a"]   cross-build, copy to the Thor (/storage/asgard-dev), render there -> /tmp/asgard-thor-*.png
# Keys are button names (up down left right a b x y lb rb select start) replayed before the shot.
# ASGARD_ARGS: the mode to render (--files, --panel ...); the panel's thor_panel.py is the source tree's.
# THOR_BUILD: a ROCKNIX SM8550 build dir with a built toolchain + qt6 (cross-compiling only).
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
REPO=$(git -C "$HERE" rev-parse --show-toplevel)
THOR_BUILD=${THOR_BUILD:-$(cd "$(dirname "$0")/../../../../.." && pwd)/build.AsgardOS-SM8550.aarch64}
OUT=${TMPDIR:-/tmp}
case "${1:-shot}" in
  shot)
    cmake -S "$HERE" -B "$OUT/asgard-home-host" -DCMAKE_BUILD_TYPE=Debug >/dev/null
    cmake --build "$OUT/asgard-home-host" -j"$(nproc)" | grep -E "error|warning" || true
    QT_FORCE_STDERR_LOGGING=1 ASGARD_ROOT="$REPO/frontend-dev/root" ASGARD_HOME_QML="$HERE/qml" ASGARD_SHOT="$OUT/asgard-shot-" \
      ASGARD_KEYS="${2:-}" \
      ASGARD_PANEL="$HERE/../../asgard/sources/thor_panel.py" "$OUT/asgard-home-host/asgard-home" ${ASGARD_ARGS:-}
    ls "$OUT"/asgard-shot-*.png ;;
  thor)
    : "${THOR:?set THOR=user@host (the Thor)}"
    cmake -S "$HERE" -B "$OUT/asgard-home-thor" -DCMAKE_BUILD_TYPE=Release \
      -DCMAKE_TOOLCHAIN_FILE="$THOR_BUILD/toolchain/etc/cmake-aarch64-asgardos-linux-gnu.conf" >/dev/null
    cmake --build "$OUT/asgard-home-thor" -j"$(nproc)" | grep -E "error|warning" || true
    ssh "$THOR" 'mkdir -p /storage/asgard-dev'
    # Upload beside it and rename: the running (or bind-mounted) binary can't be overwritten in place.
    scp -q "$OUT/asgard-home-thor/asgard-home" "$THOR:/storage/asgard-dev/asgard-home.new"
    ssh "$THOR" 'mv /storage/asgard-dev/asgard-home.new /storage/asgard-dev/asgard-home'
    rsync -a --delete "$HERE/qml/" "$THOR:/storage/asgard-dev/qml/"
    scp -q "$HERE/../../asgard/sources/thor_panel.py" "$THOR:/storage/asgard-dev/"   # its imports: the installed ones
    # Run inside the live sway session (its env comes from the running frontend), windows stay hidden.
    ssh "$THOR" "eval \"\$(tr '\\0' '\\n' < /proc/\$(systemctl show -P MainPID essway)/environ | grep -E '^(WAYLAND_DISPLAY|XDG_RUNTIME_DIR)=' | sed 's/^/export /')\"
      cd /storage/asgard-dev && ASGARD_HOME_QML=qml ASGARD_SHOT=/tmp/asgard-thor- ASGARD_KEYS='${2:-}' \
        ASGARD_PANEL=/storage/asgard-dev/thor_panel.py PYTHONPATH=/usr/share/asgard ./asgard-home ${ASGARD_ARGS:-} 2>&1 | grep -v -E 'locale|UTF-8|iCCP|reconfigure' || true"
    scp -q "$THOR:/tmp/asgard-thor-*.png" "$OUT/"
    ls "$OUT"/asgard-thor-*.png ;;
  *) sed -n '2,8p' "$0"; exit 1 ;;
esac
