#!/bin/sh
# spec: DEV-16
# requires: cmd:git
# test_build_env.py shows build.sh's empty environment holds. This is the rule itself: the code that bakes them in is still there,
# for `make SM8550`, for `make docker-SM8550` run by hand, and for an options file in the build's HOME.
cd "$(dirname "$0")/../../.." || exit 2
! git grep -qE 'LOCAL_WIFI_|LOCAL_SSH_KEYS_FILE' -- packages/asgardos/package.mk Makefile
