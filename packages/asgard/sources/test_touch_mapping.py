#!/usr/bin/env python3
# spec: SCR-4
# requires: cmd:bash cmd:sh
"""The part of SCR-4 visible in the source: each touchscreen is mapped to its own panel, and thor-sway-rotate.sh gives both
the matrix that undoes sway's rotation, or the panel's saved calibration. A copy with its paths rewritten and a stub
swaymsg. Whether a tap lands under the finger is the human check."""
import os
import re
import stat
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True
from thor_touchcal import DEFAULT  # noqa: E402

INIT = open(os.path.join(HERE, "../../wayland/compositor/sway/autostart/111-sway-init")).read()
thor = INIT[INIT.index("# AYN Thor touchscreen setup"):]
assert re.search(r"""input "0:0:top_touchscreen" map_to_output DSI-2'""", thor), "top touch isn't on the top panel"
assert re.search(r"""input "0:0:bottom_touchscreen" map_to_output DSI-1'""", thor), "bottom touch isn't on the bottom panel"

ROOTED = re.compile(r'(?<![\w.$/}-])/(sys|run|storage|usr|etc|var|tmp)(?=[/\s"\':]|$)', re.M)
script = open(os.path.join(HERE, "thor-sway-rotate.sh")).read()


def rotate(cfg, sway=""):
    with tempfile.TemporaryDirectory() as t:
        os.makedirs(f"{t}/storage/.config/sway")
        os.makedirs(f"{t}/storage/.config/system/configs")
        os.makedirs(f"{t}/bin")
        with open(f"{t}/storage/.config/sway/config", "w") as f:
            f.write(sway)
        with open(f"{t}/storage/.config/system/configs/system.cfg", "w") as f:
            f.write(cfg)
        with open(f"{t}/bin/swaymsg", "w") as f:
            f.write("#!/bin/sh\nexit 0\n")
        os.chmod(f"{t}/bin/swaymsg", stat.S_IRWXU)
        with open(f"{t}/rotate.sh", "w") as f:
            f.write(ROOTED.sub(lambda m: f"{t}/{m.group(1)}", script))
        env = {**os.environ, "PATH": f"{t}/bin:{os.environ['PATH']}"}
        subprocess.run(["sh", f"{t}/rotate.sh"], env=env, capture_output=True, timeout=30)
        return open(f"{t}/storage/.config/sway/config").read()


def matrix(text, panel):
    found = re.findall(rf'^input "0:0:{panel}_touchscreen" calibration_matrix (.*)$', text, re.M)
    assert len(found) == 1, (panel, found)
    return [float(x) for x in found[0].split()]


text = rotate("")
assert "output DSI-1 transform 90" in text
for panel in ("top", "bottom"):
    assert matrix(text, panel) == DEFAULT, (panel, matrix(text, panel))   # the one thor_touchcal.py composes with
# A saved calibration is that panel's only, and a boot doesn't stack a second matrix on the old config.
SAVED = "asgard.touch.top=1 0 0 0 1 0\n"
text = rotate(SAVED, sway=text)
assert matrix(text, "top") == [1, 0, 0, 0, 1, 0] and matrix(text, "bottom") == DEFAULT, text[-300:]
assert text.count("output DSI-1 transform 90") == 1
print("touch mapping: ok")
