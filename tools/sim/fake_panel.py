#!/usr/bin/env python3
"""The simulated Thor's stand-in for thor_panel.py --serve (Asgard Home's --panel, ASGARD_PANEL): the same line
protocol, "<id>\\t<command>\\t<value>" in and "<id>\\t<json>" out, with a fixed status and no command run. The real one
reads the machine's sysfs and runs radio, fan and kill commands, so on a desktop it would read and act on the desktop."""
import json
import sys

GAUGE = lambda name, value, unit, frac: {"name": name, "value": value, "unit": unit, "frac": frac}  # noqa: E731
STATUS = {
    "temp": 41.0, "fan": 30, "bat": "78", "charging": False, "net": 12.4, "fps": 60,
    "gauges": [GAUGE("CPU", "1.80", "GHz", 0.56), GAUGE("GPU", "443", "MHz", 0.66), GAUGE("PWR", "3.10", "W", 0.26),
               GAUGE("RAM", "3.42", "GB", 0.29)],
    "toggles": [{"key": "wifi", "label": "Wi-Fi", "on": True}, {"key": "airplane", "label": "Airplane mode", "on": False},
                {"key": "vibrate", "label": "Vibration", "on": True}, {"key": "led", "label": "Ambient LED", "on": True},
                {"key": "shot", "label": "Screenshot", "on": False}, {"key": "clean", "label": "Clean memory", "on": False},
                {"key": "task", "label": "Quit game", "on": False}, {"key": "fpsmode", "label": "120 Hz", "on": True}],
    "fan_mode": "Smart", "fan_fixed": False, "linked": True, "accent": "aurora", "vol": 50, "top": 70, "bottom": 70,
}


def serve(inp=sys.stdin, out=sys.stdout):
    for line in inp:
        rid, cmd = (line.rstrip("\n").split("\t") + [""])[:2]
        out.write(f"{rid}\t{json.dumps(STATUS if cmd == 'status' else None)}\n")
        out.flush()


if __name__ == "__main__" and sys.argv[1:] == ["--serve"]:
    serve()
