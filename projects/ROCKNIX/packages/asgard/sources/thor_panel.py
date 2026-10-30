#!/usr/bin/env python3
"""Thor Panel's hardware side: status and actions for Asgard Home's panel (asgard-panel --panel, qml/Panel.qml), which
thor_ayn_button.py opens on the bottom screen with the AYN button.

Layout modelled on AYN's Android DualScreenAssistant panel (status bar; FPS card; 4x2 quick toggles in AYN's order;
TEMP card, FAN card = fan control; CPU/GPU/PWR/RAM gauges); page 2: volume and per-screen brightness, with a lock that
moves both screens together. Toggles act on ROCKNIX's interfaces.

thor_panel.py --serve: one request per stdin line, "<id>\\t<command>[\\t<value>]"; one reply per stdout line,
"<id>\\t<json>". Commands: status (everything the panel shows), a toggle key (wifi, airplane, ... -> a message to show,
"close" or null), vol / top / bottom <0-100> (sliders, applied in the background, newest value first). The process
lives as long as the panel (python's start-up alone is a third of a second); end of input = the panel closed.
"""
import glob
import json
import os
import queue
import re
import shlex
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sdlui import run_cmd  # noqa: E402
from thor_settings import conf  # noqa: E402
import playlog  # noqa: E402

CPUFREQ = "/sys/devices/system/cpu/cpufreq"
POLICIES = ("policy0", "policy3", "policy7")
BAT = "/sys/class/power_supply/battery"
STATE = "/run/thor-panel.json"  # panel-only state: rumble level to restore, the last network sample
SHOTS = "/storage/roms/screenshots"  # RetroArch's screenshot_directory; Asgard Home lists them per game


def read(path, default=""):
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return default


def load_state():
    try:
        return json.load(open(STATE))
    except (OSError, ValueError):
        return {}


def save_state(st):
    json.dump(st, open(STATE, "w"))


def net_rate(st):
    """KB/s on wlan0 since the previous status (kept in STATE, so it survives the panel closing)."""
    b = sum(int(read(f"/sys/class/net/wlan0/statistics/{k}_bytes", "0")) for k in ("rx", "tx"))
    now = time.monotonic()
    t0, b0 = st.get("net", (0, 0))
    st["net"] = (now, b)
    return (b - b0) / max(0.1, now - t0) / 1024 if t0 and now - t0 < 10 else 0.0


def current_fps(st):
    """Frames/s of the busiest window since the previous status: sway's per-view "frames" (buffer commits, sway
    patch 1003), so every app works, emulators and Home alike. None until two samples, or on an unpatched sway.
    ponytail: counts presented frames, not the emulator's internal rate; a game that presents duplicate frames
    reads high. While the panel has the game frozen, thor_ayn_button.py's measure from just before (/run/thor-fps)."""
    try:
        return float(open("/run/thor-fps").read())
    except (OSError, ValueError):
        pass
    rc, out = run_cmd("swaymsg -t get_tree -r")
    if rc:
        return None
    frames = {}

    def walk(n):
        if "frames" in n and "Thor Panel" not in str(n.get("name")):
            frames[str(n["id"])] = n["frames"]
        for c in n.get("nodes", []) + n.get("floating_nodes", []):
            walk(c)
    walk(json.loads(out))
    now = time.monotonic()
    t0, f0 = st.get("fps", (0, {}))
    st["fps"] = (now, frames)
    if not frames or not t0 or now - t0 > 10:
        return None
    return max((f - f0.get(k, f)) / max(0.1, now - t0) for k, f in frames.items())


