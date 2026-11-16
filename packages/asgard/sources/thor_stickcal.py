#!/usr/bin/env python3
"""Stick and trigger calibration (Settings > Hardware > Calibration > Sticks), in the Settings menus' style.

Replaces GPcal (Kdog's pyxel tool, MIT): the same rsinput parameters and the same maths (95 % of the shorter
half-travel as the range, 150 % of the rest spread as the deadzone, at least 5 % of the range, antideadzone 80 % of
the deadzone), measured with those parameters reset so the driver reports raw values. Each control applies live and
can be tested; Save writes GPcal's line format to the saved calibration (CAL-2), which wins over asgard.yml's (CAL-3).

thor-stickcal.sh runs it with InputPlumber stopped (InputPlumber hides and grabs the raw pad): the pad is read and
grabbed here, so its buttons drive this tool and nothing else. Home leaves at any point and puts back the
calibration that was in place when it started; B steps back (CAL-4).
Usage: thor_stickcal.py
"""
import os
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PARAMS = os.environ.get("RSINPUT_PARAMS", "/sys/module/rsinput/parameters")
SAVED = os.environ.get("GPCAL_SAVED", "/storage/.config/asgard/gpcal.sh")  # asgard-gpcal-apply.sh's file (CAL-2)
PAD_NAME = "AYN Odin2 Gamepad"   # rsinput's raw pad (the Thor's DT names it after the Odin 2)
# The raw pad's buttons, as InputPlumber's ayn_mcu map reads them: BTN_NORTH is the west button and BTN_WEST the north.
RAW_BTN = {305: "east", 304: "south", 307: "west", 308: "north", 314: "select", 315: "start", 310: "l1", 311: "r1",
           316: "home"}
RAW_DPAD = {544: "up", 545: "down", 546: "left", 547: "right"}   # BTN_DPAD_*
ABS_X, ABS_Y, ABS_Z, ABS_RX, ABS_RY, ABS_RZ = 0, 1, 2, 3, 4, 5

AXIS_DEFAULT, TRIGGER_DEFAULT = 0x580, 0x610   # rsinput's defaults (Reset)
TRIGGER_MEASURE = 0x755                          # GPcal's trigger max while measuring: above any rest reading
AXIS_MAX_PERCENT, AXIS_DEADZONE_PERCENT, DEADZONE_MIN_PERCENT, ANTIDEADZONE_PERCENT = 95, 150, 5, 80
HOLD_S = 0.6        # a position counts once it has held this long
STEADY = 30         # ... within this many raw units
PUSHED = 0.4        # of AXIS_DEFAULT: a stick or trigger this far from rest is pushed
AT_REST = 0.25      # ... and this close to centre is at rest

STICKS = {"left": ("axis_leftx", "axis_lefty", ABS_X, ABS_Y), "right": ("axis_rightx", "axis_righty", ABS_RX, ABS_RY)}
TRIGGERS = {"left": ("trigger_left", ABS_Z), "right": ("trigger_right", ABS_RZ)}
AXES = [n for x, y, _, _ in STICKS.values() for n in (x, y)]
AXIS_KEYS = ("min", "center", "max", "deadzone", "antideadzone")
TRIGGER_KEYS = ("max", "deadzone", "antideadzone")


def param_names():
    return [f"{a}_{k}" for a in AXES for k in AXIS_KEYS] + \
           [f"{t}_{k}" for t, _ in TRIGGERS.values() for k in TRIGGER_KEYS]


# --- the maths (host-tested) -------------------------------------------------------------------------------------------
def axis_params(rests, lo, hi):
    """One stick axis from raw readings: rests (at rest after each push), lo / hi (pushed fully each way).
    Returns rsinput's {min, center, max, deadzone, antideadzone}."""
    c = sum(rests) / len(rests)
    m = AXIS_MAX_PERCENT * min(hi - c, c - lo) / 100
    dz = max(AXIS_DEADZONE_PERCENT * max(abs(r - c) for r in rests) / 100, DEADZONE_MIN_PERCENT * m / 100)
    return {"min": -int(m), "center": -round(c), "max": int(m), "deadzone": int(dz),
            "antideadzone": int(ANTIDEADZONE_PERCENT * dz / 100)}


