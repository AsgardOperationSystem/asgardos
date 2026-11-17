#!/usr/bin/env python3
# spec: CAL-4 CAL-2
# requires: cmd:node
"""python3 test_stickcal.py: stick calibration's maths (Asgard Home's qml/stickcal.js) against rsinput.c's own formulas,
a measurement driven step by step, and its saved file through asgard-gpcal-apply.sh (CAL-2)."""
import json
import os
import subprocess
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
JS = os.path.join(HERE, "../../asgard-home/src/qml/stickcal.js")
CASES = r"""
const out = {}
// A stick resting off centre at 100 (+-12), travelling 1000 each way.
out.axis = SC.axisParams([100, 112, 88, 104, 96], -900, 1100)
out.still = SC.axisParams([0, 0], -1000, 1000)
// A trigger with max = TRIGGER_MEASURE: raw 1544 at rest, 0 pressed.
out.trigger = SC.triggerParams(SC.TRIGGER_MEASURE - 1544, SC.TRIGGER_MEASURE)
// A left stick measured step by step from raw readings ([x, y, z, rx, ry, rz]), each held for HOLD_MS.
const at = { rest: [100, -40], right: [1100, -30], left: [-900, -50], down: [90, 1000], up: [110, -1080] }
let got = {}, state = { ref: null, since: 0 }, now = 0, steps = 0
for (const step of SC.STICK_STEPS) {
    const axes = [at[step][0], at[step][1], 0, 0, 0, 0]
    if (!SC.inPlace("stick", "left", step, axes, got)) throw new Error("not in place: " + step)
    for (let t = 0; t <= SC.HOLD_MS + 40; t += 33) {
        const vals = SC.watched("stick", "left", axes)
        const h = SC.hold(state, vals, true, now += 33)
        state = h.state
        if (h.progress >= 1) { got = SC.record("stick", step, vals, got); state = { ref: null, since: 0 }; steps++; break }
    }
}
out.steps = steps
out.stick = SC.result("stick", "left", got)
// Moving more than STEADY starts the hold again; leaving the place resets it.
let s = SC.hold({ ref: null, since: 0 }, [0, 0], true, 0).state
out.jitter = SC.hold(s, [20, -20], true, SC.HOLD_MS).progress
out.moved = SC.hold(s, [200, 0], true, SC.HOLD_MS).progress
out.notThere = SC.inPlace("stick", "left", "right", [300, 0, 0, 0, 0, 0], {})
out.saved = SC.savedText(Object.assign(SC.defaults(), { axis_leftx_center: 109, trigger_right_max: 1500 }))
out.names = SC.paramNames()
console.log(JSON.stringify(out))
"""


def run_js():
    src = open(JS).read().replace(".pragma library", "")
    code = "const SC = (function () {\n" + src + "\nreturn { " + ", ".join(
        n for n in ("AXIS_DEFAULT", "TRIGGER_MEASURE", "HOLD_MS", "STICK_STEPS", "axisParams", "triggerParams", "inPlace",
                    "watched", "record", "hold", "result", "savedText", "defaults", "paramNames")) + " } })()\n" + CASES
    return json.loads(subprocess.run(["node", "-e", code], check=True, capture_output=True, text=True).stdout)


def stick(raw, p):   # rsinput.c's stick report
    x = raw + p["center"]
    return 0 if abs(x) < p["deadzone"] else (1 if x > 0 else -1) * (abs(x) - p["antideadzone"])


def trigger(raw, p):   # rsinput.c's rsinput_trigger
    v = p["max"] - raw
    return 0 if v < p["deadzone"] else max(0, min(v - p["antideadzone"], p["max"] - p["antideadzone"]))


r = run_js()
p = r["axis"]
assert p["center"] == -100 and p["max"] == 950 and p["min"] == -950, p
top = p["max"] - p["antideadzone"]
assert all(stick(v, p) == 0 for v in (88, 100, 112)), p
assert stick(1100, p) >= top and stick(-900, p) <= -top, (stick(1100, p), stick(-900, p), top)
assert r["still"]["deadzone"] == int(0.05 * 950), r["still"]

t = r["trigger"]
assert t["max"] == 1544, t
assert trigger(1544, t) == 0 and trigger(1530, t) == 0 and trigger(0, t) == t["max"] - t["antideadzone"], t

# The step-by-step measurement: nine steps, and a stick whose rest (100, -40) reads 0 and whose ends reach the edge.
assert r["steps"] == 9, r["steps"]
s = r["stick"]
x = {k[len("axis_leftx_"):]: v for k, v in s.items() if k.startswith("axis_leftx_")}
y = {k[len("axis_lefty_"):]: v for k, v in s.items() if k.startswith("axis_lefty_")}
assert stick(100, x) == 0 and stick(-40, y) == 0, (x, y)
assert stick(1100, x) >= x["max"] - x["antideadzone"] and stick(-900, x) <= -(x["max"] - x["antideadzone"]), x
assert stick(1000, y) >= y["max"] - y["antideadzone"] and stick(-1080, y) <= -(y["max"] - y["antideadzone"]), y
assert 0 < r["jitter"] and r["moved"] == 0 and r["notThere"] is False, r

# Saved in GPcal's format: asgard-gpcal-apply.sh applies every parameter of it (CAL-2).
with tempfile.TemporaryDirectory() as d:
    params, saved = f"{d}/params", f"{d}/asgard/gpcal.sh"
    os.makedirs(params)
    os.makedirs(os.path.dirname(saved))
    for n in r["names"] + ["update_params"]:
        open(f"{params}/{n}", "w").close()
    open(saved, "w").write(r["saved"])
    subprocess.run(["sh", f"{HERE}/asgard-gpcal-apply.sh"], check=True, capture_output=True,
                   env=dict(os.environ, ASGARD_CONFIG="true", GPCAL_AUTOSTART=f"{d}/none", GPCAL_SAVED=saved,
                            RSINPUT_PARAMS=params))
    got = {n: open(f"{params}/{n}").read().strip() for n in r["names"]}
    assert got["axis_leftx_center"] == "109" and got["trigger_right_max"] == "1500", got
    assert got["axis_righty_min"] == str(-0x580) and len(got) == 26, got
    assert open(f"{params}/update_params").read().strip() == "1"
print("ok")
