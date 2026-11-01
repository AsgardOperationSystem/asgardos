#!/usr/bin/env python3
# spec: EMU-4
# gap: the metapackage ships desmume and gpsp (EMUS_32BIT), but SPEC.md's list of the image's cores doesn't name them.
# Tree check: every core the metapackage lists is in SPEC.md's list. The other direction is in test_emulator_tree.py.
import os
import re

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../.."))
with open(f"{REPO}/packages/virtual/emulators/package.mk") as f:
    meta = f.read()
with open(f"{REPO}/SPEC.md") as f:
    spec = f.read()
paragraph = spec[spec.index("The image's cores are:"):spec.index("- **EMU-1**")].split(":", 1)[1]
listed = {c.strip().rstrip(".") for c in paragraph.replace("\n", " ").split(",")}
head = meta[:meta.index('case "${TARGET_TYPE}"')]
cores = {c.removesuffix("-lr").removesuffix("_lr") for c in re.findall(r"[\w+-]+[-_]lr\b", head)}
assert cores and not cores - listed, sorted(cores - listed)
