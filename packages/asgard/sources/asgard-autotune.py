#!/usr/bin/env python3
"""Autotune: a game's cpu_cap_<type> / gpu_cap = "autotune" (asgard-perf-profile.sh starts it, asgard-cpu-lib.sh
autotune_stop ends it). Holds each tuned domain's clock ceiling at the lowest step that keeps the game's FPS.
ClusterTune's way (github.com/AurelioB/ClusterTune): only max clocks move, never min clocks or the governor; raise fast
when FPS falls short, lower one step at a time and undo a step that costs frames.
  asgard-autotune.py <domain>...     domain: little | mid | prime | gpu
FPS = sway's per-view frame counter (sway-100.02) of the busiest window. Target = its output's refresh rate, or the
plateau the game holds with everything at full clocks (a 30 fps game). Every change goes to /var/log/asgard-autotune.log.
ponytail: average FPS per second, so a step that adds stutter without losing frames isn't seen; sample sway every
250 ms and count long frames if that shows up.
"""
import json
import os
import subprocess
import sys
import time

CPU = "/sys/devices/system/cpu/cpufreq/policy"
GPU = "/sys/class/devfreq/3d00000.gpu"
POLICY = {"little": 0, "mid": 3, "prime": 7}
LOG = "/var/log/asgard-autotune.log"
SWAY = dict(os.environ, SWAYSOCK=os.environ.get("SWAYSOCK", "/run/0-runtime-dir/sway-ipc.0.sock"))

# Knobs, to calibrate on the Thor.
FLOOR = 0.25                # lowest ceiling, share of the top clock (set_cap's range)
GPU_FLOOR_HZ = 348_000_000  # lower GPU ceilings are untested against the GMU hangs
GPU_GAP = 5                 # s between GPU ceiling changes
HOLD = 8                    # s at target before a step down
PROBE = 4                   # s after a step down before it counts as kept
BACKOFF = 60                # s a domain that lost frames on a step down is left alone; doubles per failed probe,
MAX_BACKOFF = 600           # up to this, and starts over once the game needs more clock
SLACK = 2                   # fps under target that counts as short
IDLE_FPS = 5                # under this (paused, loading, screens off): hold


def read(path, default=""):
    try:
        return open(path).read().strip()
    except OSError:
        return default


def write(path, value):
    try:
        open(path, "w").write(str(value))
    except OSError:   # the cluster went offline (screens off): asgard-screens-off.sh stops us too
        pass


class Domain:
    """One clock ceiling: a CPU cluster's scaling_max_freq or the GPU's max_freq, as an index into its steps."""

    def __init__(self, name, steps, setter, floor, gap=0):
        self.name, self.steps, self.setter, self.gap = name, steps, setter, gap
        self.lo = next((i for i, s in enumerate(steps) if s >= floor), len(steps) - 1)
        self.i = len(steps) - 1   # asgard-perf-profile.sh starts it uncapped
        self.busy = 0.0           # 0..1, the bottleneck signal
        self.calm_until = 0.0     # no step down before this
        self.backoff = 0          # s, the current backoff
        self.last = -1e9          # time of the last change

    def top(self):
        return self.i == len(self.steps) - 1

    def ready(self, now):
        return now - self.last >= self.gap

    def set(self, i, now):
        i = max(self.lo, min(len(self.steps) - 1, i))
        if i == self.i:
            return False
        self.i, self.last = i, now
        self.setter(self.steps[i])
        return True


class Tuner:
    def __init__(self, domains, log=lambda msg: None):
        self.domains, self.log = domains, log
        self.ok = self.short = 0
        self.recent = []      # last few fps samples
        self.probe = None     # [domain, old index, fps before, until, samples]
        self.plateau = None   # fps the game holds at full clocks, when under the refresh rate
        self.flat = []

    def step(self, now, fps, target):
        if fps is None or fps < IDLE_FPS:
            self.ok = self.short = 0
            return
        self.recent = (self.recent + [fps])[-3:]
        if self.plateau and fps > self.plateau + SLACK:   # the game speeds up again (left a 30 fps scene)
            self.plateau = None
        goal = min(target, self.plateau or target)
        if self.probe:
            d, old, before, until, samples = self.probe
            samples.append(fps)
            if fps < goal - SLACK or (now >= until and sum(samples) / len(samples) < before - SLACK):
                d.set(old, now)
                d.backoff = min(max(BACKOFF, d.backoff * 2), MAX_BACKOFF)
                d.calm_until = now + d.backoff
                self.probe, self.ok = None, 0
                self.log(f"{d.name} back to {d.steps[d.i]} (fps {fps:.0f}, was {before:.0f})")
                return
            if now < until:
                return
            self.probe = None
        if fps < goal - SLACK:
            self.ok = 0
            self.short += 1
            if self.short >= 2:
                self.raise_(now, fps, goal)
            return
        self.short = 0
        self.ok += 1
        if self.ok >= HOLD:
            self.lower(now, fps)

    def raise_(self, now, fps, goal):
        up = [d for d in self.domains if not d.top()]
        if not up:   # all at full clocks and still short: the game's own rate if it holds steady
            self.flat = (self.flat + [fps])[-5:]
            if len(self.flat) == 5 and max(self.flat) - min(self.flat) <= SLACK:
                self.plateau = round(sum(self.flat) / 5)
                self.flat = []
                self.log(f"target {self.plateau} fps (holds it at full clocks)")
            return
        self.flat = []
        d = max(up, key=lambda d: d.busy)
        if d.ready(now) and d.set(d.i + 2, now):
            self.short, d.backoff = 0, 0
            self.log(f"{d.name} up to {d.steps[d.i]} (fps {fps:.0f} < {goal:.0f}, busy {d.busy:.0%})")

    def lower(self, now, fps):
        down = [d for d in self.domains if d.i > d.lo and now >= d.calm_until and d.ready(now)]
        if not down:
            return
        d = min(down, key=lambda d: d.busy)
        old = d.i
        if d.set(d.i - 1, now):
            self.ok = 0
            self.probe = [d, old, sum(self.recent) / len(self.recent), now + PROBE, []]
            self.log(f"{d.name} down to {d.steps[d.i]} (fps {fps:.0f}, busy {d.busy:.0%})")


