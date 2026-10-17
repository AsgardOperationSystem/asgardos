#!/bin/bash
# Extra Turnip (Mesa's Vulkan driver for Adreno) builds for the per-game "GPU driver" emulator option.
# Cross-compiled with the toolchain, sysroot and meson cross files of the last ./build.sh, so they match the image's
# own Mesa (compiler, flags, libdrm/xcb/wayland). Upstream Mesa: no ROCKNIX patches (rotated copies, Wayland
# pre-rotation), which XWayland emulators (Eden, Azahar) don't use.
#   ./turnip.sh <mesa version|main> [user@host]
#     -> turnip/<name>/{libvulkan_freedreno.so,icd.json}; with a host, copied to its /storage/.config/gpu-drivers/<name>/
#   e.g. ./turnip.sh 25.3.6 root@thor.local
#   PATCH=turnip-patches/<name>.patch ./turnip.sh <version> ...   -> a variant, mesa-<version>-<name>, in its own source dir
set -euo pipefail
cd "$(dirname "$0")"
V=$1; HOST=${2:-}
# ./build.sh builds in ROCKNIX's container with rocknix/ at /work, so its toolchain and cross files name /work paths:
# meson and ninja run in that container too, with turnip/ at /turnip.
B=/work/build.ROCKNIX-SM8550.aarch64
CROSS=$(cd rocknix && ls -d build.ROCKNIX-SM8550.aarch64/build/mesa-*/.aarch64-rocknix-linux-gnu 2>/dev/null | head -1)   # the image's Mesa build: its cross files
[ -f "rocknix/$CROSS/meson.conf" ] || { echo "no Mesa build in rocknix/: run ./build.sh first"; exit 1; }
CROSS=/work/$CROSS
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

# build-work/, not build/: a meson build dir is tied to the source path it was set up with (the host's, before /work).
docker run --rm --init --user "$(id -u):$(id -g)" -e HOME=/tmp -v "$PWD/rocknix:/work" -v "$PWD/turnip:/turnip" \
  ghcr.io/rocknix/rocknix-build:latest bash -euc '
  B=$1; CROSS=$2; C=$3
  export PATH="$B/toolchain/bin:$PATH"   # its meson, ninja and python (with mako/pyyaml)
  meson setup $([ -d "$C/build-work" ] && echo --reconfigure) "$C/build-work" "$C" --cross-file="$CROSS/meson.conf" --native-file="$CROSS/meson-host.conf" \
    -Dbuildtype=release -Dprefix=/usr -Dlibdir=lib -Dstrip=true -Dc_link_args=-lgcc -Dcpp_link_args=-lgcc \
    -Dvulkan-drivers=freedreno -Dfreedreno-kmds=msm -Dgallium-drivers= -Dplatforms=wayland,x11 \
    -Dopengl=false -Degl=disabled -Dgbm=disabled -Dglx=disabled -Dgles1=disabled -Dgles2=disabled \
    -Dllvm=disabled -Dshader-cache=enabled -Dvideo-codecs= -Dbuild-tests=false -Dvalgrind=disabled \
    -Dlibunwind=disabled -Dlmsensors=disabled -Dmicrosoft-clc=disabled
  ninja -C "$C/build-work" src/freedreno/vulkan/libvulkan_freedreno.so src/freedreno/vulkan/freedreno_icd.aarch64.json
' _ "$B" "$CROSS" "/turnip/src/$V$SUFFIX"

mkdir -p "$OUT"
cp "$SRC/build-work/src/freedreno/vulkan/libvulkan_freedreno.so" "$OUT/"
# The ICD file Mesa generated, pointing at the library's place on the Thor.
python3 -I - "$SRC/build-work/src/freedreno/vulkan/freedreno_icd.aarch64.json" "$DEV/libvulkan_freedreno.so" "$OUT/icd.json" <<'EOF'
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
