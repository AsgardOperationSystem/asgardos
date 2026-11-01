#!/usr/bin/env python3
# spec: PWR-11
# requires: cmd:bash cmd:flock
"""A sleep mode has to reach systemd's sleep.conf and stay there, both when Settings picks it (the key first, then
`suspendmode <mode>`) and at every boot (030-suspend_mode, then 009-sleepmode). What's offered is test_home_offers.py."""
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
            # The host's bash is older than the image's, and its /bin/sh may not be bash, as the Thor's is.
            f.write(text.replace("local -a keys=() BASH_REMATCH", "local -a keys=()").replace("#!/bin/sh", "#!/bin/bash", 1))
        os.chmod(f"{t}/{dest}", stat.S_IRWXU)

    install("../../asgardos/profile.d/001-functions", "etc/profile.d/001-functions")
    install("../../asgardos/sources/scripts/suspendmode", "usr/bin/suspendmode")
    install("../../asgardos/autostart/009-sleepmode", "usr/lib/009-sleepmode")
    install("../../hardware/quirks/platforms/SM8550/030-suspend_mode", "usr/lib/030-suspend_mode")
    open(f"{t}/etc/os-release", "w").close()
    with open(f"{t}/etc/profile", "w") as f:
        f.write(f". {t}/etc/profile.d/001-functions\n")
    for d in ("storage/.config/sleep.conf.d", "storage/.config/system/configs", "tmp", ".config/logind.conf.d"):
        os.makedirs(f"{t}/{d}")
    for name, body in (("systemctl", f'echo "$@" >> {t}/systemctl.log\n'), ("tocon", "")):
        with open(f"{t}/usr/bin/{name}", "w") as f:
            f.write("#!/bin/sh\n" + body + "exit 0\n")
        os.chmod(f"{t}/usr/bin/{name}", stat.S_IRWXU)
    env = {"PATH": "/usr/bin:/bin", "HOME": t, "QUIRK_DEVICE": "AYN Thor", "HW_DEVICE": "SM8550"}
    cfg = f"{t}/storage/.config/system/configs/system.cfg"
    sleep_d = f"{t}/storage/.config/sleep.conf.d"

    def boot(saved, *scripts):
        """The saved mode, then the scripts. Returns every sleep.conf.d file, in the order systemd reads them."""
        with open(cfg, "w") as f:
            f.write(f"system.suspendmode={saved}\n" if saved else "")
        for script in scripts:
            subprocess.run(["bash", f"{t}/usr/{script}"] if script.startswith("lib") else ["bash", f"{t}/usr/bin/suspendmode", script],
                           capture_output=True, timeout=30, env=env)
        return "".join(open(f"{sleep_d}/{n}").read() for n in sorted(os.listdir(sleep_d)))

    def state(conf):
        """What systemd ends up with: an empty assignment resets the list, and the last one wins."""
        return [line.split("=", 1)[1] for line in conf.splitlines() if line.startswith("SuspendState=")][-1]

    # Settings saves the key first, so suspendmode can't use it to tell whether anything changed.
    conf = boot("freeze", "freeze")
    assert state(conf).startswith("freeze"), conf
    conf = boot("off", "off")
    assert "AllowSuspend=no" in conf, conf
    conf = boot("mem", "mem")
    assert state(conf).startswith("mem"), conf

    # At boot a chosen mode stays chosen, and no file overrides it. A Thor updated from an older image has that file.
    BOOT = ("lib/030-suspend_mode", "lib/009-sleepmode")
    with open(f"{sleep_d}/zz-sm8550-deeponly.conf", "w") as f:
        f.write("[Sleep]\nSuspendState=\nSuspendState=mem\n")
    conf = boot("freeze", *BOOT)
    assert state(conf).startswith("freeze"), conf
    assert not os.path.exists(f"{sleep_d}/zz-sm8550-deeponly.conf")
    conf = boot("off", *BOOT)
    assert "AllowSuspend=no" in conf, conf
    assert "system.suspendmode=off" in open(cfg).read(), "a reboot undid Screen off only"
    conf = boot("", *BOOT)
    assert state(conf).startswith("mem") and "system.suspendmode=mem" in open(cfg).read(), conf

    # systemd reads sleep.conf whenever it's asked (parse_sleep_config): a change mustn't restart logind under a session.
    if os.path.exists(f"{t}/systemctl.log"):
        os.remove(f"{t}/systemctl.log")
    boot("mem", "freeze")
    log = open(f"{t}/systemctl.log").read() if os.path.exists(f"{t}/systemctl.log") else ""
    assert "logind" not in log, log
print("OK")
