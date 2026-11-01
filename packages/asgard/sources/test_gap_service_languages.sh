#!/bin/sh
# spec: DEV-17
# requires: cmd:git
# gap: asgard-motiond imports dbussy (a recipe's package, not the standard library) and asgard-gamma.service is C
cd "$(dirname "$0")/../../.." || exit 2
! command grep -qE '^\s*(import|from) dbussy' packages/asgard/sources/asgard-motiond.py && [ ! -e packages/asgard/gamma/asgard-gamma.c ]
