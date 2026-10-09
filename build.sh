#!/bin/bash
# Asgard OS = ROCKNIX (submodule rocknix/, pinned) + patches/ (changes to ROCKNIX files) + overlay/ (new files).
#   ./build.sh            prepare rocknix/ and build the SM8550 image (ROCKNIX's docker build)
#   ./build.sh prepare    only prepare: reset rocknix/, apply patches, copy overlay
#   ./build.sh upgrade    move the pin to ROCKNIX's latest next, then prepare. A failing patch means ROCKNIX
#                         changed that file: fix it in rocknix/, regenerate the patch, commit patch + new pin.
# rocknix/build.*, sources/ and target/ are git-ignored, so they survive the reset (incremental rebuilds).
set -euo pipefail
cd "$(dirname "$0")"
STEP=${1:-build}

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
