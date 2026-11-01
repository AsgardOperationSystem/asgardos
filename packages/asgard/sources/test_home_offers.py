#!/usr/bin/env python3
# spec: PERF-1 PERF-4 PERF-5 PWR-11 INP-2 SND-1 CFG-7
# requires: file:build/AsgardOS-SM8550.aarch64/toolchain/usr/local/qt6/lib/libQt6Quick.so cmd:cmake cmd:bash cmd:flock
"""What Settings offers for the menu's profile, the fan, sleep mode, stick lights and the EQ, by pressing through it on
the host: the rows' values, what they save, the commands they would run. Commands are logged, not run: that the lights,
the fan and the sound change is a device or human check. Also CFG-7's part for Home: it starts with no system.cfg.
Sleep mode: from another mode, suspendmode writes the right sleep.conf; through Settings it doesn't, test_sleep_mode_applies.py."""
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "../../../tools/test"))
import home_harness as hh  # noqa: E402
from home_harness import CFG, Root  # noqa: E402

HARDWARE = "start down down down down a"
AUDIO, DISPLAY, PERFORMANCE = HARDWARE + " a", HARDWARE + " down a", HARDWARE + " down down a"
LITTLE, GPU, FAN, SLEEP = 0, 3, 4, 8   # rows of Performance
STICK_LIGHTS = DISPLAY + " " + " ".join(["down"] * 5) + " a"
SPEAKER_EQ, HEADPHONE_EQ = 3, 4        # rows of Audio


def keys(page, row, *presses):
    return " ".join([page] + ["down"] * row + list(presses))


def values(root):
    return dict(line.split("=", 1) for line in root.read(CFG).splitlines() if "=" in line)


def press(root, sequence, cfg="", env=None):
    """From this system.cfg, press: what's saved, and what it shows and would run."""
    root.write(CFG, cfg)
    res = root.run(sequence, env=env, ms=300)
    return values(root), res


def eq_qml(root, status):
    """Home's QML with asgard-eq.py status answering this, and every command logged."""
    out = f"{root.path}/.qml"
    shutil.rmtree(out, ignore_errors=True)
    shutil.copytree(f"{hh.SRC}/qml", out)
    text = open(f"{out}/Settings.qml").read()
    assert "backend.exec(" in text
    text = text.replace("backend.exec(", "fakeExec(").replace("    function close() {", """    function fakeExec(cmd, done) {
        console.log("exec: " + cmd)
        if (done) Qt.callLater(done, cmd.indexOf("asgard-eq.py status") >= 0 ? %s : "")
    }
    function close() {""" % json.dumps(json.dumps(status)))
    open(f"{out}/Settings.qml", "w").write(text)
    return {"ASGARD_HOME_QML": out}


def eq_commands(res):
    return re.findall(r"exec: python3 /usr/share/asgard/asgard-eq\.py ((?:set|use) .*)", res.log)