def stats(st):
    temps = [int(t) for t in (read(p, "0") for p in glob.glob("/sys/class/thermal/thermal_zone*/temp"))
             if t.lstrip("-").isdigit()]
    pwm = next((read(p) for p in glob.glob("/sys/class/hwmon/hwmon*/pwm1")), "")
    cpu = max((int(read(f"{CPUFREQ}/{p}/scaling_cur_freq", "0")) for p in POLICIES), default=0)
    cpu_max = max((int(read(f"{CPUFREQ}/{p}/cpuinfo_max_freq", "1")) for p in POLICIES), default=1)
    gdev = next(iter(glob.glob("/sys/class/devfreq/*gpu*")), "")
    gpu, gpu_max = int(read(f"{gdev}/cur_freq", "0")), int(read(f"{gdev}/max_freq", "1"))
    watts = abs(int(read(f"{BAT}/current_now", "0")) * int(read(f"{BAT}/voltage_now", "0"))) / 1e12
    mem = dict(line.split(":", 1) for line in read("/proc/meminfo").splitlines() if ":" in line)
    tot = int(mem.get("MemTotal", "1 kB").split()[0])
    used = tot - int(mem.get("MemAvailable", "0 kB").split()[0])
    gauge = lambda name, val, unit, frac: {"name": name, "value": val, "unit": unit, "frac": min(1, max(0, frac))}  # noqa: E731
    return {
        "temp": max(temps) / 1000 if temps else 0, "fan": int(pwm) * 100 // 255 if pwm.isdigit() else 0,
        "gauges": [gauge("CPU", f"{cpu / 1e6:.2f}", "GHz", cpu / cpu_max),
                   gauge("GPU", f"{gpu / 1e6:.0f}", "MHz", gpu / max(1, gpu_max)),
                   gauge("PWR", f"{watts:.2f}", "W", watts / 12),
                   gauge("RAM", f"{used / 1048576:.2f}", "GB", used / tot)],
        "bat": read(f"{BAT}/capacity", "?"), "charging": read(f"{BAT}/status") == "Charging",
        "net": net_rate(st), "fps": current_fps(st),
    }


# --- toggles, in AYN's order ------------------------------------------------------------------------------------
# Fan: ROCKNIX's fancontrol curves (cooling.profile), or a fixed speed (asgard.fan_manual = PWM 0-255; fancontrol is
# stopped and pwm1 held). No "off": the Thor needs some airflow under load.
FAN = [("Quiet", "quiet", 0), ("Smart", "moderate", 0), ("Sport", "aggressive", 0),
       ("30%", "", 77), ("50%", "", 128), ("75%", "", 191), ("100%", "", 255)]


def fan_now():
    manual = conf.get("asgard.fan_manual", "")
    for i, (_, prof, pwm) in enumerate(FAN):
        if (manual and str(pwm) == manual) or (not manual and prof == conf.get("cooling.profile", "moderate")):
            return i
    return 1


def set_fan(i):
    name, prof, pwm = FAN[i]
    conf.set("asgard.fan_manual", str(pwm) if pwm else None)
    if not pwm:
        conf.set("cooling.profile", prof)
    run_cmd("systemctl restart fancontrol")  # asgard-fan.sh applies a fixed speed instead of starting the curve


RA_CFG = "/storage/.config/retroarch/retroarch.cfg"


def wifi_on():
    return conf.get("wifi.enabled", "1") == "1" and not airplane_on()


def airplane_on():
    return conf.get("asgard.airplane", "0") == "1"


def ra_rumble():
    m = re.search(r'^input_rumble_gain = "(\d+)"', read(RA_CFG), re.M)
    return int(m.group(1)) if m else 100


def toggles():
    hz = conf.get("asgard.refresh", "120")
    return [
        {"key": "wifi", "label": "Wi-Fi", "on": wifi_on()},
        {"key": "airplane", "label": "Airplane mode", "on": airplane_on()},
        {"key": "vibrate", "label": "Vibration", "on": ra_rumble() > 0},
        {"key": "led", "label": "Ambient LED", "on": conf.get("led.color", "off") != "off"},
        {"key": "shot", "label": "Screenshot", "on": False},
        {"key": "clean", "label": "Clean memory", "on": False},
        {"key": "task", "label": "Quit game", "on": False},
        {"key": "fpsmode", "label": f"{hz} Hz", "on": hz == "120"},  # top screen refresh rate
    ]


