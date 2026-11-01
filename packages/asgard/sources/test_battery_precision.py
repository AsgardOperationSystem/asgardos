#!/usr/bin/env python3
# spec: BAT-5
# The parts of BAT-5 the report meets: whole mA and 0.1 %, and no time-left guess from under half an hour of data. A figure
# for an activity too short to mean anything is test_battery_short_activity.py.
import importlib.util, os, tempfile

spec = importlib.util.spec_from_file_location("br", os.path.join(os.path.dirname(os.path.abspath(__file__)), "battery-report.py"))
br = importlib.util.module_from_spec(spec)
spec.loader.exec_module(br)


def rows(minutes, draw_per_sample=7777):
    """Discharging samples every 30 s, losing a non-round amount each."""
    return [{"ts": i * 30, "pct": 90 - i // 40, "ua": -400000, "uah": 3000000 - i * draw_per_sample, "app": "retroarch",
             "game": "", "core": "", "chg": False} for i in range(minutes * 2 + 1)]


r = br.report(rows(20))
assert "hours_left" not in r["now"], "a time-left guess from 20 minutes of gauge steps"
r = br.report(rows(40))
assert r["now"]["hours_left"] == round(r["now"]["hours_left"], 1), r["now"]
a = r["session"]["activities"][0]
assert isinstance(a["ma"], int), a
assert a["pct"] == round(a["pct"], 1), a
print("ok")
