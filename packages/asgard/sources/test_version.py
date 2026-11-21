#!/usr/bin/env python3
# spec: SET-6
# requires: cmd:sh cmd:awk
"""The Asgard version is a release number, major.minor.patch, set in distribution/version (About shows it, SET-6), and
what reads it copes: usbgadget makes the USB gadget's bcdDevice from it (still from an old date version too), and
build.sh stages the newest built .tar, since file names no longer sort by date."""
import os
import re
import subprocess

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
version = open(os.path.join(ROOT, "distribution/version")).read()
m = re.search(r'^\s*OS_VERSION="([^"]*)"', version, re.M)
assert m and re.fullmatch(r"\d+\.\d+\.\d+", m.group(1)), m and m.group(1)

line = next(l for l in open(os.path.join(ROOT, "packages/asgardos/sources/scripts/usbgadget")) if l.startswith("devversion="))


def bcd(v):
    return subprocess.run(["sh", "-c", line + 'echo "$devversion"'], env={"OS_VERSION": v, "PATH": os.environ["PATH"]},
                          capture_output=True, text=True, check=True).stdout.strip()


assert bcd("0.0.1") == "0x0001", bcd("0.0.1")
assert bcd("1.2.3") == "0x0123", bcd("1.2.3")
assert bcd("20241025") == "0x2410", bcd("20241025")
for v in ("0.0.1", "12.15.9", "20261117"):
    assert re.fullmatch(r"0x[0-9a-f]{4}", bcd(v)), (v, bcd(v))   # the kernel takes 16 bits

assert "ls -1t build/target/*.tar | head -1" in open(os.path.join(ROOT, "build.sh")).read()
print("ok")
