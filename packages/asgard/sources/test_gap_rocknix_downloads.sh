#!/bin/sh
# spec: DEV-9
# requires: cmd:git
# gap: ten packages, DISTRO_MIRROR, and three more SPEC doesn't count (emulationstation, textviewer, rocknix-joypad) download from ROCKNIX's GitHub
# The rule outright, no allowances: test_tree_deviations.py stops new ones meanwhile.
cd "$(dirname "$0")/../../.." || exit 2
! git grep -qE 'github\.com/ROCKNIX' -- distribution/options \
  packages/apps/rocknix-hotkey/package.mk packages/apps/commander/package.mk packages/apps/jstest-sdl/package.mk \
  packages/linux-firmware/extra-firmware/package.mk packages/tools/sound/soundfont-generaluser/package.mk \
  packages/emulators/standalone/aethersx2-sa/package.mk packages/emulators/standalone/drastic-sa/package.mk \
  packages/compress/cabextract/package.mk packages/apps/portmaster/package.mk packages/emulators/libretro/idtech-lr/package.mk \
  packages/ui/emulationstation/package.mk packages/textproc/textviewer/package.mk packages/linux-drivers/rocknix-joypad/package.mk
