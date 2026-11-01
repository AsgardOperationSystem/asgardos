# spec: MENU-1 MENU-3 PANEL-1
# requires: cmd:python3
"""Run: python -I test_ayn_button.py  (no Thor): thor_ayn_button.py's real loop, reading key events from FIFOs in a temp dir,
with what it would run on the Thor recorded instead. MENU-1: a lone tap against a hotkey combo; that the menu shows on the
bottom screen is test_home_windows.py. MENU-3: which key each emulator's own menu gets. PANEL-1: open, freeze, close, continue;
that it lands on the bottom screen is test_home_windows.py's window title, and on a Thor a device check."""
import os
import shutil
import struct
import sys
import tempfile
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import thor_ayn_button as btn  # noqa: E402

EV_KEY, EV_ABS = 1, 3
BTN_A, BTN_MODE, HAT0X = 305, 316, 16
EVENT = struct.Struct(btn.EVENT_FMT)
tmp = tempfile.mkdtemp()
fifos = {}
for name in ("gpio-keys-ayn", "Sony Interactive Entertainment DualSense Wireless Controller"):
    fifos[name] = f"{tmp}/{len(fifos)}"
    os.mkfifo(fifos[name])
writers = {name: os.open(path, os.O_RDWR) for name, path in fifos.items()}   # read-write: never blocks, never EOF
AYN, PAD = writers.values()


class FakePanel:
    def __init__(self, cmd, **_):
        self.cmd, self.signals, self.done = cmd, [], False
        panels.append(self)

    def poll(self):
        return 0 if self.done else None

    def send_signal(self, sig):
        self.signals.append(sig)
        self.done = True


class Completed:
    stdout, returncode = "", 0


def fake_run(cmd, **_):
    ran.append(cmd if isinstance(cmd, str) else " ".join(cmd))
    return Completed()


panels, ran, taps = [], [], []
game = ["azahar"]
real_guide_tap, real_freeze = btn.guide_tap, btn.freeze_game
btn.find_device = lambda want: fifos.get(want)
btn.Keyboard = lambda: (_ for _ in ()).throw(OSError())   # no /dev/uinput here
btn.frontend_env = lambda: {"WAYLAND_DISPLAY": "x"}
btn.running_game = lambda: game
btn.park = btn.unpark = btn.osk = btn.save_fps = lambda *_: None
btn.BACKGROUND = f"{tmp}/no-background"
btn.FPS_FILE = f"{tmp}/fps"
btn.guide_tap = lambda keyboard: taps.append(time.monotonic())
btn.subprocess.Popen = FakePanel
btn.subprocess.run = fake_run
threading.Thread(target=btn.main, daemon=True).start()


def send(fd, etype, code, value):
    os.write(fd, EVENT.pack(0, 0, etype, code, value))


def settle(seconds=0.1):
    time.sleep(seconds)


def wait_for(check, what):
    for _ in range(100):
        if check():
            return
        time.sleep(0.02)
    raise AssertionError(what)


settle(0.3)

# MENU-1: tapped alone, once; held with another button or the d-pad, or long, it stays the hotkey modifier
send(PAD, EV_KEY, BTN_MODE, 1)
send(PAD, EV_KEY, BTN_MODE, 0)
settle()
assert len(taps) == 1
settle(btn.DEBOUNCE_S + 0.05)
send(PAD, EV_KEY, BTN_MODE, 1)
send(PAD, EV_KEY, BTN_A, 1)
send(PAD, EV_KEY, BTN_A, 0)
send(PAD, EV_KEY, BTN_MODE, 0)
send(PAD, EV_KEY, BTN_MODE, 1)
send(PAD, EV_ABS, HAT0X, 1)
send(PAD, EV_KEY, BTN_MODE, 0)
send(PAD, EV_KEY, BTN_MODE, 1)
settle(btn.TAP_S + 0.1)
send(PAD, EV_KEY, BTN_MODE, 0)
settle()
assert len(taps) == 1
send(PAD, EV_KEY, BTN_MODE, 1)   # InputPlumber doubles a tap: it counts once
send(PAD, EV_KEY, BTN_MODE, 0)
send(PAD, EV_KEY, BTN_MODE, 1)
send(PAD, EV_KEY, BTN_MODE, 0)
settle()
assert len(taps) == 2

# PANEL-1: the AYN button opens it and freezes the game; again closes it and continues the game
send(AYN, EV_KEY, btn.KEY_F24, 1)
wait_for(lambda: panels, "the panel didn't open")
assert panels[0].cmd == btn.PANEL
wait_for(lambda: "killall -STOP azahar" in ran, "the game wasn't frozen")
assert "killall -CONT azahar" not in ran[-1:]
send(AYN, EV_KEY, btn.KEY_F24, 0)
send(AYN, EV_KEY, btn.KEY_F24, 1)
wait_for(lambda: panels[0].done, "the second press didn't close it")
wait_for(lambda: "killall -CONT azahar" in ran, "the game wasn't continued")
# A tile can close it too (Quit game): the game still continues
ran.clear()
send(AYN, EV_KEY, btn.KEY_F24, 1)
wait_for(lambda: len(panels) == 2 and "killall -STOP azahar" in ran, "the panel didn't reopen")
panels[1].done = True
wait_for(lambda: "killall -CONT azahar" in ran, "closing by itself didn't continue the game")
# Nothing running, nothing to freeze; Steam isn't frozen; a game already frozen behind Home stays frozen
for names, background in (([], False), (["steam"], False), (["azahar"], True)):
    ran.clear()
    game[:] = names
    if background:
        open(btn.BACKGROUND, "w").close()
    assert real_freeze(True) is False and real_freeze(False) is False and not ran, names
game[:] = ["azahar"]
os.remove(btn.BACKGROUND)

# MENU-3: their own menus, by their own keys, and never Home's menu; everything else gets Home's
pressed, opened = [], []


class Keys:
    def tap(self, code):
        pressed.append(code)


btn.frontend_menu = lambda: opened.append(1) or True
btn.subprocess.run = lambda *a, **k: Completed()
for name, key in (("ppsspp", btn.KEY_ESC), ("armsx2-qt", btn.KEY_ESC), ("aethersx2", btn.KEY_ESC), ("flycast", btn.KEY_F1)):
    pressed.clear()
    game[:] = [name]
    real_guide_tap(Keys())
    assert pressed == [key] and not opened, name
for name in ("azahar", "melonds", "eden", "retroarch"):
    pressed.clear()
    opened.clear()
    game[:] = [name]
    real_guide_tap(Keys())
    assert opened and not pressed, name
shutil.rmtree(tmp)
print("ok", flush=True)
os._exit(0)                      # the daemon's thread is still in its loop
