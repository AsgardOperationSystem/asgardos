#!/usr/bin/env python3
# spec: HOME-1
# requires: file:build/AsgardOS-SM8550.aarch64/toolchain/usr/local/qt6/lib/libQt6Quick.so cmd:cmake
"""python -I test_home_pad.py: Asgard Home's pad beyond the d-pad and face buttons (HOME-1), offscreen on a fake root.
Fake evdev nodes (ASGARD_INPUT) stand in for InputPlumber's virtual pad and keyboard: the left stick moves like the
d-pad, the back button (the keyboard's F1) is B. Home (guide) goes back to the start from anywhere. How far the real
stick has to go is a human check."""
import errno
import os
import struct
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "../../../tools/test"))
from home_harness import Root  # noqa: E402

DEVICES = ('N: Name="Sony Interactive Entertainment DualSense Wireless Controller"\nH: Handlers=event6 js1\n\n'
           'N: Name="InputPlumber Keyboard"\nH: Handlers=sysrq kbd event7\n\n')
EV_SYN, EV_KEY, EV_ABS = 0, 1, 3
ABS_X, ABS_Y, KEY_F1 = 0, 1, 59


def events(*evs):
    return b"".join(struct.pack("qqHHi", 0, 0, t, c, v) + struct.pack("qqHHi", 0, 0, EV_SYN, 0, 0) for t, c, v in evs)


def writer(path, stop, steps):
    """Once Home opens the fake node (a FIFO's writer waits for its reader), writes each (delay, bytes) step; keeps it
    open until stop, so Home never sees the device go."""
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
            for delay, data in steps:
                time.sleep(delay)
                os.write(fd, data)
            stop.wait()
        finally:
            os.close(fd)
    t = threading.Thread(target=run, daemon=True)
    t.start()
    return t


def run(root, keys, pad=(), kbd=(), ms=1500):
    inp = f"{root.path}/input"
    os.makedirs(inp, exist_ok=True)
    for node in ("event6", "event7"):
        if not os.path.exists(f"{inp}/{node}"):
            os.mkfifo(f"{inp}/{node}")
    root.write("input/devices", DEVICES)
    stop = threading.Event()
    threads = [writer(f"{inp}/event6", stop, pad), writer(f"{inp}/event7", stop, kbd)]
    r = root.run(keys, env={"ASGARD_INPUT": inp}, ms=ms)
    stop.set()
    for t in threads:
        t.join()
    return r


with Root() as root:
    root.library({"gba": ["A.gba", "B.gba", "C.gba", "D.gba", "E.gba", "F.gba", "G.gba", "H.gba"], "nds": ["Mario.nds"]})
    # In GBA's game list, the left stick pushed right then let go: one step, like the d-pad. A small push does nothing.
    r = run(root, "rb a", pad=[(0.5, events((EV_ABS, ABS_X, 255))), (0.05, events((EV_ABS, ABS_X, 128))),
                           (0.3, events((EV_ABS, ABS_X, 170))), (0.1, events((EV_ABS, ABS_X, 128)))])
    assert "gamepad: opened" in r.log and r.props["sel"] == "1", (r.props.get("sel"), r.log[-600:])
    # Held: it repeats, as a held d-pad does (the first repeat after 380 ms, then every 90 ms).
    r = run(root, "rb a", pad=[(0.5, events((EV_ABS, ABS_X, 255))), (0.6, events((EV_ABS, ABS_X, 128)))])
    assert int(r.props["sel"]) >= 2, r.props["sel"]
    # The Y axis is up and down (a row holds 6 games): up from the second row comes back to the first.
    r = run(root, "rb a down", pad=[(0.5, events((EV_ABS, ABS_Y, 0))), (0.05, events((EV_ABS, ABS_Y, 128)))])
    assert r.props["sel"] == "0" and run(root, "rb a down").props["sel"] != "0", r.props

    # The back button is B: a system opened with A is left again.
    assert run(root, "rb a").props["openSys"] != ""
    r = run(root, "rb a", kbd=[(0.6, events((EV_KEY, KEY_F1, 1), (EV_KEY, KEY_F1, 0)))])
    assert r.props["openSys"] == "" and r.props["tab"] == "1", r.props

    # Home (guide) goes back to the start: the first tab's top, from a system's games, Settings, or a game's actions.
    for keys, gone in (("rb a guide", None), ("start guide", "Appearance"), ("rb a select guide", "Scrape this game"),
                       ("right y guide", None)):
        r = run(root, keys)
        assert r.props["tab"] == "0" and r.props["openSys"] == "" and r.props["sel"] == "0", (keys, r.props)
        assert r.props["reordering"] == "false" and r.props["details"] == "false", (keys, r.props)
        assert not gone or not r.shows(gone), (keys, gone)
print("ok")
