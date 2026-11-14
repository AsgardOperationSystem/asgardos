#!/usr/bin/env python3
# spec: CAL-3
"""asgard.yml's asgard.stick_calibration reaches the sticks on a fresh install: asgard-gpcal-apply.sh (run before
InputPlumber starts) has asgard_config.py write it as the saved calibration, then applies it. A calibration made on
the device wins and is never overwritten; the yml's keys never land in system.cfg."""
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
YML = """asgard:
  charge_limit: 80
  stick_calibration:
    axis_leftx_min: -1350
    axis_leftx_center: 12
    axis_rightx_deadzone: 40
"""


def boot(root, yml, device_cal=None, gpcal_autostart=None):
    """One InputPlumber start: asgard-gpcal-apply.sh with the yml in root/flash.yml. Returns the rsinput params."""
    params, saved = f"{root}/params", f"{root}/asgard/gpcal.sh"
    os.makedirs(params, exist_ok=True)
    for p in ("axis_leftx_min", "axis_leftx_center", "axis_rightx_deadzone", "update_params"):
        open(f"{params}/{p}", "w").close()
    if yml is not None:
        open(f"{root}/flash.yml", "w").write(yml)
    elif os.path.exists(f"{root}/flash.yml"):
        os.remove(f"{root}/flash.yml")
    if device_cal is not None:
        os.makedirs(os.path.dirname(saved), exist_ok=True)
        open(saved, "w").write(device_cal)
    if gpcal_autostart is not None:
        os.makedirs(f"{root}/autostart", exist_ok=True)
        open(f"{root}/autostart/GPcal.sh", "w").write(gpcal_autostart)
    # asgard_config.py with this root's yml and system.cfg instead of /flash and /storage
    wrapper = f"{root}/cfg.py"
    open(wrapper, "w").write(
        "import importlib.util, sys\n"
        f"s = importlib.util.spec_from_file_location('c', {os.path.join(HERE, 'asgard_config.py')!r})\n"
        "c = importlib.util.module_from_spec(s); s.loader.exec_module(c)\n"
        f"c.SOURCES = [{root + '/flash.yml'!r}]\n"
        f"c.GPCAL_SAVED = sys.argv[2]\n"
        "c.main(stick=True)\n")
    env = dict(os.environ, ASGARD_CONFIG=f"{sys.executable} {wrapper}", GPCAL_SAVED=saved,
               GPCAL_AUTOSTART=f"{root}/autostart/GPcal.sh", RSINPUT_PARAMS=params)
    subprocess.run(["sh", os.path.join(HERE, "asgard-gpcal-apply.sh")], env=env, check=True, capture_output=True)
    return {p: open(f"{params}/{p}").read().strip() for p in sorted(os.listdir(params))}


with tempfile.TemporaryDirectory() as d:
    # Fresh install, no calibration on the device: the yml's values reach the driver on the first start.
    got = boot(d, YML)
    assert got == {"axis_leftx_min": "-1350", "axis_leftx_center": "12", "axis_rightx_deadzone": "40",
                   "update_params": "1"}, got
    first = open(f"{d}/asgard/gpcal.sh").read()
    # Same yml again: the file isn't rewritten.
    mtime = os.stat(f"{d}/asgard/gpcal.sh").st_mtime_ns
    boot(d, YML)
    assert os.stat(f"{d}/asgard/gpcal.sh").st_mtime_ns == mtime
    # The yml changes while the calibration is still the yml's: the new values apply.
    got = boot(d, YML.replace("-1350", "-1300"))
    assert got["axis_leftx_min"] == "-1300", got
    # The user calibrates on the device (GPcal leaves its autostart file): theirs wins, now and on every later boot.
    got = boot(d, YML, gpcal_autostart="echo -999 > /sys/module/rsinput/parameters/axis_leftx_min\n")
    assert got["axis_leftx_min"] == "-999", got
    got = boot(d, YML.replace("-1350", "-1111"))
    assert got["axis_leftx_min"] == "-999" and "asgard.yml" not in open(f"{d}/asgard/gpcal.sh").read(), got

with tempfile.TemporaryDirectory() as d:
    # A device calibration from before (no mark) is never replaced.
    got = boot(d, YML, device_cal="echo -777 > /sys/module/rsinput/parameters/axis_leftx_min\n")
    assert got["axis_leftx_min"] == "-777", got

with tempfile.TemporaryDirectory() as d:
    # No yml, or a yml without the section: nothing is written, the driver keeps its defaults.
    assert boot(d, None)["axis_leftx_min"] == "" and not os.path.exists(f"{d}/asgard/gpcal.sh")
    assert boot(d, "asgard:\n  charge_limit: 80\n")["axis_leftx_min"] == ""
    # A bad value or name writes nothing, and nothing outside rsinput's parameters can be reached.
    for bad in ("axis_leftx_min: 12abc", "update_params: 0", "'../../x': 1", "axis_leftx_min: 1; reboot"):
        got = boot(d, f"asgard:\n  stick_calibration:\n    {bad}\n")
        assert got["axis_leftx_min"] == "" and not os.path.exists(f"{d}/asgard/gpcal.sh"), (bad, got)

# The yml's calibration keys aren't system.cfg keys: the normal boot apply skips them.
import importlib.util  # noqa: E402
spec = importlib.util.spec_from_file_location("asgard_config", os.path.join(HERE, "asgard_config.py"))
config = importlib.util.module_from_spec(spec)
spec.loader.exec_module(config)
with tempfile.TemporaryDirectory() as d:
    config.APPLIED, config.SYS_CFG = f"{d}/applied.json", f"{d}/system.cfg"
    config.SYS_DEFAULT, config.AUTH_KEYS = f"{d}/default.cfg", f"{d}/authorized_keys"
    open(config.SYS_DEFAULT, "w").write("")
    wrote = config.apply(config.parse_yaml(YML))
    assert wrote == {"asgard.charge_limit": "80"}, wrote
print("ok")
