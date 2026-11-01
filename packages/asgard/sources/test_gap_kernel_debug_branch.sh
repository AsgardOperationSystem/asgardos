#!/bin/sh
# spec: DEV-3
# requires: cmd:git file:packages/linux/src/Makefile
# gap: the kernel repo has origin/debug/disp-rsc-dump besides asgard, as of the last fetch
cd "$(dirname "$0")/../../.." || exit 2
! git -C packages/linux/src for-each-ref --format='%(refname)' refs/remotes/origin | command grep -qvE '/origin/(HEAD|asgard)$'
