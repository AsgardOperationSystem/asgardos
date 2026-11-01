#!/bin/sh
# spec: DEV-11
# requires: cmd:git
# gap: the emulators package regenerates the tracked docs/supported-emulators.md during a build
cd "$(dirname "$0")/../../.." || exit 2
! command grep -qE '^\s*SYSDOCROOT="\$\{ROOT\}/docs"' distribution/options
