#!/bin/sh
# spec: DEV-15
# requires: cmd:git
# gap: distribution/options, PKG_SITE values and Home's RetroAchievements user agent carry the LAN GitLab URL
# The rule outright, no allowances: test_tree_deviations.py stops new ones meanwhile.
cd "$(dirname "$0")/../../.." || exit 2
! git grep -qE 'lan\.example|asgardos-owner' -- distribution/options packages/asgard/package.mk packages/asgard-home/package.mk \
  packages/tools/asgardos-splash/package.mk packages/asgard-home/src/achievements.cpp
