#!/usr/bin/env python3
"""Turn the Thor's screens off after IDLE seconds without input; any input turns them back on.

OLED burn-in guard for in-game idle (ES has its own screensaver). Reads every
/dev/input/event* except motion sensors and jack/lid/haptics; key and touch
events always count, stick axes only beyond ABS_THRESHOLD of their range.
Uses sway DPMS on outputs that were on, and restores exactly those.
"""
import fcntl, json, os, select, struct, subprocess, time

IDLE = int(os.environ.get("IDLE_SECONDS", "300"))
ABS_THRESHOLD = 0.10                      # fraction of axis range; filters stick jitter
SKIP = ("Motion Sensors", "Jack", "lid", "haptics")
SWAY = {"SWAYSOCK": "/var/run/0-runtime-dir/sway-ipc.0.sock"}
EV_KEY, EV_ABS = 0x01, 0x03
EVENT = struct.Struct("llHHi")


def name_of(path):
    try:
        with open(f"/sys/class/input/{os.path.basename(path)}/device/name") as f:
            return f.read().strip()
    except OSError:
        return ""


def abs_range(fd, code):
    buf = bytearray(24)  # struct input_absinfo: value, min, max, fuzz, flat, resolution
    try:
        fcntl.ioctl(fd, 0x80184540 + code, buf)  # EVIOCGABS(code)
    except OSError:
        return 0
    _, lo, hi = struct.unpack_from("iii", buf)
    return hi - lo


def open_devices(old):
    devs = {}
    for e in sorted(os.listdir("/dev/input")):
        if not e.startswith("event"):
            continue
        p = f"/dev/input/{e}"
        if p in old:
            devs[p] = old.pop(p)
            continue
        if any(s in name_of(p) for s in SKIP):
            continue
        try:
            devs[p] = {"fd": os.open(p, os.O_RDONLY | os.O_NONBLOCK), "last": {}, "range": {}}
        except OSError:
            pass
    for d in old.values():
        os.close(d["fd"])
    return devs


def is_activity(dev, typ, code, val):
    if typ == EV_KEY:
        return True
    if typ != EV_ABS:
        return False
    rng = dev["range"].setdefault(code, abs_range(dev["fd"], code))
    last = dev["last"].setdefault(code, val)
    if rng <= 0 or abs(val - last) >= rng * ABS_THRESHOLD:
        dev["last"][code] = val
        return True
    return False


def sway(*args):
    r = subprocess.run(["swaymsg", *args], env={**os.environ, **SWAY}, capture_output=True, text=True)
    return r.stdout


def lit_outputs():
    try:
        return [o["name"] for o in json.loads(sway("-t", "get_outputs", "-r")) if o.get("power") and o.get("dpms")]
    except (ValueError, KeyError):
        return []


def main():
    devs, blanked, last_input, last_scan = {}, [], time.monotonic(), 0
    while True:
        now = time.monotonic()
        if now - last_scan > 30:                 # pick up recreated virtual devices (e.g. after resume)
            devs, last_scan = open_devices(devs), now
        ready, _, _ = select.select([d["fd"] for d in devs.values()], [], [], 5)
        active = False
        for d in devs.values():
            if d["fd"] not in ready:
                continue
            try:
                data = os.read(d["fd"], EVENT.size * 64)
            except BlockingIOError:
                continue
            except OSError:
                last_scan = 0                     # device vanished; rescan next loop
                continue
            for off in range(0, len(data) - EVENT.size + 1, EVENT.size):
                _, _, typ, code, val = EVENT.unpack_from(data, off)
                active |= is_activity(d, typ, code, val)
        now = time.monotonic()
        if active:
            last_input = now
            if blanked:
                for o in blanked:
                    sway(f"output {o} dpms on")
                blanked = []
        elif not blanked and now - last_input >= IDLE:
            blanked = lit_outputs()
            for o in blanked:
                sway(f"output {o} dpms off")


if __name__ == "__main__":
    main()