# --- page 2: sliders --------------------------------------------------------------------------------------------
# The same settings and scripts as Asgard Home's Settings > Audio / Display: `volume`, and ROCKNIX's `brightness`
# (screen 1 = DSI-1 bottom, 2 = DSI-2 top); asgard.brightness_split = 1 is "unlocked" (each screen on its own).
SLIDERS = ("vol", "top", "bottom")
MIN_BRIGHT = 5  # a black panel can't be found again by touch


def locked():
    return conf.get("asgard.brightness_split", "0") != "1"


def slider_value(key):
    if key == "vol":
        return int(conf.get("audio.volume", "50") or 50)
    if locked():
        return int(conf.get("display.brightness2", "50") or 50)  # `brightness set` saves display.*, never system.brightness
    return int(conf.get("display.brightness2" if key == "top" else "display.brightness", "50") or 50)


def set_slider(key, v):
    if key == "vol":
        run_cmd(f"volume {v}")
    elif locked():
        run_cmd(f"brightness set {max(MIN_BRIGHT, v)}")
    else:
        run_cmd(f"brightness set {2 if key == 'top' else 1} {max(MIN_BRIGHT, v)}")


class Applier:
    """set_slider() on a thread, newest value per slider first: the scripts take 33-81 ms each, and a dragged slider
    sends far more values than that (worst linked: both screens)."""

    def __init__(self):
        self.want, self.busy, self.cv = {}, False, threading.Condition()
        threading.Thread(target=self.run, daemon=True).start()

    def set(self, key, v):
        with self.cv:
            self.want[key] = v
            self.cv.notify()

    def run(self):
        while True:
            with self.cv:
                while not self.want:
                    self.cv.wait()
                key, v = self.want.popitem()
                self.busy = True
            set_slider(key, v)
            with self.cv:
                self.busy = False
                self.cv.notify_all()

    def flush(self):
        """Before exiting (the thread dies with us): wait for the last values to be applied."""
        with self.cv:
            self.cv.wait_for(lambda: not self.want and not self.busy, timeout=2)


def toggle_lock():
    """Locking puts both screens at the top screen's level, as Asgard Home's switch does."""
    top = slider_value("top")
    conf.set("asgard.brightness_split", "0" if not locked() else "1")
    if locked():
        run_cmd(f"brightness set {max(MIN_BRIGHT, top)}")


def status(st):
    return {**stats(st), "toggles": toggles(), "fan_mode": FAN[fan_now()][0], "fan_fixed": bool(conf.get("asgard.fan_manual", "")),
            "linked": locked(), "accent": conf.get("asgard.accent", "aurora"), **{k: slider_value(k) for k in SLIDERS}}


