#!/usr/bin/env python3
# spec: BAT-4 LOG-6
# requires: cmd:bash cmd:awk cmd:stat
# Runs a copy of the real battery-log.sh, its paths rewritten into a temp dir, fed by the real playlog.py's launch record,
# and reads the result with the real battery-report.py. LOG-6 here: the line format, 30 s, rotation and the old file, the
# report reading both, one ps per sample and Nice=19. That its real CPU cost stays small is a device check.
import importlib.util
import csv
import os
import re
import subprocess
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
FIVE_MB = 5 * 1024 * 1024


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


br = module("br", "battery-report.py")
playlog = module("playlog", "playlog.py")

with tempfile.TemporaryDirectory() as t:
    def put(path, text):
        path = os.path.join(t, path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(text)

    for k, v in {"capacity": 71, "current_now": -400000, "voltage_now": 3900000, "charge_counter": 3000000, "temp": 310,
                 "status": "Discharging"}.items():
        put(f"sys/class/power_supply/battery/{k}", f"{v}\n")
    put("sys/class/power_supply/qcom-battmgr-usb/online", "0\n")
    put("sys/class/power_supply/qcom-battmgr-usb/current_now", "0\n")
    for p in (0, 3, 7):
        put(f"sys/devices/system/cpu/cpufreq/policy{p}/scaling_cur_freq", f"{p + 1}000\n")
    put("sys/class/devfreq/3d00000.gpu/cur_freq", "348000000\n")
    put("sys/class/backlight/a/brightness", "100\n")
    put("sys/class/backlight/b/brightness", "0\n")
    put("sys/power/suspend_stats/success", "4\n")
    os.makedirs(f"{t}/storage")
    os.makedirs(f"{t}/run")

    # Stubs: ps is whatever the case says, date advances 30 s a call, and sleep records its argument and ends the logger.
    put("bin/ps", f'#!/bin/sh\necho x >> "{t}/ps.calls"\ncat "{t}/ps.out"\n')
    put("bin/date", f'#!/bin/sh\nn=$(cat "{t}/now" 2>/dev/null || echo 1000); echo $((n + 30)) > "{t}/now"; echo $((n + 30))\n')
    put("bin/sleep", f'#!/bin/sh\necho "$1" >> "{t}/sleep.calls"\nkill -TERM $PPID\n')
    for stub in ("ps", "date", "sleep"):
        os.chmod(f"{t}/bin/{stub}", 0o755)
    put("ps.out", "sway sway\n")

    src = open(os.path.join(HERE, "battery-log.sh")).read()
    for root in ("/sys/", "/storage/", "/run/"):
        src = src.replace(root, f"{t}{root}")
    put("logger.sh", src)
    env = dict(os.environ, PATH=f"{t}/bin:{os.environ['PATH']}")
    LOG = f"{t}/storage/battery-log.csv"
    PLAYING = f"{t}/run/thor-playing.txt"

    def sample():
        """One pass of the logger's loop; returns its line as a dict."""
        subprocess.run(["bash", f"{t}/logger.sh"], env=env, check=False)
        lines = open(LOG).read().splitlines()
        return next(csv.DictReader([lines[0], lines[-1]]))

    def launch(*args):
        playlog.PLAYING = f"{t}/run/thor-playing.json"
        playlog.PLAYING_TXT = PLAYING
        playlog.start(*args)

    # LOG-6: one line per pass, with a header and the gauge's values, at 30 s, with one ps.
    r = sample()
    assert (r["capacity"], r["current_ua"], r["voltage_uv"], r["charge_uah"]) == ("71", "-400000", "3900000", "3000000"), r
    assert (r["cpu3_khz"], r["gpu_hz"], r["bl_top"], r["suspends"], r["bat_status"]) == ("4000", "348000000", "100", "4", "Discharging"), r
    assert r["app"] == "menu" and r["game"] == "" and r["core"] == "", r
    assert open(f"{t}/sleep.calls").read().split() == ["30"], "the logger's interval isn't 30 s"
    assert len(open(f"{t}/ps.calls").readlines()) == 1, "more than one ps per sample"
    assert len(open(LOG).readlines()) == 2, "not one line per sample"
    hdr = open(LOG).readline()

    # BAT-4: what Home launched: emulator, core and game (a comma or a quote in the name stays one field).
    launch('/roms/gba/Zelda "LA", Part 2.gba', "gba", "retroarch", "mgba")
    r = sample()
    assert (r["app"], r["core"], r["game"]) == ("retroarch", "mgba", 'Zelda "LA", Part 2'), r
    launch("/roms/gba/Metroid.gba", "gba", "retroarch", "mgba")
    sample()
    # BAT-4: a native port or PC app has no emulator process, and isn't Home.
    launch("/roms/ports/Doom.sh", "ports")
    r = sample()
    assert (r["app"], r["game"]) == ("ports", "Doom"), r
    sample()
    launch("/roms/pc/Gen1.desktop", "pc")
    r = sample()
    assert (r["app"], r["game"]) == ("pc", "Gen1"), r
    sample()
    os.unlink(PLAYING)
    sample()
    # ... and the report keeps them apart.
    rows = br.load([LOG])
    names = {a["name"] for a in br.report(rows)["session"]["activities"]}
    for want in ("Metroid · RetroArch mgba", "Doom · Ports", "Gen1 · PC", "Home"):
        assert want in names, (want, names)
    # An emulator that Home didn't launch still counts as that emulator; so do Thor's own UIs.
    put("ps.out", "retroarch retroarch -L x\n")
    assert sample()["app"] == "retroarch"
    put("ps.out", "python3 python3 /usr/share/asgard/thor_panel.py\n")
    assert sample()["app"] == "panel"
    put("ps.out", "sway sway\n")

    # LOG-6: at 5 MB or less it stays; past 5 MB it moves to .1 and replaces the old one; the header starts the new file.
    with open(LOG, "w") as f:
        f.write(hdr + "x" * (FIVE_MB - len(hdr) - 1) + "\n")
    sample()
    assert not os.path.exists(LOG + ".1"), "rotated at or under 5 MB"
    with open(LOG, "w") as f:
        f.write(hdr + "x" * FIVE_MB + "\n")
    put("storage/battery-log.csv.1", "the old one\n")
    r = sample()
    assert os.path.getsize(LOG + ".1") > FIVE_MB, "no rotation past 5 MB"
    assert open(LOG).readline() == hdr and len(open(LOG).readlines()) == 2, "the new file doesn't start with its header"
    assert sorted(f for f in os.listdir(f"{t}/storage") if f.startswith("battery-log")) == ["battery-log.csv", "battery-log.csv.1"]
    # A log in an older format isn't appended to.
    with open(LOG, "w") as f:
        f.write("ts,capacity\n1,2\n")
    sample()
    assert open(LOG + ".1").read() == "ts,capacity\n1,2\n" and open(LOG).readline() == hdr, "old format not rotated"

    # LOG-6: the report reads this file and the rotated one, in order.
    assert br.LOGS == ["/storage/battery-log.csv.1", "/storage/battery-log.csv"], br.LOGS
    # LOG-6: the logger's cost: lowest priority.
    unit = open(os.path.join(HERE, "..", "system.d", "thor-battery-log.service")).read()
    assert re.search(r"^Nice=19$", unit, re.M), "the logger runs above the lowest priority"
print("ok")
