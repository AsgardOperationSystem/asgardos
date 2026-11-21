#!/usr/bin/env python3
# spec: LIB-2 LIB-5
# requires: file:build/AsgardOS-SM8550.aarch64/toolchain/usr/local/qt6/lib/libQt6Quick.so cmd:cmake
"""Run: python -I test_home_library_manager.py  (no Thor): Asgard Home's side of the Library Manager, offscreen. LIB-2: the code
asgard-library.py sends through the command FIFO shows on screen, and Home tells the service it's shown; Refuse (B) tells it
the user said no; pair-end takes it away; the code never reaches the log. LIB-5: Settings > Hardware > Network has the Library
Manager, on by default, with its address and paired browsers. The service's side is test_asgard_library.py."""
import os
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "tools", "test"))
from home_harness import Root  # noqa: E402


def with_commands(r, keys, commands, ms):
    """Home pressing keys after the commands reach its FIFO, each after the delay before it ([(s, line)])."""
    fifo = f"{r.path}/cmd"

    def send():
        while not os.path.exists(fifo):
            time.sleep(0.05)
        for delay, line in commands:
            time.sleep(delay)
            with open(fifo, "w") as f:
                f.write(line + "\n")

    t = threading.Thread(target=send, daemon=True)
    t.start()
    return r.run(keys, ms=ms, env={"ASGARD_CMD_FIFO": fifo})


with Root() as r:
    r.library()
    res = with_commands(r, "", [(0.6, "pair 042917 192.168.1.23")], 1500)
    assert res.shows("Code  042 917") and res.shows("A browser at 192.168.1.23 wants to manage your games"), res.texts
    assert "shell: echo 042917 > /run/asgard-library-pin" in res.log, res.log[-1500:]
    assert "042917" not in "".join(l for l in res.log.splitlines() if "command:" in l), res.log   # not in the journal
    # pair-end: paired, run out, or the browser gave up: the code goes
    res = with_commands(r, "", [(0.6, "pair 042917 192.168.1.23"), (0.4, "pair-end")], 1700)
    assert not res.shows("Code  042 917"), res.texts
    assert "touch /run/asgard-library-pair.cancel" not in res.log   # nobody refused

# B while the code shows refuses: the service is told. The code is written as soon as Home opens its FIFO, so it's up
# before the keys are pressed.
with Root() as r:
    r.library()
    fifo = f"{r.path}/cmd"
    os.mkfifo(fifo)

    def early():
        with open(fifo, "w") as f:   # opens once Home opens it: the code arrives before the keys are pressed
            f.write("pair 042917 192.168.1.23\n")
    threading.Thread(target=early, daemon=True).start()
    res = r.run("b", ms=1200, env={"ASGARD_CMD_FIFO": fifo})
    assert "shell: touch /run/asgard-library-pair.cancel" in res.log, res.log[-1500:]
    assert not res.shows("Code  042 917"), res.texts

# LIB-5: Settings > Hardware > Network: the Library Manager, on by default, opened on its own page
NETWORK = "start down down down down a down down down a"
with Root() as r:
    r.library()
    res = r.run(NETWORK, ms=600)
    assert res.shows("Library Manager") and res.shows("Manage games from a browser"), res.texts
    page = NETWORK + " down" * 7 + " a"                               # its own page: the switch, the address, forget
    res = r.run(page, ms=600)
    assert res.shows("Address") and res.shows("Forget paired browsers"), res.texts
    assert "exec: python3 /usr/share/asgard/asgard-library.py sessions" in res.log
    assert "shell: systemctl stop asgard-library" in r.run(page + " a", ms=600).log          # off
    r.write("storage/.config/system/configs/system.cfg", "")
    asked = r.run(page + " down down a", ms=600)
    assert asked.shows("Every browser will need a new code") and "asgard-library.py forget" not in asked.log
    assert "exec: python3 /usr/share/asgard/asgard-library.py forget" in r.run(page + " down down a a", ms=600).log
    r.write("storage/.config/system/configs/system.cfg", "asgard.library_manager=0\n")
    res = r.run(NETWORK, ms=600)
    assert res.shows("Library Manager") and not res.shows("Manage games from a browser"), res.texts
print("ok")
