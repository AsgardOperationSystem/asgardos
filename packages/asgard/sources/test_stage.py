#!/usr/bin/env python3
# spec: UPD-2 UPD-3
# requires: cmd:bash cmd:sha256sum
# Runs the real `./build.sh stage` from a temp copy, with fake ssh and scp on PATH and a temp dir as the device's
# /storage/.update: a good copy lands as *.tar with nothing left over, a damaged or cut-off copy never does, the installer's
# globs can't match the temporary name, and nothing reboots or touches a game. UPD-3's "installs on the next boot" itself
# is a human check (docs/human-checks.md).
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
from fnmatch import fnmatch

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
NAME = "AsgardOS-SM8550.aarch64-test.tar"
PAYLOAD = b"not really an update\n" * 1000
# Anything that could reboot or disturb the device. A fake of each logs itself; kill is a shell builtin, so the commands
# sent over ssh are searched for them too.
DISTURBS = ["reboot", "poweroff", "halt", "shutdown", "systemctl", "pkill", "killall", "swaymsg", "telinit"]

FAKE_SSH = """#!/bin/sh
# ssh HOST COMMAND: run it here, with the device's paths moved into the temp dir
shift
echo "$*" >> "$STAGE_LOG/ssh"
exec sh -c "$(printf '%s' "$*" | sed "s#/storage/.update#$STAGE_DEVICE#g")"
"""

FAKE_SCP = """#!/bin/sh
# scp -q SRC HOST:DEST, as told by STAGE_SCP: whole, truncated (a bad copy that scp doesn't notice), or dies halfway
dest=${3#*:}
echo "$dest" >> "$STAGE_LOG/scp"
dest=$(printf '%s' "$dest" | sed "s#/storage/.update#$STAGE_DEVICE#")
case $STAGE_SCP in
  whole) cat "$2" > "$dest" ;;
  truncated) head -c 100 "$2" > "$dest" ;;
  dies) head -c 100 "$2" > "$dest"; exit 1 ;;
esac
"""


def write_script(path, text):
    with open(path, "w") as f:
        f.write(text)
    os.chmod(path, 0o755)


def stage(mode):
    """Runs a stage with the fake scp in this mode; returns (exit code, output, device files, ssh commands, scp targets, disturbers)."""
    with tempfile.TemporaryDirectory() as tmp:
        tree, device, logs, fakes = [os.path.join(tmp, d) for d in ("tree", "device", "logs", "fakes")]
        os.makedirs(os.path.join(tree, "build", "target"))
        for d in (device, logs, fakes):
            os.mkdir(d)
        shutil.copy(os.path.join(ROOT, "build.sh"), tree)
        tar = os.path.join(tree, "build", "target", NAME)
        with open(tar, "wb") as f:
            f.write(PAYLOAD)
        with open(tar + ".sha256", "w") as f:
            f.write(f"{hashlib.sha256(PAYLOAD).hexdigest()}  {NAME}\n")
        write_script(os.path.join(fakes, "ssh"), FAKE_SSH)
        write_script(os.path.join(fakes, "scp"), FAKE_SCP)
        for program in DISTURBS:
            write_script(os.path.join(fakes, program), f'#!/bin/sh\necho {program} >> "$STAGE_LOG/disturbed"\n')
        env = dict(os.environ, PATH=fakes + os.pathsep + os.environ["PATH"],
                   STAGE_LOG=logs, STAGE_DEVICE=device, STAGE_SCP=mode)
        proc = subprocess.run(["bash", os.path.join(tree, "build.sh"), "stage", "root@thor.invalid"],
                              env=env, capture_output=True, text=True, timeout=60)

        def log(name):
            path = os.path.join(logs, name)
            return open(path).read().splitlines() if os.path.exists(path) else []
        files = {f: open(os.path.join(device, f), "rb").read() for f in os.listdir(device)}
        return proc.returncode, proc.stdout + proc.stderr, files, log("ssh"), log("scp"), log("disturbed")


def fail(message, detail=""):
    sys.exit(f"FAIL: {message}\n{detail}")


def check_disturbs_nothing(mode, commands, disturbed):
    if disturbed:
        fail(f"{mode}: staging ran {disturbed} (SPEC UPD-3)")
    pattern = r"\b(kill|" + "|".join(DISTURBS) + r")\b|/run/"
    for command in commands:
        if re.search(pattern, command):
            fail(f"{mode}: the command sent to the device could disturb it (SPEC UPD-3): {command}")


def main():
    # A good copy: under a temporary name first, then the real one, and nothing else left behind.
    rc, out, files, ssh, scp, disturbed = stage("whole")
    if rc != 0:
        fail("a good copy didn't stage", out)
    if files != {NAME: PAYLOAD}:
        fail(f"after a good copy the device should hold just {NAME}, whole: {sorted(files)}", out)
    if len(scp) != 1 or scp[0].endswith(".tar"):
        fail(f"the copy must go to a temporary name, not *.tar (SPEC UPD-2): {scp}")
    if len(ssh) != 1 or "sha256sum -c" not in ssh[0]:
        fail(f"the checksum must be checked on the device (SPEC UPD-2): {ssh}")
    check_disturbs_nothing("good copy", ssh, disturbed)
    temp_name = os.path.basename(scp[0])

    # The copy arrives damaged: the checksum catches it.
    rc, out, files, ssh, _, disturbed = stage("truncated")
    if rc == 0:
        fail("a bad checksum must fail the stage (SPEC UPD-2)", out)
    if files:
        fail(f"a bad checksum must leave nothing on the device (SPEC UPD-2): {sorted(files)}", out)
    check_disturbs_nothing("bad checksum", ssh, disturbed)

    # The copy dies halfway (the device rebooted mid-transfer): no rename is even attempted.
    rc, out, files, ssh, _, disturbed = stage("dies")
    if rc == 0 or ssh:
        fail(f"a dead copy must stop the stage before the device is asked to rename it (SPEC UPD-2): exit {rc}, {ssh}", out)
    if NAME in files:
        fail("a dead copy must not look like an update (SPEC UPD-2)", out)
    check_disturbs_nothing("dead copy", ssh, disturbed)

    # What's left of that copy mustn't be something the installer picks up.
    init = os.path.join(ROOT, "packages", "sysutils", "busybox", "scripts", "init")
    with open(init) as f:
        globs = re.findall(r'"\$\{UPDATE_DIR\}"/(\*[^ ]*)', f.read())
    if "*.tar" not in globs:
        fail(f"didn't find the installer's *.tar glob in {init}: {globs}")
    caught = [g for g in globs if fnmatch(temp_name, g)]
    if caught:
        fail(f"the installer's {caught} matches the temporary name {temp_name} (SPEC UPD-2)")
    print("OK")


if __name__ == "__main__":
    main()
