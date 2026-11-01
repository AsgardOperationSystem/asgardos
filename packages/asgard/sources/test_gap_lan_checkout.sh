#!/bin/sh
# spec: DEV-9 DEV-15
# requires: cmd:git
# gap: .gitmodules and the Makefile's build image point at LAN hosts, so outside the LAN a clean checkout can't build
# The rule outright, no allowances: test_tree_deviations.py stops new ones meanwhile.
cd "$(dirname "$0")/../../.." || exit 2
! git grep -qE 'lan\.example' -- .gitmodules Makefile
