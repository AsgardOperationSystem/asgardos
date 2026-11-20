#!/bin/sh
# spec: DEV-9 DEV-15
# requires: cmd:git
# gap: the Makefile's build image is on a LAN registry, so outside the LAN a clean checkout can't build
# A clean checkout fetches only from public hosts: the submodules from GitHub, the build image from a public registry.
cd "$(dirname "$0")/../../.." || exit 2
git config -f .gitmodules --get-regexp '\.url$' | awk '{print $2}' | grep -vq '^https://github\.com/' && exit 1
git grep -qE '^docker-%: DOCKER_IMAGE := "(ghcr\.io|docker\.io)/[^"]*@sha256:[0-9a-f]{64}"' -- Makefile
