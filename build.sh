#!/bin/bash
# Asgard OS = ROCKNIX (submodule rocknix/, pinned) + patches/ (changes to ROCKNIX files) + overlay/ (new files).
#   ./build.sh            prepare rocknix/ and build the SM8550 image (ROCKNIX's docker build)
#   ./build.sh prepare    only prepare: reset rocknix/, apply patches, copy overlay
#   ./build.sh upgrade    move the pin to ROCKNIX's latest next, then prepare. A failing patch means ROCKNIX
#                         changed that file: fix it in rocknix/, regenerate the patch, commit patch + new pin.
#   ./build.sh stage [user@host]   put the built .tar in the device's /storage/.update (installs on next boot);
#                                  the host defaults to $THOR
# rocknix/build.*, sources/ and target/ are git-ignored, so they survive the reset (incremental rebuilds).
set -euo pipefail
cd "$(dirname "$0")"
STEP=${1:-build}

if [ "$STEP" = stage ]; then
  HOST=${2:-${THOR:?pass user@host or set THOR=user@host}}
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

# ROCKNIX's docker build copies the caller's whole environment into the container (scripts/get_env -> .env), so
# it starts from an empty one: no tokens or session vars go in, and none of LOCAL_WIFI_SSID / LOCAL_WIFI_KEY /
# LOCAL_SSH_KEYS_FILE, which ROCKNIX would bake into the image. Personal settings go in asgard.yml (inject-config.sh).
# The tree is mounted at /work with HOME=/tmp, so binaries carry /work/... paths, not this machine's home dir and
# user name. Changing the work dir needs a clean build: rm -rf rocknix/build.ROCKNIX-SM8550.*
if [ "$STEP" = build ]; then
  env -i PATH="$PATH" TERM="${TERM:-dumb}" LANG=C.UTF-8 HOME=/tmp DOCKER_WORK_DIR=/work make -C rocknix docker-SM8550
  ls -1 rocknix/target/*.img.gz rocknix/target/*.tar 2>/dev/null
fi
