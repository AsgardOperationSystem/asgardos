#!/bin/sh
# spec: DEV-2
# requires: cmd:git
# gap: 87 other devices' quirks and about 45 files naming other SoCs, recipe branches among them
# The rule outright, no allowances: test_tree_deviations.py stops new ones meanwhile.
cd "$(dirname "$0")/../../.." || exit 2
git ls-files packages/hardware/quirks/devices | cut -d/ -f5 | sort -u | command grep -qvx 'AYN Thor' && exit 1
! git grep -qIE '\b(RK[0-9]{4}[A-Z]*|S922X|H700|SM8250|SM8650|SM8750|SM6115|SM4450|RPi[0-9]?)\b' -- \
  ':!*.md' ':!docs' ':!*.patch' ':!packages/asgard/sources/test_*' ':!packages/security/openssl/cert/cacert.pem'