with Root() as r:
    r.library()

    # --- CFG-7: no system.cfg at all.
    os.remove(f"{r.path}/{CFG}")
    res = r.run("", ms=300)
    assert res.rc == 0 and res.shows("GBA"), (res.rc, res.texts)

    # --- PERF-1: the menu's cap per type is 25-100 % in fives, or Off. Left from the default 90.
    cap = "asgard.cpu_cap.little"
    assert press(r, keys(PERFORMANCE, LITTLE, *["left"] * 13))[0].get(cap) == "25"
    v, res = press(r, keys(PERFORMANCE, LITTLE, *["left"] * 14))
    assert v.get(cap) == "off", v
    assert "/usr/share/asgard/asgard-cpu-cap.sh" in res.log, "the cap isn't applied"
    assert press(r, keys(PERFORMANCE, LITTLE, *["left"] * 15))[0].get(cap) == "100"

    # --- PERF-4: the menu's GPU cap is 25-100 % in fives, with no Auto: Auto is per game (test_perf_profile.py).
    assert press(r, keys(PERFORMANCE, GPU, *["left"] * 15))[0].get("asgard.gpu_cap") == "25"
    v, res = press(r, keys(PERFORMANCE, GPU, *["left"] * 16))
    assert v.get("asgard.gpu_cap") == "100", v
    assert "/usr/share/asgard/asgard-cpu-cap.sh" in res.log, "the cap isn't applied"

    # --- PERF-5: the fan's curves and fixed speeds, in one row. Right from the default curve.
    fan = lambda n, cfg="": press(r, keys(PERFORMANCE, FAN, *["right"] * n), cfg)
    v, res = fan(1)
    assert v.get("cooling.profile") == "aggressive" and not v.get("asgard.fan_manual"), v
    assert "systemctl restart fancontrol" in res.log and res.shows("Sport"), res.texts
    for n, speed in ((2, "77"), (3, "128"), (4, "191"), (5, "255")):
        assert fan(n)[0].get("asgard.fan_manual") == speed, n
    v, res = fan(6)                                 # from a fixed speed back to a curve, which clears it
    assert v.get("cooling.profile") == "quiet" and not v.get("asgard.fan_manual"), v
    assert fan(7)[0].get("cooling.profile") == "moderate"
    assert fan(1, "asgard.fan_manual=128\n")[0].get("asgard.fan_manual") == "191", "a fixed speed isn't the row's value"

    # --- PWR-11: Sleep, Light sleep and Screen off only.
    for n, value, label in ((0, "", "Sleep"), (1, "freeze", "Light sleep"), (2, "off", "Screen off only"), (3, "mem", "Sleep")):
        v, res = press(r, keys(PERFORMANCE, SLEEP, *["right"] * n))
        assert v.get("system.suspendmode", "") == value, (n, v)
        assert res.shows(label), res.texts
        if n:
            assert f"shell: suspendmode {value}" in res.log, res.log[-300:]

    # --- INP-2: stick lights: off, colour or battery level, and a brightness.
    v, res = press(r, keys(STICK_LIGHTS, 0, "right"))
    assert v.get("led.color") == "rgb" and "shell: ledcontrol rgb" in res.log and res.shows("Colour"), res.texts
    v, res = press(r, keys(STICK_LIGHTS, 0, "right", "right"))
    assert v.get("led.color") == "battery" and "shell: ledcontrol battery" in res.log and res.shows("Battery level"), res.texts
    v, res = press(r, keys(STICK_LIGHTS, 1, "right"))
    assert v.get("analogsticks.led", "").split(" ")[0] == "255" and res.shows("High"), v
    assert "shell: analog_sticks_ledcontrol 255 " in res.log
    v, res = press(r, keys(STICK_LIGHTS, 2, "right"))   # a colour, for the right stick
    assert v.get("analogsticks.led", "").split(" ")[1:4] != ["0", "0", "255"], v
    assert "shell: analog_sticks_ledcontrol " in res.log

    # --- SND-1: the speaker's three. Right and left from each, so the cycle's order shows.
    env = eq_qml(r, {"speaker": "thor", "headphones": "thor", "headphones_name": "", "saved": []})
    res = press(r, keys(AUDIO, SPEAKER_EQ, "right"), env=env)[1]
    assert eq_commands(res) == ["set speaker joey"] and res.shows("Thor tuning"), eq_commands(res)
    res = press(r, keys(AUDIO, SPEAKER_EQ, "left"), env=env)[1]
    assert eq_commands(res) == ["set speaker off"], eq_commands(res)
    env = eq_qml(r, {"speaker": "joey", "headphones": "thor", "headphones_name": "", "saved": []})
    res = press(r, keys(AUDIO, SPEAKER_EQ, "right"), env=env)[1]
    assert eq_commands(res) == ["set speaker off"] and res.shows("Joey"), eq_commands(res)
    # The headphones' Thor tuning, Off, and AutoEQ: a saved profile by name, or a row to find one.
    env = eq_qml(r, {"speaker": "thor", "headphones": "thor", "headphones_name": "", "saved": []})
    res = press(r, keys(AUDIO, HEADPHONE_EQ, "right"), env=env)[1]
    assert eq_commands(res) == ["set headphones off"], eq_commands(res)
    assert res.shows("Find your headphones"), res.texts
    env = eq_qml(r, {"speaker": "thor", "headphones": "autoeq", "headphones_name": "HD 600", "saved": ["HD 600"]})
    res = press(r, keys(AUDIO, HEADPHONE_EQ, "right"), env=env)[1]
    assert eq_commands(res) == ["set headphones thor"] and res.shows("HD 600"), (eq_commands(res), res.texts)
    env = eq_qml(r, {"speaker": "thor", "headphones": "thor", "headphones_name": "", "saved": ["HD 600"]})
    res = press(r, keys(AUDIO, HEADPHONE_EQ, "left"), env=env)[1]
    assert eq_commands(res) == ["use 'HD 600'"], eq_commands(res)

# --- PWR-11: from another mode, suspendmode writes what each one means. A copy with its paths rewritten, as test_post_update.py.
ROOTED = re.compile(r'(?<![\w.$/}-])/(sys|run|storage|usr|etc|var|tmp)(?=[/\s"\':]|$)', re.M)
for mode, want in (("off", "AllowSuspend=no"), ("freeze", "SuspendState=freeze"), ("mem", "SuspendState=mem")):
    with tempfile.TemporaryDirectory() as t:
        def install(source, dest):
            text = ROOTED.sub(lambda m: f"{t}/{m.group(1)}", open(os.path.join(HERE, source)).read())
            os.makedirs(os.path.dirname(f"{t}/{dest}"), exist_ok=True)
            with open(f"{t}/{dest}", "w") as f:
                f.write(text.replace("local -a keys=() BASH_REMATCH", "local -a keys=()"))   # host bash older than the image's
            os.chmod(f"{t}/{dest}", stat.S_IRWXU)

        install("../../asgardos/profile.d/001-functions", "etc/profile.d/001-functions")
        install("../../asgardos/sources/scripts/suspendmode", "usr/bin/suspendmode")
        open(f"{t}/etc/os-release", "w").close()
        with open(f"{t}/etc/profile", "w") as f:
            f.write(f". {t}/etc/profile.d/001-functions\n")
        for d in ("storage/.config/sleep.conf.d", "storage/.config/system/configs", "tmp"):
            os.makedirs(f"{t}/{d}")
        with open(f"{t}/usr/bin/systemctl", "w") as f:
            f.write("#!/bin/sh\nexit 0\n")
        os.chmod(f"{t}/usr/bin/systemctl", stat.S_IRWXU)
        with open(f"{t}/storage/.config/system/configs/system.cfg", "w") as f:
            f.write("system.suspendmode=other\n")
        subprocess.run(["bash", f"{t}/usr/bin/suspendmode", mode], capture_output=True, timeout=30)
        conf = open(f"{t}/storage/.config/sleep.conf.d/sleep.conf").read()
        assert want in conf, (mode, conf)
        assert f"system.suspendmode={mode}\n" in open(f"{t}/storage/.config/system/configs/system.cfg").read()
print("home offers: ok")
