#!/bin/sh
# spec: DEV-9 DEV-15
# requires: cmd:git cmd:curl
# gap: the build image on ghcr.io isn't public yet, so a clean checkout elsewhere can't pull it
# A clean checkout fetches only from public hosts: the submodules from GitHub, the build image from a public registry,
# pinned by digest and pullable without a login.
cd "$(dirname "$0")/../../.." || exit 2
git config -f .gitmodules --get-regexp '\.url$' | awk '{print $2}' | grep -vq '^https://github\.com/' && exit 1
img=$(sed -n 's/^docker-%: DOCKER_IMAGE := "\(ghcr\.io\/[^"@]*@sha256:[0-9a-f]\{64\}\)"$/\1/p' Makefile)
[ -n "$img" ] || { echo "the Makefile's build image isn't a digest-pinned ghcr.io image"; exit 1; }
repo=${img#ghcr.io/}; repo=${repo%@*}; digest=${img#*@}
token=$(curl -fsS "https://ghcr.io/token?scope=repository:$repo:pull" 2>/dev/null | sed -n 's/.*"token":"\([^"]*\)".*/\1/p')
curl -fsS -o /dev/null -H "Authorization: Bearer $token" \
  -H 'Accept: application/vnd.docker.distribution.manifest.v2+json, application/vnd.oci.image.manifest.v1+json' \
  "https://ghcr.io/v2/$repo/manifests/$digest" 2>/dev/null || { echo "$img can't be pulled without a login"; exit 1; }
