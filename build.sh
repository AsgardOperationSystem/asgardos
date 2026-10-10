#!/bin/bash
# Asgard OS = ROCKNIX (submodule rocknix/, pinned) + patches/ (changes to ROCKNIX files) + overlay/ (new files).
#   ./build.sh            prepare rocknix/ and build the SM8550 image (ROCKNIX's docker build)
#   ./build.sh prepare    only prepare: reset rocknix/, apply patches, copy overlay
#   ./build.sh upgrade    move the pin to ROCKNIX's latest next, then prepare. A failing patch means ROCKNIX
#                         changed that file: fix it in rocknix/, regenerate the patch, commit patch + new pin.
#   ./build.sh stage [user@host]   put the built .tar in the device's /storage/.update (installs on next boot)
# rocknix/build.*, sources/ and target/ are git-ignored, so they survive the reset (incremental rebuilds).
set -euo pipefail
cd "$(dirname "$0")"
STEP=${1:-build}

if [ "$STEP" = stage ]; then
  HOST=${2:-root@192.168.50.30}
  TAR=$(ls -1 rocknix/target/*.tar | head -1)
  NAME=$(basename "$TAR")
  SUM=$(cut -d' ' -f1 "$TAR.sha256")
  # Copied under a temporary name and renamed only once its checksum matches on the device: a copy cut short
  # (the device rebooted mid-transfer, 2026-10-10) must never look like an update to ROCKNIX's installer,
  # which only picks up *.tar.
  scp -q "$TAR" "$HOST:/storage/.update/$NAME.part"
  ssh "$HOST" "cd /storage/.update && echo '$SUM  $NAME.part' | sha256sum -c - >/dev/null \
    && mv '$NAME.part' '$NAME' && echo 'staged $NAME, installs on the next boot' \
    || { rm -f '$NAME.part'; echo 'checksum mismatch on the device: not staged'; exit 1; }"
  exit
fi

if [ "$STEP" = upgrade ]; then
  git -C rocknix fetch -q --depth 1 origin next
  git -C rocknix checkout -q --detach FETCH_HEAD
  echo "rocknix -> $(git -C rocknix log -1 --format='%h %ci %s')"
else
  git submodule update -q --init --depth 1 rocknix
fi
# ROCKNIX's build runs git inside docker, which only mounts rocknix/: keep the submodule's git dir in there
# instead of the usual ../.git/modules/rocknix pointer.
if [ -f rocknix/.git ]; then
  GD=$(git -C rocknix rev-parse --absolute-git-dir)
  rm rocknix/.git && mv "$GD" rocknix/.git && git -C rocknix config --unset core.worktree
fi
git -C rocknix reset -q --hard
git -C rocknix clean -qfd

shopt -s nullglob
PATCHES=(patches/*.patch)
for p in "${PATCHES[@]}"; do
  git -C rocknix apply --whitespace=nowarn "$PWD/$p" || { echo "FAILED: $p no longer applies to rocknix/"; exit 1; }
done
[ -d overlay ] && cp -a overlay/. rocknix/
echo "rocknix/ prepared: ${#PATCHES[@]} patches + overlay"

# Never pass LOCAL_WIFI_SSID / LOCAL_WIFI_KEY / LOCAL_SSH_KEYS_FILE: ROCKNIX bakes them into the image.
# Personal settings go in asgard.yml (see inject-config.sh).
if [ "$STEP" = build ]; then
  env -u LOCAL_WIFI_SSID -u LOCAL_WIFI_KEY -u LOCAL_SSH_KEYS_FILE make -C rocknix docker-SM8550
  ls -1 rocknix/target/*.img.gz rocknix/target/*.tar 2>/dev/null
fi
