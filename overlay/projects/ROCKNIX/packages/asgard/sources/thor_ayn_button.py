#!/usr/bin/env python3
"""Thor buttons daemon (blocking reads, no polling).

* AYN button (KEY_F24 on gpio-keys-ayn): toggle Thor Panel on the bottom screen.
* Button 10 (BTN_MODE on InputPlumber's virtual pad) **tapped alone** (released within TAP_S, nothing else pressed
  meanwhile): open the running emulator's menu, or exit games whose emulator has none. Holding it with other buttons
  is left alone, so ROCKNIX's hotkey combos (it's their modifier) keep working.
  - RetroArch: MENU_TOGGLE over its network command port (runemu.sh enables it on dual-screen devices).
  - PPSSPP, ARMSX2, AetherSX2: Esc (their pause menus), from a small uinput keyboard.
  - anything else (Azahar, melonDS, Dolphin, ...): Asgard Home's in-game menu (paused, save/load, quit...), through
    its command FIFO; exit (SIGTERM, then SIGKILL after EXIT_GRACE_S) if the frontend isn't there to show it.
"""
import fcntl
import os
import select
import signal
import socket
import struct
import subprocess
import time

KEY_F24, BTN_MODE, KEY_ESC, KEY_F4 = 194, 316, 1, 62
EV_SYN, EV_KEY, EV_ABS = 0, 1, 3
ABS_HAT0X, ABS_HAT0Y = 16, 17
TAP_S = 0.5
DEBOUNCE_S = 0.6
EXIT_GRACE_S = 4
PANEL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "thor_panel.py")
EVENT_FMT = "llHHi"
EVENT_SIZE = struct.calcsize(EVENT_FMT)
ESC_EMULATORS = ("ppsspp", "armsx2-qt", "aethersx2")
MENU_FIFO = "/run/asgard-home.cmd"


def find_device(want):
    name = None
    for line in open("/proc/bus/input/devices"):
        if line.startswith("N: Name="):
            name = line.strip()[9:-1]
        elif line.startswith("H: Handlers=") and name == want:
            ev = next(h for h in line.split("=", 1)[1].split() if h.startswith("event"))
            return f"/dev/input/{ev}"
    return None


def frontend_env():
    """Environment of the frontend: essway's main process (start_frontend.sh execs it, so environ is complete)."""
    pid = subprocess.run(["systemctl", "show", "-P", "MainPID", "essway"], capture_output=True, text=True).stdout.strip()
    try:
        raw = open(f"/proc/{pid}/environ", "rb").read()
    except OSError:  # no frontend running ("0" / empty)
        return None
    env = dict(kv.split("=", 1) for kv in raw.decode(errors="replace").split("\0") if "=" in kv)
    env.pop("SDL_GAMECONTROLLERCONFIG", None)
    return env


class Keyboard:
    """Minimal uinput keyboard that can press Esc and F4 (Azahar's pause)."""

    def __init__(self):
        self.fd = os.open("/dev/uinput", os.O_WRONLY | os.O_NONBLOCK)
        fcntl.ioctl(self.fd, 0x40045564, EV_KEY)   # UI_SET_EVBIT
        for key in (KEY_ESC, KEY_F4):
            fcntl.ioctl(self.fd, 0x40045565, key)  # UI_SET_KEYBIT
        dev = struct.pack("80sHHHHi", b"Thor Buttons Keyboard", 0x06, 0x1234, 0x5678, 1, 0) + bytes(4 * 64 * 4)
        os.write(self.fd, dev)                     # legacy struct uinput_user_dev
        fcntl.ioctl(self.fd, 0x5501)               # UI_DEV_CREATE
        time.sleep(0.2)

    def tap(self, code):
        for value in (1, 0):
            os.write(self.fd, struct.pack(EVENT_FMT, 0, 0, EV_KEY, code, value))
            os.write(self.fd, struct.pack(EVENT_FMT, 0, 0, EV_SYN, 0, 0))
            time.sleep(0.05)


def azahar_pause(keyboard, env):
    """F4 to Azahar (pause / resume) after focusing it, so the key reaches it. True if Azahar is running."""
    if "azahar" not in running_game() or not keyboard or not env:
        return False
    subprocess.run('swaymsg "[pid=$(pidof -s azahar)] focus"', shell=True, env=env, capture_output=True)
    keyboard.tap(KEY_F4)
    return True


