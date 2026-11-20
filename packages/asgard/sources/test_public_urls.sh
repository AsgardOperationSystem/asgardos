#!/bin/sh
# spec: DEV-15
# requires: cmd:git
# distribution/options, PKG_SITE values and Home's RetroAchievements user agent name the public project, not a LAN host.
cd "$(dirname "$0")/../../.." || exit 2
! git grep -qE 'lan\.example|asgardos-owner' -- distribution/options packages/asgard/package.mk packages/asgard-home/package.mk \
  packages/tools/asgardos-splash/package.mk packages/asgard-home/src/achievements.cpp
