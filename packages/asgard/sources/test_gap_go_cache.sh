#!/bin/sh
# spec: DEV-11
# requires: cmd:git
# gap: a Go package's build writes .cache/ and .config/ to the tree root
# The .gitignore lines keep this red after someone just deletes the directories: the build would make them again.
cd "$(dirname "$0")/../../.." || exit 2
[ ! -e .cache ] && [ ! -e .config ] && ! command grep -qxE '/\.(cache|config)/' .gitignore
