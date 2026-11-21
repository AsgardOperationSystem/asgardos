#!/usr/bin/env python3
# spec: INP-1
"""The gyro reaches SDL games as the motion of InputPlumber's virtual DualSense (INP-1): SDL reads it from the pad's
"Motion Sensors" event node. ROCKNIX's sixaxis rules deleted every such node; this checks, on the image's udev rules,
that no rule deletes the node of a uhid device (the virtual pad), and that the node still isn't taken for a joystick.
That SDL then sees the motion is the device check."""
import fnmatch
import glob
import os
import re
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..")
NODE = {"ACTION": "add", "SUBSYSTEMS": "input", "ENV{DEVNAME}": "/dev/input/event11",
        "ATTRS{name}": "Sony Interactive Entertainment DualSense Wireless Controller Motion Sensors",
        "DEVPATH": "/devices/virtual/misc/uhid/0003:054C:0CE6.0001/input/input12/event11"}


def applies(rule):
    """Whether every match key of a rule line holds for NODE (keys it doesn't know about don't match)."""
    for key, op, value in re.findall(r'([A-Z]+(?:\{[^}]*\})?)\s*(==|!=)\s*"([^"]*)"', rule):
        if key not in NODE:
            return False
        if fnmatch.fnmatchcase(NODE[key], value) != (op == "=="):
            return False
    return True


def main():
    failures, joystick_cleared = [], False
    rules = glob.glob(os.path.join(ROOT, "packages", "**", "udev.d", "*.rules"), recursive=True)
    rules += glob.glob(os.path.join(ROOT, "device", "**", "*.rules"), recursive=True)
    for path in rules:
        for n, line in enumerate(open(path, errors="replace"), 1):
            if line.lstrip().startswith("#") or not applies(line):
                continue
            where = f"{os.path.relpath(path, ROOT)}:{n}"
            if re.search(r'RUN\+?="[^"]*\brm\b', line):
                failures.append(f"{where} deletes the virtual DualSense's motion node")
            if 'ENV{ID_INPUT_JOYSTICK}=""' in line:
                joystick_cleared = True
    if not joystick_cleared:
        failures.append("no rule clears ID_INPUT_JOYSTICK on the motion node, so it could be taken for a second pad")
    if failures:
        sys.exit("FAIL:\n  " + "\n  ".join(failures))
    print("OK")


if __name__ == "__main__":
    main()
