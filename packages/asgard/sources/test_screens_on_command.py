#!/usr/bin/env python3
# spec: PWR-10 OLED-1
# requires: file:build/AsgardOS-SM8550.aarch64/toolchain/usr/local/qt6/lib/libQt6Quick.so cmd:cmake
"""The power handler's `screens-on` command turns Home's X state off, with the panels and stick lights back on, so the next
button isn't swallowed as a wake. power-handler's side is test_power_key_idle_blank.sh."""
import os
import stat
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "tools", "test"))
from home_harness import Root  # noqa: E402

with Root() as r:
    r.library()
    bin_dir = f"{r.path}/fakebin"
    os.makedirs(bin_dir)
    for name, body in (("swaymsg", f'echo "$*" >> {r.path}/sway.log\n'), ("systemctl", ""), ("ledcontrol", "")):
        with open(f"{bin_dir}/{name}", "w") as f:
            f.write("#!/bin/sh\n" + body)
        os.chmod(f"{bin_dir}/{name}", stat.S_IRWXU)
    fifo = f"{r.path}/cmd"

    def send():
        while not os.path.exists(fifo):
            time.sleep(0.05)
        time.sleep(0.8)
        with open(fifo, "w") as f:
            f.write("screens-on\n")

    sender = threading.Thread(target=send, daemon=True)
    sender.start()
    res = r.run("x", ms=1500, env={"ASGARD_CMD_FIFO": fifo, "PATH": f"{bin_dir}:{os.environ['PATH']}"})
    sender.join(1)
    log = open(f"{r.path}/sway.log").read().splitlines()
    assert any("power off" in line for line in log), log
    assert "power on" in log[-1], log
print("OK")
