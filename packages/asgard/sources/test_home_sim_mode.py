# spec: DEV-16 DEV-18
# requires: file:build/AsgardOS-SM8550.aarch64/toolchain/usr/local/qt6/lib/libQt6Quick.so cmd:cmake
"""Run: python -I test_home_sim_mode.py  (no Thor): Asgard Home's simulated-Thor mode, ASGARD_SIM, which the
asgard-simulator repository runs it in to render its screens on a desktop. In it Home runs no command: exec answers
from the root's sim/exec.json (first matching regex, else ""), and RetroArch's network commands are only logged. The
name, version and free space it shows are the root's, never the desktop's (DEV-16)."""
import json
import os
import socket
import stat
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../../tools/test"))
from home_harness import CFG, Root  # noqa: E402

SIM = {"ASGARD_SIM": "1"}
ABOUT = "start down down down down down a"

with Root() as r:
    r.library()
    r.write(CFG, "system.hostname=SimThor\n")
    r.write("etc/os-release", 'OS_NAME="AsgardOS"\nOS_VERSION="9.9.9"\nBUILD_ID="abcdef0123"\nHW_DEVICE="SM8550"\n')
    r.write("sim/space", "12 GB free of 34 GB\n")
    r.write("sim/exec.json", json.dumps([{"match": "^uname -r", "out": "1.2.3-sim"},
                                         {"match": "uname", "out": "second match, never used"}]))

    about = r.run(ABOUT, env=SIM)
    assert about.shows("●  SimThor") and about.shows("Version 9.9.9") and about.shows("1.2.3-sim"), about.texts
    host = socket.gethostname()
    assert not any(host in t for t in about.texts), host
    assert "\nexec: " not in "\n" + about.log and "sim exec: uname -r (9 bytes)" in about.log, about.log
    assert "sim exec: cat /usr/share/asgard/emulator-versions 2>/dev/null (0 bytes)" in about.log   # no answer: ""

    # Without it, the desktop answers: its hostname, and exec reaches the desktop branch
    plain = r.run(ABOUT)
    assert "\nexec: " in "\n" + plain.log, plain.log

    files = r.run("", args=("--files",), env=SIM)
    assert files.shows("12 GB free of 34 GB"), files.texts

    # A game in play, as RetroArch: the menu's pause is logged, not sent to 127.0.0.1:55355
    fake = f"{r.path}/runemu"
    r.write("runemu", '#!/bin/sh\necho retroarch >"$ASGARD_KILL_DATA"\necho menu >"$ASGARD_CMD_FIFO"\n'
                      'i=0; while [ $i -lt 100 ] && kill -0 $PPID 2>/dev/null; do sleep 0.1; i=$((i+1)); done\n')
    os.chmod(fake, os.stat(fake).st_mode | stat.S_IXUSR)
    game = r.run("a a", ms=2500, env={**SIM, "ASGARD_RUNEMU": fake, "ASGARD_KILL_DATA": f"{r.path}/kill-data",
                                      "ASGARD_CMD_FIFO": f"{r.path}/cmd"})
    assert game.shows("Resume") and "sim retroarch: PAUSE_TOGGLE" in game.log, game.log
print("ok")
