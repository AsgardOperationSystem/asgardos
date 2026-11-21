#!/usr/bin/env python3
# spec: GAME-11
# Reads the emulators' shipped pad configs and checks each against the pad games see: InputPlumber's virtual DualSense
# (GAME-9), as SDL2 numbers it through evdev (GUID 0300fd57...11810000, checked on a Thor 2026-11-21). The emulated A is
# the Thor's printed A (east), B is B (south), X is X (north), Y is Y (west); a PlayStation's Cross is south. Home alone
# is Asgard's (MENU-1), so nothing binds it alone. A config numbered for the raw Thor pad (AYN Odin2 Gamepad: Select b6,
# Start b7, Home b8, d-pad b11-b14) binds the wrong buttons here.
import os
import re
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..")
SA = os.path.join(ROOT, "packages", "emulators", "standalone")

# SDL2 joystick buttons of the virtual DualSense: hid-playstation's keys in keycode order.
SOUTH, EAST, NORTH, WEST, L1, R1, L2, R2, SELECT, START, HOME, L3, R3 = range(13)
THOR_A, THOR_B, THOR_X, THOR_Y = EAST, SOUTH, NORTH, WEST

failures = []


def read(*path):
    with open(os.path.join(SA, *path)) as f:
        return f.read()


def keys(text, sep="="):
    """key -> value of key=value / key = value lines (the last one wins)."""
    out = {}
    for line in text.splitlines():
        if sep in line and not line.lstrip().startswith(("#", ";", "[")):
            k, v = line.split(sep, 1)
            out[k.strip()] = v.strip()
    return out


def expect(what, got, want):
    if got != want:
        failures.append(f"{what}: {got!r}, want {want!r}")


def section(text, name):
    """key = value lines of one [name] section of an ini."""
    m = re.search(rf"^\[{re.escape(name)}\]\n(.*?)(?=^\[|\Z)", text, re.M | re.S)
    if not m:
        raise KeyError(f"[{name}]")
    return keys(m.group(1))


def sticks(what, pad, axis):
    """Both sticks point the way they're pushed: left/up on the axis' minus side. axis(name) gives the binding."""
    for stick, side in (("L", "Left"), ("R", "Right")):
        for direction, sign, xy in (("Left", "-", "X"), ("Right", "+", "X"), ("Up", "-", "Y"), ("Down", "+", "Y")):
            expect(f"{what} {stick}{direction}", pad[f"{stick}{direction}"], axis(sign, side, xy))


def duckstation():
    pad = section(read("duckstation-sa", "config", "InputPlumber", "settings.ini"), "Pad1")
    for button, name in (("Cross", "A"), ("Circle", "B"), ("Triangle", "Y"), ("Square", "X")):  # SDL names: by position
        expect(f"DuckStation {button}", pad[button], f"SDL-0/{name}")
    sticks("DuckStation", pad, lambda sign, side, xy: f"SDL-0/{sign}{side}{xy}")


def pcsx2(what, text):
    """ARMSX2 and AetherSX2 (PCSX2's ini): Cross is south, and Home alone opens the pause menu through the Esc that
    thor_ayn_button.py sends, and does nothing in the game."""
    pad = section(text, "Pad1")
    for button, names in (("Cross", ("A", "FaceSouth")), ("Circle", ("B", "FaceEast")),
                          ("Triangle", ("Y", "FaceNorth")), ("Square", ("X", "FaceWest"))):
        if pad[button] not in (f"SDL-0/{n}" for n in names):
            failures.append(f"{what} {button}: {pad[button]!r}, want south/east/north/west by position")
    sticks(what, pad, lambda sign, side, xy: f"SDL-0/{sign}{side}{xy}")
    for k, v in pad.items():
        if v == "SDL-0/Guide":
            failures.append(f"{what}: the PS2's {k} is bound to Home alone")
    hotkeys = re.search(r"^\[Hotkeys\]\n(.*?)(?=^\[|\Z)", text, re.M | re.S).group(1)
    if "OpenPauseMenu = Keyboard/Escape" not in hotkeys.splitlines():
        failures.append(f"{what}: Esc (Home's tap) doesn't open the pause menu")


def armsx2():
    pcsx2("ARMSX2", read("armsx2-sa", "config", "inputplumber", "ARMSX2", "inis", "PCSX2.ini"))


def aethersx2():
    pcsx2("AetherSX2", read("aethersx2-sa", "config", "InputPlumber", "aethersx2", "inis", "PCSX2.ini"))


def drastic():
    """DraStic numbers joystick buttons 1024 + n. The d-pad is a hat, which reaches it as keys from gptokeyb."""
    cfg = keys(read("drastic-sa", "config", "SM8550", "drastic.cfg"))
    b = lambda name: cfg[f"controls_b[CONTROL_INDEX_{name}]"]
    for name, button in (("A", THOR_A), ("B", THOR_B), ("X", THOR_X), ("Y", THOR_Y), ("L", L1), ("R", R1),
                         ("SELECT", SELECT), ("START", START), ("TOUCH_CURSOR_PRESS", R3)):
        expect(f"DraStic {name}", b(name), str(1024 + button))
    for k, v in cfg.items():
        if v == str(1024 + HOME):
            failures.append(f"DraStic: {k} is bound to Home alone")
        if v.isdigit() and 1024 + 13 <= int(v) < 1024 + 64:
            failures.append(f"DraStic: {k} = {v} is a button the virtual DualSense doesn't have")
    gptk = keys(read("drastic-sa", "config", "drastic.gptk"))
    for direction in ("UP", "DOWN", "LEFT", "RIGHT"):
        key = gptk[direction.lower()]
        if len(key) != 1:
            failures.append(f"DraStic: gptokeyb sends no key for the d-pad's {direction.lower()}")
            continue
        for prefix in ("", "UI_"):
            expect(f"DraStic controls_a {prefix}{direction}", cfg[f"controls_a[CONTROL_INDEX_{prefix}{direction}]"],
                   str(ord(key)))


def main():
    for check in (drastic, duckstation, armsx2, aethersx2):
        try:
            check()
        except (KeyError, OSError) as e:
            failures.append(f"{check.__name__}: missing {e}")
    if failures:
        sys.exit("FAIL:\n  " + "\n  ".join(failures))
    print("OK")


if __name__ == "__main__":
    main()
