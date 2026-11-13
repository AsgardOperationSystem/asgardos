#!/usr/bin/env python3
# spec: NET-1
"""Run: python -I test_bt_headphone_battery.py  (no Thor): headphones report their battery over HFP, so PipeWire is built
with its native HFP backend and WirePlumber turns it on, with no switch to the call profile when an app opens a
microphone, and nothing left setting the backend to none. That a pair reports one is a human check."""
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
PKGS = os.path.join(HERE, "..", "..")


def read(*p):
    return open(os.path.join(*p)).read()


def body(text):
    return "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))


pw = read(PKGS, "audio", "pipewire", "package.mk")
assert "-Dbluez5-backend-hfp-native=enabled" in pw, "PipeWire built without native HFP"
# 1.2.6 calls rfcomm_send_volume_cmd from the HFP code but defines it only with HSP: HFP alone doesn't compile
assert "-Dbluez5-backend-hsp-native=enabled" in pw, "PipeWire 1.2.6 HFP needs HSP built too"
# HFP runs over RFCOMM: without it bluetoothd logs "socket(STREAM, RFCOMM): Protocol not supported" (a Thor, 2026-11-13)
kconf = read(PKGS, "..", "device", "linux", "linux.aarch64.conf").splitlines()
assert "CONFIG_BT_RFCOMM=m" in kconf or "CONFIG_BT_RFCOMM=y" in kconf, "the kernel has no RFCOMM, so HFP can't connect"
conf = body(read(HERE, "..", "wireplumber", "62-bluez-headphone-battery.conf"))
assert re.search(r'bluez5\.hfphsp-backend\s*=\s*"native"', conf), "HFP backend not turned on"
assert re.search(r"bluetooth\.autoswitch-to-headset-profile\s*=\s*false", conf), "a microphone would switch to HFP"
assert "cp ${PKG_DIR}/wireplumber/*.conf ${INSTALL}/usr/share/wireplumber/wireplumber.conf.d/" in read(HERE, "..", "package.mk")
assert not re.search(r'hfphsp-backend\s*=\s*"none"', read(PKGS, "audio", "wireplumber", "package.mk")), "ROCKNIX's off switch is back"
print("OK")
