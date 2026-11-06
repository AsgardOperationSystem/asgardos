#!/usr/bin/env python3
# spec: PWR-14
# requires: file:build/AsgardOS-SM8550.aarch64/toolchain/usr/local/qt6/lib/libQt6Quick.so cmd:cmake
"""Home shows the battery read at the wake, not the one from before the sleep: the 5 s poll only pauses in a sleep, so it
kept the old level for up to 5 s after the lid opened. A fake /sys under the test root: the level changes, then the
wake command comes (sleep.d/asgard-game-pause sends it after every sleep), and Home shows the new level well inside the
5 s. Without the command it still shows the old one, so the test sees the command, not the poll."""
import os
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "tools", "test"))
from home_harness import Root  # noqa: E402

with Root() as r:
    r.library()
    bat = f"{r.path}/sys/class/power_supply/battery"
    os.makedirs(bat)
    with open(f"{bat}/capacity", "w") as f:
        f.write("48\n")
    with open(f"{bat}/status", "w") as f:
        f.write("Discharging\n")
    fifo = f"{r.path}/cmd"

    def send(cmd):
        while not os.path.exists(fifo):
            time.sleep(0.05)
        time.sleep(0.8)
        with open(f"{bat}/capacity", "w") as f:   # what the gauge says once awake
            f.write("81\n")
        if cmd:
            with open(fifo, "w") as f:
                f.write(cmd + "\n")

    for cmd, want, not_want in (("", "48%", "81%"), ("wake", "81%", "48%")):
        with open(f"{bat}/capacity", "w") as f:
            f.write("48\n")
        sender = threading.Thread(target=send, args=(cmd,), daemon=True)
        sender.start()
        res = r.run("", ms=2000, env={"ASGARD_CMD_FIFO": fifo})   # under the 5 s poll
        sender.join(1)
        assert res.shows(want) and not res.shows(not_want), (cmd or "no command", want, res.texts)
        if os.path.exists(fifo):
            os.unlink(fifo)
print("OK")
