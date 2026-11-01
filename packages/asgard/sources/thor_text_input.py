#!/usr/bin/env python3
"""A game's text prompt on the bottom screen: sdlui's on-screen keyboard, for emulator frontends that have none.

Eden Duo's eden-cli (patch 0004-eden-cli-software-keyboard) starts it for the Switch's software keyboard, while the
game waits. The text goes to stdout (UTF-8, no newline), exit 0; cancelled: exit 1; it couldn't run: exit 2.

The window goes to DSI-1 by its title (# thor-keyboard in thor-sway-rotate.sh; `assign`, or its fullscreen request
would take fullscreen from the game), with focus left on the game: the pad reaches us by the evdev grab. Asking for
fullscreen takes it from whatever fills DSI-1 (companion, Lumi-Dex), so that gets it back afterwards, and the panel
goes back to the power state it was in. The game can be killed with the keyboard open (Home's quit is -9): we die with it, as a
helper left behind would keep the pad grabbed.
"""
import argparse
import ctypes
import fcntl
import json
import os
import signal
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sdlui  # noqa: E402

TITLE = "Asgard Keyboard (Bottom)"
PR_SET_PDEATHSIG = 1
EVIOCGKEY_96 = 0x80604518  # EVIOCGKEY(96): which keys are down


def sway(*args):
    return subprocess.run(["swaymsg", *args], capture_output=True, text=True)


def bottom_windows():
    """(con id, fullscreen?) of the windows on DSI-1."""
    found = []

    def walk(n, output=None):
        if n.get("type") == "output":
            output = n.get("name")
        if output == "DSI-1" and n.get("pid"):
            found.append((n["id"], n.get("fullscreen_mode") == 1))
        for c in n.get("nodes", []) + n.get("floating_nodes", []):
            walk(c, output)
    p = sway("-t", "get_tree", "-r")
    if p.returncode == 0:
        walk(json.loads(p.stdout))
    return found


def bottom_powered():
    p = sway("-t", "get_outputs", "-r")
    return p.returncode == 0 and any(o["name"] == "DSI-1" and o.get("power") for o in json.loads(p.stdout))


def wait_pad_released(fd, timeout=1.5):
    """The button that closed the keyboard is still down: wait, so the game doesn't get it when it resumes."""
    end = time.monotonic() + timeout
    keys = bytearray(96)
    while fd is not None and time.monotonic() < end:
        try:
            fcntl.ioctl(fd, EVIOCGKEY_96, keys)
        except OSError:
            return
        if not any(keys):
            return
        time.sleep(0.01)


def arg_text(s):
    return os.fsencode(s).decode("utf-8", "replace")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--title", default="")
    ap.add_argument("--initial", default="")
    ap.add_argument("--max", type=int, default=None)
    ap.add_argument("--min", type=int, default=0)
    ap.add_argument("--digits", action="store_true")
    ap.add_argument("--secret", action="store_true")
    ap.add_argument("--no-cancel", action="store_true")
    a = ap.parse_args()

    ctypes.CDLL(None).prctl(PR_SET_PDEATHSIG, signal.SIGTERM)
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(1))
    if os.getppid() == 1:  # the parent went away before prctl
        return 1

    before = bottom_windows()
    powered = bottom_powered()
    ui = sdlui.UI(TITLE, display=1, grab_pad=True)
    try:
        if ui.pad_fd is None:  # no grab: sdlui falls back to SDL's events, which need the focus
            sway(f'[title="^{TITLE}"] focus')
        text = ui.keyboard(arg_text(a.title) or "Enter text", arg_text(a.initial), secret=a.secret, max_len=a.max,
                           min_len=a.min, allowed="0123456789" if a.digits else None, cancel=not a.no_cancel)
        wait_pad_released(ui.pad_fd)
    finally:
        sdlui.sdl.SDL_DestroyWindow(ui.win)
        sdlui.sdl.SDL_Quit()
        time.sleep(0.1)  # sway sees the window go
        fullscreen = [i for i, fs in before if fs]
        if fullscreen:
            sway(f"[con_id={fullscreen[0]}] fullscreen enable")
        sway("focus output DSI-2")
        if not powered:
            sway("output DSI-1 power off")
    if text is None:
        return 1
    os.write(1, text.encode("utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