def cpu_domain(name):
    p = f"{CPU}{POLICY[name]}"
    steps = sorted(int(x) for x in read(f"{p}/scaling_available_frequencies").split())
    if not steps:
        return None
    d = Domain(name, steps, lambda khz: write(f"{p}/scaling_max_freq", khz), steps[-1] * FLOOR)
    d.cpus = [int(c) for c in read(f"{p}/related_cpus").split()]
    return d


def gpu_domain():
    steps = sorted(int(x) for x in read(f"{GPU}/available_frequencies").split())
    if not steps:
        return None
    return Domain("gpu", steps, lambda hz: write(f"{GPU}/max_freq", hz),
                  max(steps[-1] * FLOOR, GPU_FLOOR_HZ), GPU_GAP)


def cpu_times():
    """cpu number -> (busy, total) jiffies from /proc/stat."""
    out = {}
    for line in read("/proc/stat").splitlines():
        f = line.split()
        if f and f[0].startswith("cpu") and f[0] != "cpu":
            v = [int(x) for x in f[1:]]
            out[int(f[0][3:])] = (sum(v) - v[3] - v[4], sum(v))   # idle + iowait
    return out


def gpu_times(text):
    """devfreq trans_stat -> {freq: ms spent there}: rows "[*]  <freq>: <transition counts...> <time ms>"."""
    out = {}
    for line in text.splitlines():
        f = line.replace("*", " ").split()
        if len(f) > 2 and f[0].endswith(":") and f[0][:-1].isdigit():
            out[int(f[0][:-1])] = int(f[-1])
    return out


def sway(kind):
    r = subprocess.run(["swaymsg", "-t", kind, "-r"], capture_output=True, text=True, env=SWAY)
    return json.loads(r.stdout) if r.returncode == 0 else None


def views(tree):
    """view id -> (frames, output name) for every window that counts frames (not the Thor Panel)."""
    out = {}

    def walk(n, output):
        if n.get("type") == "output":
            output = n.get("name")
        if "frames" in n and "Thor Panel" not in str(n.get("name")):
            out[n["id"]] = (n["frames"], output)
        for c in n.get("nodes", []) + n.get("floating_nodes", []):
            walk(c, output)
    walk(tree, None)
    return out


def main(names):
    domains = [d for d in (gpu_domain() if n == "gpu" else cpu_domain(n) for n in names if n in POLICY or n == "gpu")
               if d]
    if not domains:
        return

    def log(msg):
        with open(LOG, "a") as f:
            f.write(f"{time.strftime('%F %T')} {msg}\n")
    log("start: " + " ".join(d.name for d in domains))
    tuner = Tuner(domains, log)
    gpu = next((d for d in domains if d.name == "gpu"), None)
    t0, frames0, cpu0, gpu0 = time.monotonic(), {}, cpu_times(), gpu_times(read(f"{GPU}/trans_stat"))
    while True:
        time.sleep(1)
        now = time.monotonic()
        cpu1 = cpu_times()
        for d in domains:
            if d is not gpu:
                d.busy = max((((cpu1[c][0] - cpu0[c][0]) / max(1, cpu1[c][1] - cpu0[c][1]))
                              for c in d.cpus if c in cpu1 and c in cpu0), default=0.0)
        cpu0 = cpu1
        if gpu:   # share of the time at its ceiling: simple_ondemand only goes there above 90 % load
            gpu1 = gpu_times(read(f"{GPU}/trans_stat"))
            spent = {f: gpu1[f] - gpu0.get(f, 0) for f in gpu1}
            gpu.busy = sum(t for f, t in spent.items() if f >= gpu.steps[gpu.i]) / max(1, sum(spent.values()))
            gpu0 = gpu1
        tree, fps, target = sway("get_tree"), None, 60
        frames1 = views(tree) if tree else {}
        rates = {k: ((f - frames0[k][0]) / max(0.1, now - t0), out) for k, (f, out) in frames1.items() if k in frames0}
        if rates:
            fps, output = max(rates.values(), key=lambda r: r[0])
            for o in sway("get_outputs") or []:
                if o.get("name") == output and o.get("current_mode"):
                    target = o["current_mode"]["refresh"] / 1000
        t0, frames0 = now, frames1
        tuner.step(now, fps, target)


if __name__ == "__main__":
    main(sys.argv[1:])
