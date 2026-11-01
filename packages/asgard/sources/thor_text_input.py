#!/usr/bin/env python3
"""A game's text prompt on the bottom screen: Asgard Home's keyboard, for emulator frontends that have none.

Eden Duo's eden-cli (patch 0004-eden-cli-software-keyboard) starts it for the Switch's software keyboard, while the
game waits. It runs asgard-text-input (asgard-home --text-input, qml/TextInput.qml; arguments passed on), whose stdout
and exit code are the answer: the text, exit 0; cancelled, exit 1; failed, exit 2. Around it, what the keyboard does to
the screens: the window fills DSI-1 (# thor-text-input in thor-sway-rotate.sh), which takes fullscreen from whatever
was there (companion, Lumi-Dex) and powers the panel on, so both go back afterwards.

The game can be killed with the keyboard open (Home's quit is -9): both processes end with it, as a keyboard left behind
would keep the pad grabbed.
"""
import ctypes
import fcntl
import json
import os
import signal
import subprocess
import sys
import time

PR_SET_PDEATHSIG = 1
EVIOCGKEY_96 = 0x80604518  # EVIOCGKEY(96): which keys are down
PAD_NAME = "Sony Interactive Entertainment DualSense Wireless Controller"
SYSTEM_CFG = "/storage/.config/system/configs/system.cfg"


def frontend_env():
    """The frontend's environment (Qt and Mesa as Home runs them), not the game's. essway's main process: as the Panel."""
    try:
        pid = subprocess.run(["systemctl", "show", "-P", "MainPID", "essway"], capture_output=True, text=True).stdout.strip()
        raw = open(f"/proc/{pid}/environ", "rb").read()
        return dict(kv.split("=", 1) for kv in raw.decode(errors="replace").split("\0") if "=" in kv) or dict(os.environ)
    except (OSError, ValueError):
        return dict(os.environ)


def accent():
    value = ""
    try:
        for line in open(SYSTEM_CFG):
            if line.startswith("asgard.accent="):  # the last one wins, as in ROCKNIX's get_setting
                value = line.split("=", 1)[1].strip()
    except OSError:
        pass
    return value


def sway(*args):
    return subprocess.run(["swaymsg", *args], capture_output=True, text=True)


def bottom_fullscreen():
    """Con id of the fullscreen window on DSI-1, if any."""
    def walk(n, output=None):
        if n.get("type") == "output":
            output = n.get("name")
        if output == "DSI-1" and n.get("pid") and n.get("fullscreen_mode") == 1:
            return n["id"]
        for c in n.get("nodes", []) + n.get("floating_nodes", []):
            found = walk(c, output)
            if found:
                return found
        return None
    p = sway("-t", "get_tree", "-r")
    return walk(json.loads(p.stdout)) if p.returncode == 0 else None


def bottom_powered():
    p = sway("-t", "get_outputs", "-r")
    return p.returncode == 0 and any(o["name"] == "DSI-1" and o.get("power") for o in json.loads(p.stdout))


def wait_pad_released(timeout=1.5):
    """The button that closed the keyboard is still down: wait, so the game doesn't get it when it resumes."""
    name = None
    fd = None
    try:
        for line in open("/proc/bus/input/devices"):
            if line.startswith("N: Name="):
                name = line[9:].strip().strip('"')
            elif line.startswith("H: Handlers=") and name == PAD_NAME:
                ev = next((h for h in line[12:].split() if h.startswith("event")), None)
                if ev:
                    fd = os.open("/dev/input/" + ev, os.O_RDONLY | os.O_NONBLOCK)
                    break
        if fd is None:
            return
        end = time.monotonic() + timeout
        keys = bytearray(96)
        while time.monotonic() < end:
            fcntl.ioctl(fd, EVIOCGKEY_96, keys)
            if not any(keys):
                return
            time.sleep(0.01)
    except OSError:
        pass
    finally:
        if fd is not None:
            os.close(fd)


def main():
    ctypes.CDLL(None).prctl(PR_SET_PDEATHSIG, signal.SIGTERM)
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(1))
    if os.getppid() == 1:  # the parent went away before prctl
        return 1

    env = frontend_env()
    os.environ.update({k: env[k] for k in ("WAYLAND_DISPLAY", "SWAYSOCK", "XDG_RUNTIME_DIR") if k in env})
    fullscreen = bottom_fullscreen()
    powered = bottom_powered()
    child = None
    try:
        # stdout goes straight to the caller: only the keyboard's answer is on it.
        child = subprocess.Popen(["asgard-text-input", "--text-input", f"--accent={accent()}", *sys.argv[1:]], env=env)
        code = child.wait()
        wait_pad_released()
        return code if code in (0, 1) else 2
    except OSError as e:
        print(f"thor_text_input: {e}", file=sys.stderr)
        return 2
    finally:
        if child is not None and child.poll() is None:
            child.terminate()
            child.wait()
        time.sleep(0.1)  # sway sees the window go
        if fullscreen:
            sway(f"[con_id={fullscreen}] fullscreen enable")
        sway("focus output DSI-2")
        if not powered:
            sway("output DSI-1 power off")


if __name__ == "__main__":
    sys.exit(main())
