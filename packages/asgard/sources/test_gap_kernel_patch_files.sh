#!/bin/sh
# spec: DEV-7
# requires: cmd:git
# gap: packages/linux/patches/mainline holds four patch files (not applied: PKG_PATCH_DIRS is empty)
cd "$(dirname "$0")/../../.." || exit 2
[ -z "$(git ls-files 'packages/linux/patches/*')" ]
