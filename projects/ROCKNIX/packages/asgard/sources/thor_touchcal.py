#!/usr/bin/env python3
"""Touch screen calibration (Settings > Hardware > Calibration), one panel per run.

Tap 5 targets; an affine fit of the taps (as delivered through the current libinput calibration_matrix) to the
targets is composed into that matrix and applied live with swaymsg. A test screen then draws a dot per touch:
A keeps it (asgard.touch.<screen> in system.cfg, re-applied at boot by thor-sway-rotate.sh), Y redoes it, B puts
the old matrix back. The controller drives every step, so a bad calibration can't lock touch input out.
Usage: thor_touchcal.py top|bottom|reset
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

DEFAULT = [0.0, -1.0, 1.0, 1.0, 0.0, 0.0]  # thor-sway-rotate.sh's rotation for both panels (DSI-1/2 transform 90)
SCREENS = {"top": ("0:0:top_touchscreen", 0, "Touch Calibration"),
           "bottom": ("0:0:bottom_touchscreen", 1, "Touch Calibration (Bottom)")}  # "Bottom": ROCKNIX's DSI-1 rules
TARGETS = [(0.1, 0.1), (0.9, 0.1), (0.9, 0.9), (0.1, 0.9), (0.5, 0.5)]
MAX_RMS = 0.04  # of the screen size; taps further off than this from any affine fit were mis-taps


def solve3(m, v):
    """Solve the 3x3 system m x = v (Gaussian elimination, partial pivoting)."""
    a = [row[:] + [v[i]] for i, row in enumerate(m)]
    for c in range(3):
        p = max(range(c, 3), key=lambda r: abs(a[r][c]))
        if abs(a[p][c]) < 1e-12:
            raise ValueError("singular")
        a[c], a[p] = a[p], a[c]
        for r in range(3):
            if r != c:
                f = a[r][c] / a[c][c]
                a[r] = [x - f * y for x, y in zip(a[r], a[c])]
    return [a[i][3] / a[i][i] for i in range(3)]


def fit_affine(taps, targets):
    """Least-squares [a b c d e f] with target ~ (a x + b y + c, d x + e y + f) for each tap (x, y); and the RMS error."""
    rows = [(x, y, 1.0) for x, y in taps]
    ata = [[sum(r[i] * r[j] for r in rows) for j in range(3)] for i in range(3)]
    out = []
    for k in range(2):
        out += solve3(ata, [sum(r[i] * t[k] for r, t in zip(rows, targets)) for i in range(3)])
    err = [(out[0] * x + out[1] * y + out[2] - tx) ** 2 + (out[3] * x + out[4] * y + out[5] - ty) ** 2
           for (x, y), (tx, ty) in zip(taps, targets)]
    return out, (sum(err) / len(err)) ** 0.5


def compose(a, m):
    """libinput matrices as [a b c d e f]: a after m."""
    return [a[0] * m[0] + a[1] * m[3], a[0] * m[1] + a[1] * m[4], a[0] * m[2] + a[1] * m[5] + a[2],
            a[3] * m[0] + a[4] * m[3], a[3] * m[1] + a[4] * m[4], a[3] * m[2] + a[4] * m[5] + a[5]]


def fmt(m):
    return " ".join(f"{v:.6f}" for v in m)


def sway(*args):
    from sdlui import run_cmd
    return run_cmd("swaymsg " + " ".join(f"'{a}'" for a in args))[1]


def current(ident):
    for i in json.loads(sway("-t", "get_inputs", "-r") or "[]"):
        if i.get("identifier") == ident:
            return i.get("libinput", {}).get("calibration_matrix") or DEFAULT
    return DEFAULT


def apply(ident, m):
    sway("input", ident, "calibration_matrix", *fmt(m).split())


def save(screen, m):
    from sdlui import run_cmd
    run_cmd(f". /etc/profile; set_setting asgard.touch.{screen} '{fmt(m) if m else ''}'")


def calibrate(screen):
    import sdlui
    ident, display, title = SCREENS[screen]
    ui = sdlui.UI(title, display=display, grab_pad=True)  # the pad drives only this window
    old = current(ident)
    bg, fg, dim, accent = (10, 10, 14), (235, 238, 245), (150, 156, 170), (120, 180, 255)

    def screen_text(lines, y0):
        for i, s in enumerate(lines):
            ui.text(s, ui.w // 2, y0 + i * int(48 * ui.s), font="small", color=fg if i == 0 else dim, align="center")

    def collect():
        taps, last = [], 0.0
        while len(taps) < len(TARGETS):
            tx, ty = TARGETS[len(taps)]
            x, y, r = int(tx * ui.w), int(ty * ui.h), int(40 * ui.s)

            def draw():
                ui.rect(0, 0, ui.w, ui.h, bg)
                ui.rect(x - r, y - 2, 2 * r, 4, accent)
                ui.rect(x - 2, y - r, 4, 2 * r, accent)
                ui.rect(x - 6, y - 6, 12, 12, fg)
                screen_text([f"Tap the centre of the cross  ({len(taps) + 1} of {len(TARGETS)})",
                             "Use a fingertip, and hold still for a moment.  B cancels."], ui.h // 2 + int(90 * ui.s))
            ui.show(draw)
            while True:
                a = ui.poll()
                if a in ("b", "quit"):
                    return None
                if a == "touch" and time.monotonic() - last > 0.35:  # one tap = one target
                    last = time.monotonic()
                    taps.append((ui.touch[0] / ui.w, ui.touch[1] / ui.h))
                    break
                sdlui.sdl.SDL_Delay(10)
        return taps

    while True:
        apply(ident, old)
        taps = collect()
        if taps is None:
            apply(ident, old)
            return
        try:
            fix, rms = fit_affine(taps, TARGETS)
        except ValueError:
            fix, rms = None, 1.0
        if rms > MAX_RMS:
            ui.message("Touch calibration", ["Those taps didn't line up. Let's try again."])
            continue
        new = compose(fix, old)
        apply(ident, new)
        dots = []
        while True:
            def draw():
                ui.rect(0, 0, ui.w, ui.h, bg)
                for dx, dy in dots[-30:]:
                    ui.rect(dx - 8, dy - 8, 16, 16, accent)
                screen_text(["Touch around the screen: dots should appear under your finger.",
                             "A  keep        Y  redo        B  cancel"], int(ui.h * 0.4))
            ui.show(draw)
            a = ui.wait()
            if a == "touch":
                dots.append(ui.touch)
            elif a == "a":
                save(screen, new)
                return
            elif a == "y":
                break
            elif a in ("b", "quit"):
                apply(ident, old)
                return


def main():
    what = sys.argv[1] if len(sys.argv) > 1 else ""
    if what == "reset":
        for screen, (ident, _, _) in SCREENS.items():
            apply(ident, DEFAULT)
            save(screen, None)
    elif what in SCREENS:
        calibrate(what)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
