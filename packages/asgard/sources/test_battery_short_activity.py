#!/usr/bin/env python3
# spec: BAT-5
# gap: battery-report.py gives every activity an average mA, even one 30 s sample long, which is one gauge step divided by 30 s.
# The gauge's figures only mean something over minutes, so a minute-long activity must not show an average current.
import importlib.util, os

spec = importlib.util.spec_from_file_location("br", os.path.join(os.path.dirname(os.path.abspath(__file__)), "battery-report.py"))
br = importlib.util.module_from_spec(spec)
spec.loader.exec_module(br)


def row(ts, uah, app): return {"ts": ts, "pct": 90, "ua": -400000, "uah": uah, "app": app, "game": "", "core": "", "chg": False}


seg = [row(i * 30, 3000000 - i * 3000, "menu") for i in range(120)]        # an hour of Home
seg += [row(3600 + i * 30, 2640000 - i * 8000, "retroarch") for i in range(2)]   # one minute of a game, one gauge step
seg += [row(3660, 2632000, "menu")]
acts = {a["name"]: a for a in br.report(seg)["session"]["activities"]}
short = acts.get("RetroArch")
assert short is None or short.get("ma") is None, f"an average current from a minute of gauge steps: {short}"
print("ok")
