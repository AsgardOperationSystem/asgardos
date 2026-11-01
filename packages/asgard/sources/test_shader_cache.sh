#!/bin/sh
# spec: OVR-3
# requires: cmd:bash cmd:od cmd:dd
# asgard-shader-cache.sh, its paths in a temp dir: the half of OVR-3 about deleting a game's shader cache. It deletes this game's only.
# That Settings offers it for a game is test_game_options.py.
set -e
HERE=$(dirname "$(readlink -f "$0")")
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
S=$T/script.sh
sed "s|/storage|$T/storage|g" "$HERE/asgard-shader-cache.sh" >"$S"

# Azahar: <title ID>_* from the NCSD header's media ID, little-endian at 0x108.
A=$T/storage/.config/azahar/shaders/vulkan/precompiled
mkdir -p "$A"
touch "$A/0004000000011C00_a.bin" "$A/0004000000011C00_b.bin" "$A/0004000000099999_other.bin"
printf 'x' | dd of="$T/game.3ds" bs=1 seek=263 2>/dev/null
printf 'NCSD' | dd of="$T/game.3ds" bs=1 seek=256 conv=notrunc 2>/dev/null
printf '\000\034\001\000\000\000\004\000' | dd of="$T/game.3ds" bs=1 seek=264 conv=notrunc 2>/dev/null
out=$(bash "$S" 3ds "$T/game.3ds")
case "$out" in Deleted*0004000000011C00*) ;; *) echo "3ds said: $out"; exit 1 ;; esac
[ ! -e "$A/0004000000011C00_a.bin" ] && [ ! -e "$A/0004000000011C00_b.bin" ]
[ -e "$A/0004000000099999_other.bin" ]
out=$(bash "$S" 3ds "$T/game.3ds")
case "$out" in "No shader cache"*) ;; *) echo "second run said: $out"; exit 1 ;; esac

# Eden: shader/<title ID>/ from the file name.
E=$T/storage/.local/share/eden/shader
mkdir -p "$E/0100aaaaaaaaaaaa" "$E/0100bbbbbbbbbbbb"
out=$(bash "$S" switch "/roms/switch/Game [0100AAAAAAAAAAAA][v0].nsp")
case "$out" in Deleted*) ;; *) echo "switch said: $out"; exit 1 ;; esac
[ ! -d "$E/0100aaaaaaaaaaaa" ] && [ -d "$E/0100bbbbbbbbbbbb" ]

# Anything it can't name: says so, deletes nothing.
touch "$T/notanimage.3ds"
bash "$S" 3ds "$T/notanimage.3ds" >/dev/null && { echo "accepted a non-NCSD file"; exit 1; }
bash "$S" switch "/roms/no-id.nsp" >/dev/null && { echo "accepted a name with no title ID"; exit 1; }
bash "$S" gba "/roms/x.gba" >/dev/null && { echo "accepted a system it doesn't handle"; exit 1; }
[ -d "$E/0100bbbbbbbbbbbb" ] && [ -e "$A/0004000000099999_other.bin" ]
echo ok
