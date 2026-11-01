#!/usr/bin/env python3
# spec: EMU-1
# requires: cmd:git
# gap: pico-8 was dropped from the metapackage, though every ROCKNIX system has to stay in the image.
# Tree check: every system the metapackage registered at the fork point (7cffc96) is still registered.
import os
import re
import subprocess

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../.."))
systems = lambda text: set(re.findall(r"^\s*add_es_system\s+(\S+)", text, re.M))  # noqa: E731
then = subprocess.run(["git", "-C", REPO, "show", "7cffc96:projects/ROCKNIX/packages/virtual/emulators/package.mk"],
                      check=True, capture_output=True, text=True).stdout
with open(f"{REPO}/packages/virtual/emulators/package.mk") as f:
    now = f.read()
assert systems(then) and not systems(then) - systems(now), f"gone since the fork: {sorted(systems(then) - systems(now))}"
