#!/bin/sh
# spec: SCR-1
# requires: cmd:wayland-scanner cmd:cc lib:libwayland-client.so
# asgard-gamma's warmth/tint -> channel gains and contrast -> exponent (built for the host from ../gamma).
set -e
G=$(dirname "$0")/../gamma; T=$(mktemp -d); trap 'rm -rf $T' EXIT
wayland-scanner client-header $G/wlr-gamma-control-unstable-v1.xml $T/wlr-gamma-control-unstable-v1-client-protocol.h
wayland-scanner private-code $G/wlr-gamma-control-unstable-v1.xml $T/proto.c
cc -I$T -o $T/g $G/asgard-gamma.c $T/proto.c -lwayland-client -lm
[ "$($T/g --gains 0 0)" = "1.000 1.000 1.000" ] || { echo "FAIL: neutral"; exit 1; }
[ "$($T/g --gains 2 0)" = "1.000 0.980 0.940" ] || { echo "FAIL: warm"; exit 1; }
[ "$($T/g --gains -2 0)" = "0.940 0.980 1.000" ] || { echo "FAIL: cool"; exit 1; }
[ "$($T/g --gains 0 3)" = "1.000 0.940 1.000" ] || { echo "FAIL: magenta"; exit 1; }
[ "$($T/g --gains 0 -3)" = "0.940 1.000 0.940" ] || { echo "FAIL: green"; exit 1; }
[ "$($T/g --exponent 0)" = "1.0" ] && [ "$($T/g --exponent 10)" = "2.0" ] && [ "$($T/g --exponent -5)" = "0.5" ] ||
  { echo "FAIL: exponent"; exit 1; }
echo ok
