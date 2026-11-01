#!/usr/bin/env python3
# spec: PWR-11
# requires: cmd:bash cmd:flock
# gap: Settings writes system.suspendmode, then runs suspendmode, which sees no change and does nothing: Light sleep never reaches sleep.conf
"""What Settings does when a sleep mode is picked: the key first, then `suspendmode <mode>`. The mode has to end up in
systemd's sleep.conf. What's offered, and suspendmode from another mode, is test_home_offers.py."""
import os
import re
import stat
import subprocess
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOTED = re.compile(r'(?<![\w.$/}-])/(sys|run|storage|usr|etc|var|tmp)(?=[/\s"\':]|$)', re.M)
with tempfile.TemporaryDirectory() as t:
    def install(source, dest):
        text = ROOTED.sub(lambda m: f"{t}/{m.group(1)}", open(os.path.join(HERE, source)).read())
        os.makedirs(os.path.dirname(f"{t}/{dest}"), exist_ok=True)
        with open(f"{t}/{dest}", "w") as f:
            f.write(text.replace("local -a keys=() BASH_REMATCH", "local -a keys=()"))   # host bash older than the image's
        os.chmod(f"{t}/{dest}", stat.S_IRWXU)

    install("../../asgardos/profile.d/001-functions", "etc/profile.d/001-functions")
    install("../../asgardos/sources/scripts/suspendmode", "usr/bin/suspendmode")
    open(f"{t}/etc/os-release", "w").close()
    with open(f"{t}/etc/profile", "w") as f:
        f.write(f". {t}/etc/profile.d/001-functions\n")
    for d in ("storage/.config/sleep.conf.d", "storage/.config/system/configs", "tmp"):
        os.makedirs(f"{t}/{d}")
    with open(f"{t}/usr/bin/systemctl", "w") as f:
        f.write("#!/bin/sh\nexit 0\n")
    os.chmod(f"{t}/usr/bin/systemctl", stat.S_IRWXU)
    with open(f"{t}/storage/.config/system/configs/system.cfg", "w") as f:
        f.write("system.suspendmode=freeze\n")   # Settings.qml's choice(): set(key, v), then its after(v)
    subprocess.run(["bash", f"{t}/usr/bin/suspendmode", "freeze"], capture_output=True, timeout=30)
    conf = f"{t}/storage/.config/sleep.conf.d/sleep.conf"
    assert os.path.exists(conf), "sleep.conf wasn't written"
    assert "SuspendState=freeze" in open(conf).read()
