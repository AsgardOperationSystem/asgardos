#!/usr/bin/env python3
# spec: XFER-3
"""Run: python -I test_sleep_through_transfers.py  (no Thor): every Sleep a user can ask for goes through asgard-transfers.py
sleep, which turns it into a standby while downloads or scrapes run: Home's power menu and Settings, the old settings program,
and power-handler's power key and lid close while busy. A plain `systemctl suspend` is left only where it's meant: the
transfers service itself (and its no-service fallback), power-handler with nothing running, and asgard-charge-fix's lid-shut
resleep after a cable wake. The power key and lid going there is test_power_handler_standby.sh."""
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
PKGS = os.path.normpath(os.path.join(HERE, "..", ".."))
ALLOWED = {"asgard/sources/asgard-transfers.py", "hardware/quirks/platforms/SM8550/bin/power-handler",
           "asgard/sleep.d/asgard-charge-fix"}
SCAN = ("asgard/sources", "asgard/sleep.d", "asgard-home/src/qml", "asgard-home/src", "hardware/quirks/platforms/SM8550")

found = []
for top in SCAN:
    for dirpath, _, files in os.walk(os.path.join(PKGS, top)):
        for f in files:
            if f.startswith("test_") or f.endswith((".png", ".ttf", ".wav", ".svg", ".ogg")):
                continue
            path = os.path.join(dirpath, f)
            rel = os.path.relpath(path, PKGS)
            try:
                text = open(path, encoding="utf-8").read()
            except (UnicodeDecodeError, OSError):
                continue
            for n, line in enumerate(text.splitlines(), 1):
                code = line.split("#", 1)[0] if not f.endswith((".qml", ".cpp", ".h")) else line.split("//", 1)[0]
                if re.search(r"systemctl\s+suspend", code) and rel not in ALLOWED:
                    found.append(f"{rel}:{n}: {line.strip()}")
assert not found, "Sleep that skips asgard-transfers.py sleep:\n" + "\n".join(found)

for rel in ("asgard-home/src/qml/PowerMenu.qml", "asgard-home/src/qml/Settings.qml", "asgard/sources/thor_settings.py"):
    assert "asgard-transfers.py sleep" in open(os.path.join(PKGS, rel)).read() or \
        "transfers + \"sleep\"" in open(os.path.join(PKGS, rel)).read(), rel
print("ok")
