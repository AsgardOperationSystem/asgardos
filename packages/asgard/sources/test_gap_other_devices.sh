#!/bin/sh
# spec: DEV-2
# requires: cmd:git
# gap: device/config.xml and device/filesystem/ still carry other SM8550 handhelds' device trees and input maps
cd "$(dirname "$0")/../../.." || exit 2
! git grep -qEi 'odin|retroid|ayaneo|pocket' -- device/config.xml device/filesystem
