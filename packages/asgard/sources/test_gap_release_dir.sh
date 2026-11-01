#!/bin/sh
# spec: DEV-11
# requires: cmd:git
# gap: scripts/image builds the release in target/ at the tree root and leaves it there, empty
cd "$(dirname "$0")/../../.." || exit 2
! command grep -qE '^\s*RELEASE_DIR="target/' scripts/image
