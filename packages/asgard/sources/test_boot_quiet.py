#!/usr/bin/env python3
# spec: SCR-5
"""The part of SCR-5 visible in the source: the kernel command line that keeps boot quiet, and the splash and its boot
animation switched on, ahead of sway. How it looks, and on which screen, is the human check."""
import os
import re

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../.."))
read = lambda name: open(os.path.join(REPO, name)).read()

cmdline = re.search(r'EXTRA_CMDLINE="([^"]*)"', read("device/options")).group(1).split()
for word in ("quiet", "loglevel=1", "systemd.show_status=false", "vt.global_cursor_default=0"):
    assert word in cmdline, f"{word} isn't on the kernel command line"
UNIT = read("packages/asgard/system.d/asgard-bootanim.service")
assert re.search(r"^ExecStart=/usr/bin/asgardos-splash --animate ", UNIT, re.M), "the unit doesn't run the animation"
assert re.search(r"^Before=sway\.service$", UNIT, re.M) and re.search(r"^WantedBy=sysinit\.target$", UNIT, re.M), UNIT
enabled = re.search(r"for unit in ([^;]*);", read("packages/asgard/package.mk")).group(1).split()
assert "asgard-bootanim" in enabled, enabled
# Drawn on the bigger panel only, which is the top one, with the others off.
DRM = read("packages/tools/asgardos-splash/src/drmsplash.c")
assert "largest connected panel" in DRM and re.search(r"count_connectors = 1", DRM), "the splash isn't on one panel"
print("boot quiet: ok")
