#!/usr/bin/env python3
# spec: CAL-4 CAL-2
# requires: lib:libSDL2-2.0.so.0 lib:libSDL2_ttf-2.0.so.0 lib:libSDL2_image-2.0.so.0
"""python3 test_thor_stickcal.py: stick calibration's maths against rsinput's own formulas, its saved file through
asgard-gpcal-apply.sh, and the raw pad's buttons (A, B, d-pad, Home) through sdlui."""
import os
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import thor_stickcal as sc  # noqa: E402


def stick(raw, p):   # rsinput.c's stick report
    x = raw + p["center"]
    return 0 if abs(x) < p["deadzone"] else (1 if x > 0 else -1) * (abs(x) - p["antideadzone"])


def trigger(raw, p):   # rsinput.c's rsinput_trigger
    v = p["max"] - raw
    return 0 if v < p["deadzone"] else max(0, min(v - p["antideadzone"], p["max"] - p["antideadzone"]))


# A stick resting off centre at 100 (+-12), travelling 1000 each way: rest reads 0, both ends reach the range's edge.
p = sc.axis_params([100, 112, 88, 104, 96], lo=-900, hi=1100)
assert p["center"] == -100 and p["max"] == 950 and p["min"] == -950, p
top = p["max"] - p["antideadzone"]
for r in (88, 100, 112):
    assert stick(r, p) == 0, (r, stick(r, p))
assert stick(1100, p) >= top and stick(-900, p) <= -top, (stick(1100, p), stick(-900, p), top)
# A perfectly still stick still gets the minimum deadzone.
assert sc.axis_params([0, 0], -1000, 1000)["deadzone"] == int(0.05 * 950)

# A trigger measured with max = TRIGGER_MEASURE: raw 1544 at rest, 0 pressed. Rest reads 0, pressed reads full.
rest, full = sc.TRIGGER_MEASURE - 1544, sc.TRIGGER_MEASURE - 0
t = sc.trigger_params(rest, full)
assert t["max"] == 1544, t
assert trigger(1544, t) == 0 and trigger(1530, t) == 0, (trigger(1544, t), trigger(1530, t))
assert trigger(0, t) == t["max"] - t["antideadzone"], (trigger(0, t), t)

# The saved file is GPcal's format: asgard-gpcal-apply.sh applies every parameter of it (CAL-2).
with tempfile.TemporaryDirectory() as d:
    params, saved = f"{d}/params", f"{d}/asgard/gpcal.sh"
    os.makedirs(params)
    for n in sc.param_names() + ["update_params"]:
        open(f"{params}/{n}", "w").close()
    cal = sc.defaults()
    cal.update({"axis_leftx_center": 109, "axis_lefty_center": -72, "trigger_right_max": 1500})
    sc.SAVED = saved
    sc.save(cal)
    subprocess.run(["sh", f"{HERE}/asgard-gpcal-apply.sh"], check=True, capture_output=True,
                   env=dict(os.environ, ASGARD_CONFIG="true", GPCAL_AUTOSTART=f"{d}/none", GPCAL_SAVED=saved,
                            RSINPUT_PARAMS=params))
    sc.PARAMS = params
    assert sc.read_params() == cal, sc.read_params()
    assert open(f"{params}/update_params").read().strip() == "1"

# The raw pad drives sdlui: A (BTN_EAST) selects, B (BTN_SOUTH) goes back, BTN_DPAD_* move, axes reach on_abs,
# and Home (BTN_MODE) calls on_home from inside any wait (a menu, a message).
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import sdlui  # noqa: E402

ui = object.__new__(sdlui.UI)
r, w = os.pipe()
os.set_blocking(r, False)
ui.pad_fd, ui.held, ui.ev_btn, ui.ev_dpad = r, None, sc.RAW_BTN, sc.RAW_DPAD
axes, homes = {}, []
ui.on_abs, ui.on_home = axes.__setitem__, lambda: homes.append(1)


def send(etype, code, value):
    os.write(w, struct.pack("llHHi", 0, 0, etype, code, value))


for code, want in ((305, "a"), (304, "b"), (308, "x"), (307, "y"), (544, "up"), (547, "right")):
    send(1, code, 1)
    assert ui._poll_pad() == want, (code, want)
send(3, sc.ABS_RX, -700)
send(1, 316, 1)
assert ui._poll_pad() is None and axes == {sc.ABS_RX: -700} and homes == [1], (axes, homes)
print("ok")
