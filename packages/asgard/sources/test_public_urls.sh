#!/bin/sh
# spec: DEV-15
# requires: cmd:git
# distribution/options, PKG_SITE values and Home's RetroAchievements user agent name the public project, nothing else.
cd "$(dirname "$0")/../../.." || exit 2
PUBLIC='https://github.com/AsgardOperationSystem/asgardos'
for f in packages/asgard/package.mk packages/asgard-home/package.mk packages/tools/asgardos-splash/package.mk; do
  grep -qxF "PKG_SITE=\"$PUBLIC\"" "$f" || { echo "$f: PKG_SITE isn't $PUBLIC"; exit 1; }
done
git grep -qF "(+$PUBLIC)" -- packages/asgard-home/src/achievements.cpp || { echo "Home's user agent doesn't name $PUBLIC"; exit 1; }
for key in HOME_URL WIKI_URL BUG_REPORT_URL; do
  git grep -qE "^\s*$key=\"$PUBLIC(/|\")" -- distribution/options || { echo "distribution/options: $key isn't under $PUBLIC"; exit 1; }
done
git grep -qE '^\s*GIT_ORGANIZATION="AsgardOperationSystem"' -- distribution/options || { echo "GIT_ORGANIZATION isn't AsgardOperationSystem"; exit 1; }
