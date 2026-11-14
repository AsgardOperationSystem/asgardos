#!/usr/bin/env python3
# spec: COMP-5
# requires: cmd:bash
# setsettings.sh's set_ds_span_opts, run for real against a fake RetroArch config folder: on the Thor the melonDS and DeSmuME
# cores get the top/bottom layout, gap and touch input that vertical-check's span needs (the image's melonDS default was
# Left/Right with joystick touch), each core's other options are kept, and RetroArch's aspect is the core's, unscaled.
# Elsewhere, and for other cores, nothing changes. Whether the picture really lands on both panels is a human check (COMP-5).
import os
import re
import subprocess
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = open(f"{HERE}/../../asgardos/sources/scripts/setsettings.sh").read()


def function(name):
    m = re.search(rf"^function {name}\(\) \{{\n.*?^\}}\n", SOURCE, re.M | re.S)
    assert m, name
    return m.group(0)


def run(core, device="AYN Thor", own=None):
    with tempfile.TemporaryDirectory() as t:
        with open(f"{t}/retroarch-core-options.cfg", "w") as f:
            f.write('melonds_screen_layout = "Left/Right"\nmelonds_touch_mode = "Joystick"\nmelonds_threaded_renderer = "enabled"\n'
                    'desmume_cpu_mode = "jit"\nmgba_solar_sensor_level = "0"\n')
        if own:
            os.makedirs(f"{t}/config/{own[0]}")
            with open(f"{t}/config/{own[0]}/{own[0]}.opt", "w") as f:
                f.write(own[1])
        script = (function("set_melondsds_opt") + function("set_ds_span_opts")
                  + f'add_setting() {{ echo "$2=$3" >>"{t}/ra"; }}\n'
                  + f'RETROARCH_PATH="{t}"; QUIRK_DEVICE="{device}"; CORE="{core}"\nset_ds_span_opts\n')
        subprocess.run(["bash", "-c", script], check=True)
        opts = {}
        for root, _, files in os.walk(f"{t}/config"):
            for name in files:
                opts[name] = dict(re.findall(r'^(\S+) = "(.*)"$', open(os.path.join(root, name)).read(), re.M))
        ra = open(f"{t}/ra").read().split() if os.path.exists(f"{t}/ra") else []
        return opts, ra


PINNED = ["aspect_ratio_index=22", "video_scale_integer=false"]

opts, ra = run("melonds")
assert opts == {"melonDS.opt": {"melonds_screen_layout": "Top/Bottom", "melonds_touch_mode": "Touch", "melonds_screen_gap": "31",
                                "melonds_threaded_renderer": "enabled"}}, opts
assert ra == PINNED, ra

opts, ra = run("desmume", own=("DeSmuME", 'desmume_screens_layout = "left/right"\ndesmume_pointer_type = "mouse"\n'
                                          'desmume_screens_gap = "0"\ndesmume_cpu_mode = "interpreter"\n'))
assert opts == {"DeSmuME.opt": {"desmume_screens_layout": "top/bottom", "desmume_pointer_type": "touch", "desmume_screens_gap": "31",
                                "desmume_cpu_mode": "interpreter"}}, opts
assert ra == PINNED, ra

# melonDS DS: ROCKNIX's set_melondsdsopts places it with a custom viewport, which integer scaling would undo.
assert run("melondsds") == ({}, ["video_scale_integer=false"])
assert run("mgba") == ({}, [])
assert run("melonds", device="AYN Odin 2") == ({}, [])

# It runs for every RetroArch launch, after the aspect and scaling settings it overrides.
tail = SOURCE[SOURCE.index("\nwait\n"):]
assert re.search(r"^set_melondsdsopts\nset_ds_span_opts\nflush_settings$", tail, re.M), "set_ds_span_opts isn't run before flush"
print("ok")
