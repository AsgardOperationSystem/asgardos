#!/bin/bash
# Builds a libretro core for this machine (x86_64) from the source the image build downloaded, for the simulated Thor's
# games in play (tools/sim/runemu.sh): build/sim/cores/<core>_libretro.so.
#   tools/sim/build-core.sh snes9x
# It takes the tarball matching the image's PKG_VERSION in build/sources/<core>-lr, else the newest one there, and
# says which. Only cores built with a plain `make` in their libretro dir are known here.
set -euo pipefail
cd "$(dirname "$0")/../.."
core=${1:?usage: tools/sim/build-core.sh <core> (snes9x)}
case $core in
  snes9x) dir=libretro ;;
  *) echo "build-core: $core isn't known yet (snes9x)" >&2; exit 1 ;;
esac
pkg=$(ls -d packages/emulators/libretro/"$core"-lr)
want=$(sed -n 's/^PKG_VERSION="\([^"]*\)".*/\1/p' "$pkg/package.mk")
src=build/sources/$core-lr/$core-lr-$want.tar.gz
if [ ! -f "$src" ]; then
  src=$(ls -t build/sources/"$core"-lr/*.tar.gz 2>/dev/null | head -1)
  [ -n "$src" ] || { echo "build-core: no $core source in build/sources: build the image first" >&2; exit 1; }
  echo "build-core: the image's $core ($want) isn't downloaded; building $(basename "$src") instead" >&2
fi
work=build/sim/cores/src
rm -rf "$work/$core" && mkdir -p "$work/$core"
tar -xzf "$src" -C "$work/$core" --strip-components=1
ver=$(basename "$src" .tar.gz); ver=${ver##*-}
# GIT_VERSION: the tarball has no .git, and the core's Makefile would ask git, which answers with this repo's commit
make -C "$work/$core/$dir" -j"$(nproc)" GIT_VERSION=" ${ver:0:7}" >"$work/$core.log" 2>&1 ||
  { tail -20 "$work/$core.log" >&2; exit 1; }
cp "$work/$core/$dir/${core}_libretro.so" build/sim/cores/
echo "build/sim/cores/${core}_libretro.so (${ver:0:7})"
