#!/usr/bin/env python3
"""Thor buttons daemon (blocking reads, no polling).

* AYN button (KEY_F24 on gpio-keys-ayn): toggle Thor Panel (asgard-panel --panel, Asgard Home's qml/Panel.qml with
  thor_panel.py behind it) on the bottom screen. The running game is frozen (SIGSTOP) while it's open and continues
  (SIGCONT) when it closes: AYN again, or a tile that closes it. Asgard Home's bottom window steps aside meanwhile.
* Button 10 (BTN_MODE on InputPlumber's virtual pad) **tapped alone** (released within TAP_S, nothing else pressed
  meanwhile): open the running emulator's menu, or exit games whose emulator has none. Holding it with other buttons
  is left alone, so ROCKNIX's hotkey combos (it's their modifier) keep working.
  - RetroArch: Asgard Home's in-game menu too (it has a "RetroArch menu" entry); RetroArch's own menu
    (MENU_TOGGLE over its network command port, enabled by runemu.sh on dual-screen devices) without a frontend.
  - PPSSPP, ARMSX2, AetherSX2: Esc (their pause menus); Flycast: F1 (its menu, bound by start_flycast.sh), from a
    small uinput keyboard.
  - Steam: InputPlumber turns Home into F20 on its keyboard while Steam runs (steam-pad-profile.py), so Steam
    never sees it; F20 opens Asgard Home's in-game menu (Steam overlay / Quick Access entries), or Steam's own
    overlay without a frontend.
  - anything else (Azahar, melonDS, Dolphin, ...): Asgard Home's in-game menu (paused, save/load, quit...), through
    its command FIFO; exit (SIGTERM, then SIGKILL after EXIT_GRACE_S) if the frontend isn't there to show it.
"""
import fcntl
import json
import os
import select
import signal
import socket
import struct
import subprocess
import time

KEY_F24, KEY_F20, BTN_MODE, KEY_ESC, KEY_F1 = 194, 190, 316, 1, 59
EV_SYN, EV_KEY, EV_ABS = 0, 1, 3
ABS_HAT0X, ABS_HAT0Y = 16, 17
TAP_S = 0.5
DEBOUNCE_S = 0.6
EXIT_GRACE_S = 4
PANEL = ["asgard-panel", "--panel"]
HOME_BOTTOM_Q = '[title="^Asgard Home .Bottom.$"]'
EVENT_FMT = "llHHi"
EVENT_SIZE = struct.calcsize(EVENT_FMT)
MENU_KEYS = {"ppsspp": KEY_ESC, "armsx2-qt": KEY_ESC, "aethersx2": KEY_ESC, "flycast": KEY_F1}  # their menu keys
MENU_FIFO = "/run/asgard-home.cmd"
OSK_PID = "/run/asgard-osk.pid"     # start_firefox.sh: its touch keyboard (wvkbd) on the bottom screen
BACKGROUND = "/run/asgard-bg.json"   # asgard-background.py: a game is frozen behind Asgard Home ("Back to Home")


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
    """Minimal uinput keyboard that can press the emulators' menu keys."""

    def __init__(self):
        self.fd = os.open("/dev/uinput", os.O_WRONLY | os.O_NONBLOCK)
        fcntl.ioctl(self.fd, 0x40045564, EV_KEY)   # UI_SET_EVBIT
        for key in set(MENU_KEYS.values()):
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


def freeze_game(stop):
    """SIGSTOP (stop) / SIGCONT the running game's processes; works for every emulator, unlike their own pause keys.
    Steam is left alone (it has its own overlay). Returns whether anything was frozen."""
    names = [n for n in running_game() if n != "steam"]
    if not names or "steam" in running_game() or os.path.exists(BACKGROUND):  # a background game stays frozen
        return False
    subprocess.run(["killall", "-STOP" if stop else "-CONT", *names], capture_output=True)
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
    if not names or "steam" in names or os.path.exists(BACKGROUND):   # Home itself is in front: a plain tap   # Steam: Home is its Quick Access button (steam-pad-profile.py)
        return
    if "retroarch" in names:
        if not frontend_menu():
            socket.socket(socket.AF_INET, socket.SOCK_DGRAM).sendto(b"MENU_TOGGLE", ("127.0.0.1", 55355))
    elif any(n in MENU_KEYS for n in names) and keyboard:
        name = next(n for n in names if n in MENU_KEYS)
        env = frontend_env()   # focus it first, so the key reaches it (not the bottom screen)
        if env:
            subprocess.run(f'swaymsg "[pid=$(pidof -s {name})] focus"', shell=True, env=env, capture_output=True)
        keyboard.tap(MENU_KEYS[name])
    elif not frontend_menu():
        exit_game(names)


