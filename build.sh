#!/bin/bash
# Asgard OS: build the image from this tree as it stands, or stage a built update on a Thor.
#   ./build.sh            build the SM8550 image (docker build, our pinned build container); log in build/log/
#   ./build.sh stage [user@host]   put the built .tar in the device's /storage/.update (installs on next boot);
#                                  the host defaults to $THOR
# Everything the build makes goes to build/ (git-ignored): build dirs, sources/, target/, log/.
set -euo pipefail
cd "$(dirname "$0")"
STEP=${1:-build}

if [ "$STEP" = stage ]; then
  HOST=${2:-${THOR:?pass user@host or set THOR=user@host}}
  TAR=$(ls -1t build/target/*.tar | head -1)   # the newest build: names carry the release (0.0.1), not a date
  NAME=$(basename "$TAR")
  SUM=$(cut -d' ' -f1 "$TAR.sha256")
  # Copied under a temporary name and renamed only once its checksum matches on the device: a copy cut short
  # (the device rebooted mid-transfer, 2026-10-10) must never look like an update to the installer,
  # which only picks up *.tar.
  scp -q "$TAR" "$HOST:/storage/.update/$NAME.part"
  ssh "$HOST" "cd /storage/.update && echo '$SUM  $NAME.part' | sha256sum -c - >/dev/null \
    && mv '$NAME.part' '$NAME' && echo 'staged $NAME, installs on the next boot' \
    || { rm -f '$NAME.part'; echo 'checksum mismatch on the device: not staged'; exit 1; }"
  exit
fi

# The docker build copies the caller's whole environment into the container (scripts/get_env -> .env), so
# it starts from an empty one: no tokens or session vars go in, and none of LOCAL_WIFI_SSID / LOCAL_WIFI_KEY /
# LOCAL_SSH_KEYS_FILE, which the build would bake into the image. Personal settings go in asgard.yml (inject-config.sh).
# The tree is mounted at /work with HOME=/tmp, so binaries carry /work/... paths, not this machine's home dir and
# user name. Changing the work dir or the build dir needs a clean build: rm -rf build/AsgardOS-SM8550.*
if [ "$STEP" = build ]; then
  mkdir -p build/log
  LOG=build/log/build-$(date +%Y%m%d-%H%M%S).log
  echo "log: $LOG"
  exec > >(tee "$LOG") 2>&1
  env -i PATH="$PATH" TERM="${TERM:-dumb}" LANG=C.UTF-8 HOME=/tmp DOCKER_WORK_DIR=/work CUSTOM_GIT_HASH="$(git rev-parse HEAD)" make docker-SM8550
  ls -1 build/target/*.img.gz build/target/*.tar 2>/dev/null
fi