def trigger_params(rest, full):
    """One trigger from its readings with max = TRIGGER_MEASURE (the driver reports max - raw): at rest and pressed
    fully. max becomes the raw rest value, so the trigger reads 0 at rest and its travel above that."""
    r0, r1 = TRIGGER_MEASURE - rest, TRIGGER_MEASURE - full
    dz = DEADZONE_MIN_PERCENT * (r0 - r1) / 100
    return {"max": int(r0), "deadzone": int(dz), "antideadzone": int(ANTIDEADZONE_PERCENT * dz / 100)}


def defaults():
    p = {}
    for a in AXES:
        p.update({f"{a}_min": -AXIS_DEFAULT, f"{a}_center": 0, f"{a}_max": AXIS_DEFAULT, f"{a}_deadzone": 0,
                  f"{a}_antideadzone": 0})
    for t, _ in TRIGGERS.values():
        p.update({f"{t}_max": TRIGGER_DEFAULT, f"{t}_deadzone": 0, f"{t}_antideadzone": 0})
    return p


def saved_text(p):
    """GPcal's file format, which asgard-gpcal-apply.sh runs the rsinput lines of (CAL-2)."""
    lines = ["#!/usr/bin/env bash", "#", "# Stick calibration, made with Asgard's thor_stickcal.py (GPcal's format)", "#"]
    lines += [f"echo {p[n]} > /sys/module/rsinput/parameters/{n}" for n in param_names()]
    lines += ["echo 1 > /sys/module/rsinput/parameters/update_params"]
    return "\n".join(lines) + "\n"


class Hold:
    """A value that has to hold steady (within STEADY) for HOLD_S while a condition is true."""
    def __init__(self):
        self.ref, self.since = None, 0.0

    def progress(self, values, ok, now):
        if not ok or self.ref is None or any(abs(a - b) > STEADY for a, b in zip(values, self.ref)):
            self.ref, self.since = (tuple(values) if ok else None), now
            return 0.0
        return min(1.0, (now - self.since) / HOLD_S)


# --- the driver ----------------------------------------------------------------------------------------------------------
def read_params():
    p = {}
    for n in param_names():
        with open(f"{PARAMS}/{n}") as f:
            p[n] = int(f.read().strip())
    return p


def write_params(p):
    for n, v in p.items():
        with open(f"{PARAMS}/{n}", "w") as f:
            f.write(str(int(v)))
    with open(f"{PARAMS}/update_params", "w") as f:   # the driver re-reads its ranges
        f.write("1")


def save(p):
    os.makedirs(os.path.dirname(SAVED), exist_ok=True)
    tmp = SAVED + ".tmp"
    with open(tmp, "w") as f:
        f.write(saved_text(p))
    os.chmod(tmp, 0o755)
    os.replace(tmp, SAVED)


def open_raw_pad(wait_s=5.0):
    """rsinput's evdev node, opened non-blocking and grabbed. InputPlumber puts it back in /dev/input once it stops."""
    import fcntl
    end = time.monotonic() + wait_s
    while True:
        name = None
        for line in open("/proc/bus/input/devices"):
            if line.startswith("N: Name="):
                name = line[9:].strip().strip('"')
            elif line.startswith("H: Handlers=") and name == PAD_NAME:
                ev = next((h for h in line[12:].split() if h.startswith("event")), None)
                try:
                    fd = os.open(f"/dev/input/{ev}", os.O_RDONLY | os.O_NONBLOCK)
                    fcntl.ioctl(fd, 0x40044590, 1)   # EVIOCGRAB
                    return fd
                except (OSError, TypeError):
                    pass
        if time.monotonic() > end:
            return None
        time.sleep(0.2)


def abs_now(fd, code):
    import fcntl
    buf = bytearray(24)
    fcntl.ioctl(fd, 0x80184540 + code, buf)   # EVIOCGABS: value first
    return struct.unpack("6i", buf)[0]


# --- the UI ------------------------------------------------------------------------------------------------------------
class Home(Exception):
    pass


