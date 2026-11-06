#!/usr/bin/env python3
# spec: SND-6
"""Run: python -I test_outputs_stay_open.py  (no Thor): WirePlumber keeps the Thor's outputs open 60 s after their last
sound, so a menu sound doesn't wait about half a second for the DSP's path to reopen. The rule matches every ALSA
output (speaker and headphones) and is installed with the other Asgard WirePlumber files. That the delay is gone is a
human check."""
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
conf = open(os.path.join(HERE, "..", "wireplumber", "61-thor-outputs-stay-open.conf")).read()
body = "\n".join(line for line in conf.splitlines() if not line.lstrip().startswith("#"))
assert re.search(r"monitor\.alsa\.rules\s*=", body), "not an ALSA monitor rule"
assert re.search(r'node\.name\s*=\s*"~alsa_output\.\*"', body), "doesn't match every ALSA output"
m = re.search(r"session\.suspend-timeout-seconds\s*=\s*(\d+)", body)
assert m and int(m.group(1)) == 60, "outputs don't stay open 60 s"
mk = open(os.path.join(HERE, "..", "package.mk")).read()
assert "cp ${PKG_DIR}/wireplumber/*.conf ${INSTALL}/usr/share/wireplumber/wireplumber.conf.d/" in mk, "not installed"
print("OK")
