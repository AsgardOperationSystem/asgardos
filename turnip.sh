#!/bin/bash
# Extra Turnip (Mesa's Vulkan driver for Adreno) builds for the per-game "GPU driver" emulator option.
# Cross-compiled with the toolchain, sysroot and meson cross files of the last ./build.sh, so they match the image's
# own Mesa (compiler, flags, libdrm/xcb/wayland). Upstream Mesa: no ROCKNIX patches (rotated copies, Wayland
# pre-rotation), which XWayland emulators (Eden, Azahar) don't use.
#   ./turnip.sh <mesa version|main> [user@host]
#     -> turnip/<name>/{libvulkan_freedreno.so,icd.json}; with a host, copied to its /storage/.config/gpu-drivers/<name>/
#   e.g. ./turnip.sh 25.3.6 root@192.168.50.30
#   PATCH=turnip-patches/<name>.patch ./turnip.sh <version> ...   -> a variant, mesa-<version>-<name>, in its own source dir
set -euo pipefail
cd "$(dirname "$0")"
V=$1; HOST=${2:-}
B="$PWD/rocknix/build.ROCKNIX-SM8550.aarch64"
CROSS=$(ls -d "$B"/build/mesa-*/.aarch64-rocknix-linux-gnu | head -1)   # the image's Mesa build: its cross files
[ -f "$CROSS/meson.conf" ] || { echo "no Mesa build in $B: run ./build.sh first"; exit 1; }
NAME="mesa-$V"; [ "$V" = main ] && NAME="mesa-main-$(date +%Y%m%d)"
SUFFIX=${PATCH:+-$(basename "$PATCH" .patch)}
NAME="$NAME$SUFFIX"
SRC="$PWD/turnip/src/$V$SUFFIX"; OUT="$PWD/turnip/$NAME"; DEV="/storage/.config/gpu-drivers/$NAME"

if [ ! -d "$SRC" ]; then
  git clone --depth 1 -b "$([ "$V" = main ] && echo main || echo "mesa-$V")" https://gitlab.freedesktop.org/mesa/mesa.git "$SRC"
  [ -z "${PATCH:-}" ] || git -C "$SRC" apply "$(realpath "$PATCH")"
elif [ "$V" = main ]; then
  git -C "$SRC" pull --depth 1 --ff-only
fi

export PATH="$B/toolchain/bin:$PATH"   # its meson, ninja and python (with mako/pyyaml)
meson setup $([ -d "$SRC/build" ] && echo --reconfigure) "$SRC/build" "$SRC" --cross-file="$CROSS/meson.conf" --native-file="$CROSS/meson-host.conf" \
  -Dbuildtype=release -Dprefix=/usr -Dlibdir=lib -Dstrip=true -Dc_link_args=-lgcc -Dcpp_link_args=-lgcc \
  -Dvulkan-drivers=freedreno -Dfreedreno-kmds=msm -Dgallium-drivers= -Dplatforms=wayland,x11 \
  -Dopengl=false -Degl=disabled -Dgbm=disabled -Dglx=disabled -Dgles1=disabled -Dgles2=disabled \
  -Dllvm=disabled -Dshader-cache=enabled -Dvideo-codecs= -Dbuild-tests=false -Dvalgrind=disabled \
  -Dlibunwind=disabled -Dlmsensors=disabled -Dmicrosoft-clc=disabled
ninja -C "$SRC/build" src/freedreno/vulkan/libvulkan_freedreno.so src/freedreno/vulkan/freedreno_icd.aarch64.json

mkdir -p "$OUT"
cp "$SRC/build/src/freedreno/vulkan/libvulkan_freedreno.so" "$OUT/"
# The ICD file Mesa generated, pointing at the library's place on the Thor.
python3 -I - "$SRC/build/src/freedreno/vulkan/freedreno_icd.aarch64.json" "$DEV/libvulkan_freedreno.so" "$OUT/icd.json" <<'EOF'
import json, sys
icd = json.load(open(sys.argv[1]))
icd["ICD"]["library_path"] = sys.argv[2]
json.dump(icd, open(sys.argv[3], "w"), indent=4)
EOF
git -C "$SRC" describe --tags --always > "$OUT/version"
echo "built $OUT ($(cat "$OUT/version"))"

if [ -n "$HOST" ]; then
  ssh "$HOST" "mkdir -p '$DEV'"
  scp -q "$OUT/libvulkan_freedreno.so" "$OUT/icd.json" "$OUT/version" "$HOST:$DEV/"
  echo "installed on $HOST: $DEV"
fi
