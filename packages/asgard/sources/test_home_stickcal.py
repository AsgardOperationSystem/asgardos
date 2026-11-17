#!/usr/bin/env python3
# spec: CAL-4
# requires: file:build/AsgardOS-SM8550.aarch64/toolchain/usr/local/qt6/lib/libQt6Quick.so cmd:cmake
"""python -I test_home_stickcal.py: stick calibration inside Asgard Home's Settings, on the host against a fake rsinput.
Opening a control stops InputPlumber, resets that control so the driver reports raw values, and shows the first step;
Home (guide) or B puts back what was there and restarts InputPlumber; Reset saves the defaults. After it closes, the
raw pad drives Settings until InputPlumber's virtual pad is back, then the virtual pad takes over (fake evdev nodes,
ASGARD_INPUT). A whole measurement needs the Thor (human check); the maths is test_stickcal.py."""
import errno
import os
import struct
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "../../../tools/test"))
from home_harness import Root  # noqa: E402

PARAMS = "sys/module/rsinput/parameters"
HARDWARE, CALIBRATION = 4, 6
LEFT_STICK, LEFT_TRIGGER, RIGHT_TRIGGER, RESET = 3, 5, 6, 8
RAW_PAD = 'N: Name="AYN Odin2 Gamepad"\nH: Handlers=event5 js0\n\n'
VIRTUAL_PAD = 'N: Name="Sony Interactive Entertainment DualSense Wireless Controller"\nH: Handlers=event6 js1\n\n'
BTN_EAST = 0x131   # A, on both pads
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


def writer(path, stop, then=None):
    """Opens a fake event node for writing once Home opens it (a FIFO's writer waits for its reader), then runs
    then(fd); keeps it open until stop, so Home never sees the pad go."""
    def run():
        while not stop.is_set():
            try:
                fd = os.open(path, os.O_WRONLY | os.O_NONBLOCK)
                break
            except OSError as e:
                assert e.errno == errno.ENXIO, e
                time.sleep(0.02)
        else:
            return
        try:
            if then:
                then(fd)
            stop.wait()
        finally:
            os.close(fd)
    t = threading.Thread(target=run, daemon=True)
    t.start()
    return t


def press_a(fd):
    time.sleep(0.4)   # B (the last key) has closed the calibration
    try:
        os.write(fd, b"".join(struct.pack("qqHHi", 0, 0, t, c, v) for t, c, v in ((1, BTN_EAST, 1), (0, 0, 0),
                                                                                  (1, BTN_EAST, 0), (0, 0, 0))))
    except BrokenPipeError:   # Home let go of the raw pad: the A goes nowhere
        pass


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

    # Closed: InputPlumber's virtual pad takes seconds to come back, so the raw pad keeps driving Settings until then. A
    # pressed on it after B opens the left trigger again.
    fresh(root)
    inp = f"{root.path}/input"
    os.makedirs(inp)
    os.mkfifo(f"{inp}/event5")
    os.mkfifo(f"{inp}/event6")
    root.write("input/devices", RAW_PAD)
    stop = threading.Event()
    t = writer(f"{inp}/event5", stop, press_a)
    r = root.run(keys(LEFT_TRIGGER, "b"), env={"ASGARD_INPUT": inp}, ms=1200)
    stop.set(); t.join()
    assert f"gamepad: opened {inp}/event5" in r.log, r.log
    assert r.shows("Left trigger") and r.shows("Cancel"), r.texts   # measuring (its steps run on: the fake axes rest)

    # Then the virtual pad shows up and Home switches to it.
    fresh(root)
    stop = threading.Event()

    def virtual_appears(_fd):
        time.sleep(0.4)
        root.write("input/devices", RAW_PAD + VIRTUAL_PAD)
    threads = [writer(f"{inp}/event5", stop, virtual_appears), writer(f"{inp}/event6", stop)]
    root.write("input/devices", RAW_PAD)
    r = root.run(keys(LEFT_TRIGGER, "b"), env={"ASGARD_INPUT": inp}, ms=1200)
    stop.set()
    for t in threads:
        t.join()
    assert f"gamepad: opened {inp}/event6" in r.log, r.log
    assert not r.shows("Cancel"), r.texts

    # Stopped mid-calibration (a crash): the next start brings InputPlumber back.
    root.write("run/asgard-stickcal")
    r = root.run("", ms=200)
    assert "shell: systemctl restart inputplumber" in r.log and not root.exists("run/asgard-stickcal"), r.log
print("ok")