def steam_home():
    """Home while Steam runs (F20 from InputPlumber): our menu, else Steam's overlay (Guide, past the profile)."""
    if "steam" in running_game() and not os.path.exists(BACKGROUND) and not frontend_menu():
        subprocess.run(["busctl", "call", "org.shadowblip.InputPlumber", "/org/shadowblip/InputPlumber/CompositeDevice0",
                        "org.shadowblip.Input.CompositeDevice", "SendButtonChord", "as", "1", "Gamepad:Button:Guide"],
                       capture_output=True)


def park(env):
    subprocess.run(["swaymsg", f"{HOME_BOTTOM_Q} move container to workspace thor-park"], env=env, capture_output=True)


def unpark(env):
    """After the panel: Asgard Home's bottom window back on DSI-1, or the panel off if nothing is to show there."""
    subprocess.run(["swaymsg", "focus output DSI-2"], env=env, capture_output=True)
    p = subprocess.run(["swaymsg", "-t", "get_tree", "-r"], env=env, capture_output=True, text=True)
    if p.returncode:
        return

    def busy(n, o=None):
        if n.get("type") == "output":
            o = n.get("name")
        if o == "DSI-1" and n.get("pid") and n.get("name") not in ("Thor Panel (Bottom)", "Asgard Home (Bottom)"):
            return True
        return any(busy(c, o) for c in n.get("nodes", []) + n.get("floating_nodes", []))
    if busy(json.loads(p.stdout)):
        return  # a game owns the bottom screen; Asgard Home stays parked meanwhile
    if '"Asgard Home (Bottom)"' in p.stdout:
        subprocess.run(["swaymsg", f"{HOME_BOTTOM_Q} move container to output DSI-1"], env=env, capture_output=True)
        if not running_game():
            return
        # In a game Home's bottom window is hidden: the panel would stay lit (and touchable, which pauses
        # RetroArch) until Home came back. Off, like thor-bottom-idle-off.sh does at game start.
    subprocess.run(["swaymsg", "output DSI-1 power off"], env=env, capture_output=True)


def osk(show):
    """A tool's touch keyboard covers the bottom screen (a layer above windows): hidden while the panel is open."""
    try:
        os.kill(int(open(OSK_PID).read()), signal.SIGUSR2 if show else signal.SIGUSR1)
    except (OSError, ValueError):
        pass


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
        if "kbd" not in fds.values():   # InputPlumber's keyboard: F20 = Home while Steam runs
            path = find_device("InputPlumber Keyboard")
            if path:
                fds[os.open(path, os.O_RDONLY)] = "kbd"

    try:
        keyboard = Keyboard()
    except OSError:
        keyboard = None
    freeze_game(False)  # a game frozen by a previous run of this daemon (crash/restart) would stay stopped
    panel, paused, panel_env = None, False, None
    guide_down, other_pressed, last_tap = None, False, 0.0
    while True:
        if pad_fd() is None:
            open_pad()
        if panel and panel.poll() is not None:  # panel closed (AYN again, B, or a tile): resume
            panel = None
            unpark(panel_env)
            osk(True)
            if paused:
                paused = False
                freeze_game(False)
        waiting = pad_fd() is None or panel is not None  # poll for the pad to appear / the panel to close
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
                        env = panel_env = frontend_env()
                        if env:
                            paused = freeze_game(True)  # the game waits while the panel is open
                            osk(False)
                            park(env)
                            panel = subprocess.Popen(PANEL, env=env, start_new_session=True,
                                                     stdout=subprocess.DEVNULL,
                                                     stderr=open("/tmp/thor-panel.log", "a"))
                continue
            if fds[fd] == "kbd":
                if etype == EV_KEY and code == KEY_F20 and value == 1 and time.monotonic() - last_tap > DEBOUNCE_S:
                    last_tap = time.monotonic()
                    steam_home()
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
