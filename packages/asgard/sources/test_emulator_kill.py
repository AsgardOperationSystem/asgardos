#!/usr/bin/env python3
# spec: GAME-2
# Tree check: every standalone package's start script declares its process with `set_kill set "<signal> <name>"`, or is only a
# dispatcher to scripts that do (start_steam.sh).
import glob
import os
import re

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../.."))
scripts = glob.glob(f"{ROOT}/emulators/standalone/*/**/start_*.sh", recursive=True)
assert scripts
missing = []
for path in scripts:
    with open(path, errors="replace") as f:
        text = f.read()
    if not re.search(r'^[^#\n]*set_kill set "(-\w+ )?[\w.+ ${}@-]+"', text, re.M) and not re.search(r"^[^#\n]*start_\w+\.sh", text, re.M):
        missing.append(os.path.relpath(path, ROOT))
assert not missing, missing
