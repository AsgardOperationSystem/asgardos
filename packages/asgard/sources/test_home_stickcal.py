#!/usr/bin/env python3
# spec: CAL-4
# requires: file:build/AsgardOS-SM8550.aarch64/toolchain/usr/local/qt6/lib/libQt6Quick.so cmd:cmake
"""python -I test_home_stickcal.py: stick calibration inside Asgard Home's Settings, on the host against a fake rsinput.
Opening a control stops InputPlumber, resets that control so the driver reports raw values, and shows the first step;
Home (guide) or B puts back what was there and restarts InputPlumber; Reset saves the defaults. Reading the raw pad and
a whole measurement need the Thor (human check); the maths is test_stickcal.py."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "../../../tools/test"))
from home_harness import Root  # noqa: E402

PARAMS = "sys/module/rsinput/parameters"
HARDWARE, CALIBRATION = 4, 6
LEFT_STICK, RIGHT_TRIGGER, RESET = 3, 6, 8
ORIGINAL = {f"axis_{a}_{k}": v for a in ("leftx", "lefty", "rightx", "righty")
            for k, v in (("min", -1002), ("center", 109), ("max", 1002), ("deadzone", 50), ("antideadzone", 40))}
ORIGINAL.update({f"trigger_{s}_{k}": v for s in ("left", "right") for k, v in (("max", 1552), ("deadzone", 0),
                                                                               ("antideadzone", 0))})


def keys(row, *then):
    return " ".join(["start", *["down"] * HARDWARE, "a", *["down"] * CALIBRATION, "a", *["down"] * row, "a", *then])


def rsinput(root):
    return {n: int(root.read(f"{PARAMS}/{n}")) for n in ORIGINAL}


def fresh(root):
    for n, v in ORIGINAL.items():
        root.write(f"{PARAMS}/{n}", str(v))
    root.write(f"{PARAMS}/update_params", "0")


with Root() as root:
    # Left stick: InputPlumber stops, the stick is reset to raw, the first step shows; the triggers are left alone.
    fresh(root)
    r = root.run(keys(LEFT_STICK), ms=300)
    assert "shell: systemctl stop inputplumber" in r.log, r.log
    assert r.shows("Left stick") and r.shows("Let go of the stick"), r.texts
    p = rsinput(root)
    assert p["axis_leftx_center"] == 0 and p["axis_leftx_max"] == 0x580 and p["axis_lefty_deadzone"] == 0, p
    assert p["axis_rightx_center"] == 109 and p["trigger_left_max"] == 1552, p
    assert root.read(f"{PARAMS}/update_params") == "1" and root.exists("run/asgard-stickcal")

    # Home leaves at once: the calibration that was there, InputPlumber restarted, nothing saved, back on the page.
    for out in ("guide", "b"):
        fresh(root)
        r = root.run(keys(LEFT_STICK, out), ms=300)
        assert rsinput(root) == ORIGINAL, (out, rsinput(root))
        assert "shell: systemctl restart inputplumber" in r.log and not root.exists("run/asgard-stickcal"), (out, r.log)
        assert not root.exists("storage/.config/asgard/gpcal.sh"), out
        assert not r.shows("Let go of the stick") and r.shows("Right trigger"), (out, r.texts)

    # A trigger measures with its max raised to TRIGGER_MEASURE; the sticks stay as they were.
    fresh(root)
    r = root.run(keys(RIGHT_TRIGGER), ms=300)
    p = rsinput(root)
    assert r.shows("Right trigger") and r.shows("Let go of the trigger"), r.texts
    assert p["trigger_right_max"] == 0x755 and p["trigger_left_max"] == 1552 and p["axis_leftx_center"] == 109, p

    # Reset: rsinput's defaults, live and saved.
    fresh(root)
    root.run(keys(RESET, "a"), ms=300)
    p = rsinput(root)
    assert p["axis_leftx_center"] == 0 and p["axis_leftx_max"] == 0x580 and p["trigger_left_max"] == 0x610, p
    saved = root.read("storage/.config/asgard/gpcal.sh")
    assert "echo 1408 > /sys/module/rsinput/parameters/axis_leftx_max" in saved, saved

    # Stopped mid-calibration (a crash): the next start brings InputPlumber back.
    root.write("run/asgard-stickcal")
    r = root.run("", ms=200)
    assert "shell: systemctl restart inputplumber" in r.log and not root.exists("run/asgard-stickcal"), r.log
print("ok")