def activate(key, st):
    """Run a tile; returns the message to show, "close" (the panel closes) or None."""
    if key in ("fan", "fan-"):
        i = (fan_now() + (-1 if key == "fan-" else 1)) % len(FAN)
        set_fan(i)
        return "Fan: " + FAN[i][0] + (" (fixed)" if FAN[i][2] else "")
    if key == "lock":
        toggle_lock()
    elif key == "clean":
        before = int(read("/proc/meminfo").split("MemAvailable:")[1].split()[0])
        run_cmd("sync; echo 3 > /proc/sys/vm/drop_caches")
        after = int(read("/proc/meminfo").split("MemAvailable:")[1].split()[0])
        return f"Freed {max(0, after - before) // 1024} MB"
    elif key == "wifi":
        on = not wifi_on()
        if on and airplane_on():
            conf.set("asgard.airplane", "0")
            run_cmd("rfkill unblock all")
        conf.set("wifi.enabled", "1" if on else "0")
        run_cmd(f"wifictl {'enable' if on else 'disable'}", 60)
        return "Wi-Fi on" if on else "Wi-Fi off"
    elif key == "airplane":
        # All radios off (rfkill); off again restores Wi-Fi and Bluetooth as they were. 090-asgard-tuning reapplies it.
        on = not airplane_on()
        conf.set("asgard.airplane", "1" if on else "0")
        if on:
            run_cmd("rfkill block all")
        else:
            run_cmd("rfkill unblock all")
            if conf.get("wifi.enabled", "1") == "1":
                run_cmd("wifictl enable", 60)
            if conf.get("bluetooth.enabled", "0") == "1":
                run_cmd("rocknix-bluetooth enable", 60)
        return "Airplane mode on" if on else "Airplane mode off"
    elif key == "vibrate":
        cur = ra_rumble()
        if cur > 0:
            st["rumble"] = cur
        new = 0 if cur > 0 else st.get("rumble", 25) or 25
        cfg = re.sub(r'^input_rumble_gain = "\d+"', f'input_rumble_gain = "{new}"', read(RA_CFG), flags=re.M)
        open(RA_CFG, "w").write(cfg + "\n")
        return "RetroArch rumble " + ("off" if new == 0 else "on")
    elif key == "led":
        run_cmd(f"ledcontrol {'off' if conf.get('led.color', 'off') != 'off' else 'rgb'}")
    elif key == "shot":
        # Top screen only (the panel itself is on the bottom one); named like RetroArch's so Asgard Home matches the game.
        p = playlog.playing()
        stem = os.path.splitext(os.path.basename(p["rom"]))[0] if p else "Thor"
        path = f"{SHOTS}/{stem}-{time.strftime('%y%m%d-%H%M%S')}.png"
        ok = run_cmd(f"mkdir -p {SHOTS} && grim -o DSI-2 {shlex.quote(path)}")[0] == 0
        return "Screenshot saved" if ok else "Screenshot failed"
    elif key == "fpsmode":
        # the same setting as Settings > Display; thor-sway-rotate.sh applies it at boot
        hz = 60 if conf.get("asgard.refresh", "120") == "120" else 120
        if run_cmd(f"swaymsg output DSI-2 mode 1080x1920@{hz}Hz")[0] == 0:
            conf.set("asgard.refresh", str(hz))
        else:
            return f"{hz} Hz not available"
    elif key == "task":
        target = [w for w in read("/tmp/.process-kill-data").split() if not w.startswith("-")]
        if target and target not in (["emulationstation"],):
            # the game is frozen while the panel is open (thor_ayn_button.py): CONT so it can act on the TERM
            run_cmd(f"killall -TERM {' '.join(target)}; killall -CONT {' '.join(target)}")
            return "close"
        return "No game running"
    return None


def serve(inp=sys.stdin, out=sys.stdout):
    """The --serve loop. Status answers at once; tiles run one at a time on a worker (Wi-Fi can take a minute), so
    the panel's status keeps coming meanwhile; sliders go to the Applier."""
    st, lock, todo, applier = load_state(), threading.Lock(), queue.Queue(), Applier()

    def reply(rid, fn):
        try:
            data = fn()
        except Exception as e:  # noqa: BLE001 - a broken reading must not take the panel's data down with it
            data = {"error": str(e)}
        with lock:
            out.write(f"{rid}\t{json.dumps(data)}\n")
            out.flush()
            save_state(st)

    def worker():
        while True:
            rid, cmd = todo.get()
            reply(rid, lambda: activate(cmd, st))
            todo.task_done()
    threading.Thread(target=worker, daemon=True).start()
    for line in inp:
        rid, cmd, value = (line.rstrip("\n").split("\t") + ["", ""])[:3]
        if cmd == "status":
            reply(rid, lambda: status(st))
        elif cmd in SLIDERS:
            applier.set(cmd, min(100, max(0, int(value or 0))))
            reply(rid, lambda: None)
        else:
            todo.put((rid, cmd))
    todo.join()
    applier.flush()


if __name__ == "__main__" and sys.argv[1:] == ["--serve"]:
    serve()