class App:
    def __init__(self, ui, fd):
        import sdlui
        self.sdlui, self.ui, self.fd = sdlui, ui, fd
        self.abs = {c: abs_now(fd, c) for c in (ABS_X, ABS_Y, ABS_Z, ABS_RX, ABS_RY, ABS_RZ)}
        ui.pad_fd, ui.ev_btn, ui.ev_dpad = fd, RAW_BTN, RAW_DPAD
        ui.on_abs = self.abs.__setitem__
        ui.on_home = self.home
        self.original = read_params()
        self.p = dict(self.original)

    def home(self):
        raise Home()

    def hints(self, *extra):
        h = self.sdlui.hint
        return [h(g, t) for g, t in extra]

    # one live screen: a title, two lines, and a drawing below them
    def frame(self, title, lines, body, hints):
        ui = self.ui
        x0, y0, pw, rh = ui.panel(title, 7)
        for i, s in enumerate(lines):
            ui.text(s.upper(), ui.w // 2, y0 + i * rh + rh // 2, "m_item", self.sdlui.M_HELP if i == 0 else self.sdlui.M_TEXT,
                    "center", maxw=pw - 40, vcenter=True)
        body(x0, y0 + 2 * rh, pw, 5 * rh)
        ui.help_bar(hints)
        ui.present()

    def gate(self, cx, cy, half, x, y, scale, marks=()):
        """A square stick gate with crosshair; the dot at (x, y) in units where `scale` is the edge."""
        ui, grey, dim, accent = self.ui, (96, 96, 96), (48, 48, 48), (120, 180, 255)
        ui.rect(cx - half, cy - half, 2 * half, 2 * half, (12, 12, 12))
        ui.rect(cx - half, cy, 2 * half, 2, dim)
        ui.rect(cx, cy - half, 2, 2 * half, dim)
        for mx, my in marks:
            px, py = cx + int(half * max(-1, min(1, mx / scale))), cy + int(half * max(-1, min(1, my / scale)))
            ui.rect(px - 4, py - 4, 8, 8, grey)
        px, py = cx + int(half * max(-1, min(1, x / scale))), cy + int(half * max(-1, min(1, y / scale)))
        r = max(6, int(14 * ui.s))
        ui.rect(px - r, py - r, 2 * r, 2 * r, accent)

    def bar(self, x, y, w, h, frac, color=(120, 180, 255)):
        self.ui.rect(x, y, w, h, (12, 12, 12))
        self.ui.rect(x, y, int(w * max(0.0, min(1.0, frac))), h, color)

    def loop(self, step):
        """Run step(now) every frame until it returns non-None; B returns 'b'."""
        while True:
            a = self.ui.poll()
            if a in ("b", "quit"):
                return "b"
            r = step(time.monotonic(), a)
            if r is not None:
                return r
            self.sdlui.sdl.SDL_Delay(16)

    # --- a stick ----------------------------------------------------------------------------------------------------
    def calibrate_stick(self, side):
        ax, ay, cx_code, cy_code = STICKS[side]
        before = {k: v for k, v in self.p.items() if k.startswith((ax, ay))}
        measure = {f"{a}_{k}": v for a in (ax, ay) for k, v in
                   (("min", -AXIS_DEFAULT), ("center", 0), ("max", AXIS_DEFAULT), ("deadzone", 0), ("antideadzone", 0))}
        while True:
            write_params({**self.p, **measure})
            got = self.measure_stick(side, cx_code, cy_code)
            if got is None:
                write_params(self.p)
                return
            rests, ext = got
            new = {}
            for a, i, lo, hi in ((ax, 0, ext["left"], ext["right"]), (ay, 1, ext["up"], ext["down"])):
                new.update({f"{a}_{k}": v for k, v in axis_params([r[i] for r in rests], lo, hi).items()})
            write_params({**self.p, **new})
            choice = self.test_stick(side, cx_code, cy_code, {**self.p, **new})
            if choice == "a":
                self.p.update(new)
                return
            if choice != "y":
                write_params(self.p)
                self.p.update(before)
                return

    def measure_stick(self, side, cx_code, cy_code):
        steps = ["rest", "right", "rest", "left", "rest", "down", "rest", "up", "rest"]
        rests, ext, hold = [], {}, Hold()
        title = f"{side} stick"
        k = [0]

        def step(now, _a):
            what = steps[k[0]]
            x, y = self.abs[cx_code], self.abs[cy_code]
            if what == "rest":
                ok = abs(x) < AT_REST * AXIS_DEFAULT and abs(y) < AT_REST * AXIS_DEFAULT
                lines = ["Let go of the stick", "Leave it centred until the bar fills"]
            else:
                v = {"right": x, "left": -x, "down": y, "up": -y}[what]
                ok = v > PUSHED * AXIS_DEFAULT
                lines = [f"Push the stick all the way {what}", "Hold it there until the bar fills, then let go"]
            prog = hold.progress((x, y), ok, now)
            if prog >= 1.0:
                if what == "rest":
                    rests.append((x, y))
                else:
                    ext[what] = x if what in ("left", "right") else y
                k[0] += 1
                hold.__init__()
                if k[0] == len(steps):
                    return (rests, ext)
            marks = [(r[0], r[1]) for r in rests] + [(ext[d], 0) if d in ("left", "right") else (0, ext[d]) for d in ext]

            def body(x0, yb, pw, h):
                half = int(h * 0.36)
                self.gate(self.ui.w // 2, yb + half + int(10 * self.ui.s), half, x, y, AXIS_DEFAULT, marks)
                bw = int(pw * 0.5)
                self.bar(self.ui.w // 2 - bw // 2, yb + 2 * half + int(40 * self.ui.s), bw, int(12 * self.ui.s), prog)
                self.ui.text(f"STEP {k[0] + 1} OF {len(steps)}", self.ui.w // 2, yb + 2 * half + int(80 * self.ui.s),
                             "m_small", self.sdlui.M_TEXT, "center")
            self.frame(title, lines, body, self.hints(("b", "Cancel"), (None, "Home  Exit")))
            return None
        r = self.loop(step)
        return None if r == "b" else r

    def test_stick(self, side, cx_code, cy_code, p):
        ax, ay, _, _ = STICKS[side]
        rx, ry = p[f"{ax}_max"] - p[f"{ax}_antideadzone"], p[f"{ay}_max"] - p[f"{ay}_antideadzone"]

        def step(_now, a):
            if a in ("a", "y"):
                return a
            x, y = self.abs[cx_code], self.abs[cy_code]

            def body(x0, yb, pw, h):
                half = int(h * 0.36)
                cx, cy = self.ui.w // 2, yb + half + int(10 * self.ui.s)
                self.gate(cx, cy, half, x / max(1, rx), y / max(1, ry), 1.0)
                self.ui.text(f"X {100 * x / max(1, rx):+.0f} %    Y {100 * y / max(1, ry):+.0f} %", cx,
                             cy + half + int(40 * self.ui.s), "m_small", self.sdlui.M_TEXT, "center")
            self.frame(f"{side} stick", ["Move the stick around: the dot should reach every edge",
                                         "and sit in the middle when you let go"],
                       body, self.hints(("a", "Keep"), ("y", "Redo"), ("b", "Undo")))
            return None
        return self.loop(step)

    # --- a trigger --------------------------------------------------------------------------------------------------
    def calibrate_trigger(self, side):
        name, code = TRIGGERS[side]
        before = {k: v for k, v in self.p.items() if k.startswith(name)}
        while True:
            write_params({**self.p, f"{name}_max": TRIGGER_MEASURE, f"{name}_deadzone": 0, f"{name}_antideadzone": 0})
            steps, got, hold, k = ["rest", "press", "rest"], {}, Hold(), [0]

            def step(now, _a):
                v = self.abs[code]
                what = steps[k[0]]
                rest_v = got.get("rest", v)
                ok = (v - rest_v > PUSHED * AXIS_DEFAULT) if what == "press" else ("rest" not in got or v - rest_v < STEADY * 2)
                prog = hold.progress((v,), ok, now)
                if prog >= 1.0:
                    if what == "press":
                        got["full"] = v
                    elif "rest" not in got:
                        got["rest"] = v
                    k[0] += 1
                    hold.__init__()
                    if k[0] == len(steps):
                        return got
                lines = (["Press the trigger all the way and hold it", "until the bar fills, then let go"]
                         if what == "press" else ["Let go of the trigger", "Leave it until the bar fills"])

                def body(x0, yb, pw, h):
                    bw = int(pw * 0.7)
                    self.bar(self.ui.w // 2 - bw // 2, yb + int(h * 0.25), bw, int(40 * self.ui.s), v / TRIGGER_MEASURE,
                             (96, 96, 96))
                    self.bar(self.ui.w // 2 - bw // 4, yb + int(h * 0.55), bw // 2, int(12 * self.ui.s), prog)
                self.frame(f"{side} trigger", lines, body, self.hints(("b", "Cancel"), (None, "Home  Exit")))
                return None
            r = self.loop(step)
            if r == "b":
                write_params(self.p)
                return
            new = {f"{name}_{k}": v for k, v in trigger_params(r["rest"], r["full"]).items()}
            write_params({**self.p, **new})
            top = new[f"{name}_max"] - new[f"{name}_antideadzone"]

            def test(_now, a):
                if a in ("a", "y"):
                    return a
                v = self.abs[code]

                def body(x0, yb, pw, h):
                    bw = int(pw * 0.7)
                    self.bar(self.ui.w // 2 - bw // 2, yb + int(h * 0.3), bw, int(40 * self.ui.s), v / max(1, top))
                    self.ui.text(f"{100 * v / max(1, top):.0f} %", self.ui.w // 2, yb + int(h * 0.55), "m_small",
                                 self.sdlui.M_TEXT, "center")
                self.frame(f"{side} trigger", ["Press the trigger: the bar should be empty at rest", "and full when pressed"],
                           body, self.hints(("a", "Keep"), ("y", "Redo"), ("b", "Undo")))
                return None
            choice = self.loop(test)
            if choice == "a":
                self.p.update(new)
                return
            if choice != "y":
                self.p.update(before)
                write_params(self.p)
                return

    # --- everything live ----------------------------------------------------------------------------------------------
    def test_all(self):
        p = self.p

        def rng(a):
            return max(1, p[f"{a}_max"] - p[f"{a}_antideadzone"])

        def step(_now, _a):
            def body(x0, yb, pw, h):
                half = int(h * 0.3)
                for i, (side, (ax, ay, cx_code, cy_code)) in enumerate(STICKS.items()):
                    cx = x0 + pw * (1 + 2 * i) // 4
                    self.gate(cx, yb + half + int(60 * self.ui.s), half, self.abs[cx_code] / rng(ax), self.abs[cy_code] / rng(ay), 1.0)
                    t, code = TRIGGERS[side]
                    self.bar(cx - half, yb, 2 * half, int(20 * self.ui.s), self.abs[code] / rng(t))
            self.frame("Test", ["Sticks and triggers as games see them", ""], body, self.hints(("b", "Back")))
            return None
        self.loop(step)

    def menu(self):
        ui, sel = self.ui, 0
        items = [("Left stick", ""), ("Right stick", ""), ("Left trigger", ""), ("Right trigger", ""), ("Test", ""),
                 ("Reset to defaults", ""), ("Save", "")]
        while True:
            sel = ui.menu("Stick calibration", items, sel,
                          hints=self.hints(("a", "Select"), ("b", "Back"), (None, "Home  Exit")))
            if sel is None:
                if self.p == self.original:
                    return
                if ui.confirm("Leave without saving", "the calibration goes back to how it was"):
                    write_params(self.original)
                    return
                sel = 0
            elif sel < 2:
                self.calibrate_stick(("left", "right")[sel])
            elif sel < 4:
                self.calibrate_trigger(("left", "right")[sel - 2])
            elif sel == 4:
                self.test_all()
            elif sel == 5:
                if ui.confirm("Reset to defaults", "the driver's own range, no deadzone"):
                    self.p = defaults()
                    write_params(self.p)
            else:
                write_params(self.p)
                save(self.p)
                ui.message("Stick calibration", ["Saved: it applies from now on and at every boot."])
                return


def main():
    import sdlui
    fd = open_raw_pad()
    ui = sdlui.UI("Stick Calibration", display=0)
    if fd is None:
        ui.message("Stick calibration", ["The controller isn't there: try again in a moment."])
        return
    app = App(ui, fd)
    try:
        app.menu()
    except Home:
        write_params(app.original)   # Home leaves at once, nothing changed


if __name__ == "__main__":
    main()