def running_game():
    """Process names of the running emulator, from ROCKNIX's kill-hotkey target ('' = in the frontend)."""
    try:
        words = open("/tmp/.process-kill-data").read().split()
    except OSError:
        return []
    names = [w for w in words if not w.startswith("-")]
    return [] if names in (["emulationstation"],) else names


def exit_game(names):
    subprocess.run(["killall", "-TERM", *names], capture_output=True)
    deadline = time.time() + EXIT_GRACE_S
    while time.time() < deadline:
        if subprocess.run(["pidof", *names], capture_output=True).returncode:
            return
        time.sleep(0.2)
    subprocess.run(["killall", "-KILL", *names], capture_output=True)


def guide_tap(keyboard):
    names = running_game()
    if not names:
        return
    if "retroarch" in names:
        socket.socket(socket.AF_INET, socket.SOCK_DGRAM).sendto(b"MENU_TOGGLE", ("127.0.0.1", 55355))
    elif any(n in ESC_EMULATORS for n in names) and keyboard:
        keyboard.tap(KEY_ESC)
    elif not frontend_menu():
        exit_game(names)


def frontend_menu():
    try:
        fd = os.open(MENU_FIFO, os.O_WRONLY | os.O_NONBLOCK)  # fails without a reader
    except OSError:
        return False
    try:
        os.write(fd, b"menu\n")
        return True
    finally:
        os.close(fd)


def main():
    # The virtual pad appears a few seconds into boot and InputPlumber re-creates it when it restarts (stick
    # calibration does, at boot): look for it again whenever it's missing, and when reading it fails. Without
    # this the daemon started before the pad and never saw button 10 (2026-10-10).
    fds = {}
    ayn = find_device("gpio-keys-ayn")
    if ayn:
        fds[os.open(ayn, os.O_RDONLY)] = "ayn"

    def pad_fd():
        return next((fd for fd, role in fds.items() if role == "pad"), None)

    def open_pad():
        path = find_device("Sony Interactive Entertainment DualSense Wireless Controller")
        if path:
            fds[os.open(path, os.O_RDONLY)] = "pad"

    try:
        keyboard = Keyboard()
    except OSError:
        keyboard = None
    panel, paused = None, False
    guide_down, other_pressed, last_tap = None, False, 0.0
    while True:
        if pad_fd() is None:
            open_pad()
        if paused and panel and panel.poll() is not None:  # panel closed (AYN again, B, or a tile): resume
            paused = False
            azahar_pause(keyboard, frontend_env())
        waiting = pad_fd() is None or paused  # poll for the pad to appear / the panel to close
        for fd in select.select(list(fds), [], [], 0.5 if waiting else None)[0]:
            try:
                data = os.read(fd, EVENT_SIZE)
            except OSError:  # the pad went away (InputPlumber restarted): drop it, the loop finds the new one
                os.close(fd)
                del fds[fd]
                continue
            _, _, etype, code, value = struct.unpack(EVENT_FMT, data)
            if fds[fd] == "ayn":
                if etype == EV_KEY and code == KEY_F24 and value == 1:
                    if panel and panel.poll() is None:
                        panel.send_signal(signal.SIGTERM)  # the loop below resumes a paused game
                    else:
                        env = frontend_env()
                        if env:
                            paused = azahar_pause(keyboard, env)  # the game waits while the panel is open
                            panel = subprocess.Popen(["python3", PANEL], env=env, start_new_session=True,
                                                     stdout=subprocess.DEVNULL,
                                                     stderr=open("/tmp/thor-panel.log", "a"))
                continue
            # virtual pad: detect a lone tap of button 10
            if etype == EV_KEY and code == BTN_MODE:
                if value == 1:
                    guide_down, other_pressed = time.monotonic(), False
                elif value == 0 and guide_down is not None:
                    # One Home tap reaches us twice in a row (InputPlumber), which opened the in-game menu and
                    # closed it again at once: taps closer than DEBOUNCE_S count once.
                    now = time.monotonic()
                    if not other_pressed and now - guide_down <= TAP_S and now - last_tap > DEBOUNCE_S:
                        last_tap = now
                        guide_tap(keyboard)
                    guide_down = None
            elif guide_down is not None and ((etype == EV_KEY and value == 1) or
                                             (etype == EV_ABS and code in (ABS_HAT0X, ABS_HAT0Y) and value)):
                other_pressed = True  # it's a hotkey combo, not a tap


if __name__ == "__main__":
    main()
