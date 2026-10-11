#!/usr/bin/env python3
"""Thor Panel: bottom-screen quick panel opened by the AYN button (KEY_F24, see thor_ayn_button.py).

Layout modelled on AYN's Android DualScreenAssistant panel (status bar; FPS card; 4x2 quick toggles in AYN's order;
TEMP card, FAN card = fan control; CPU/GPU/PWR/RAM ring gauges), drawn from scratch with SDL geometry (no AYN assets).
Page 2: volume and per-screen brightness sliders, with a lock that moves both screens together. Toggles act on
ROCKNIX's interfaces. Touch or d-pad + A (the pad is grabbed, so the paused game doesn't see it); L1/R1 = page;
only AYN closes.
Window title contains "Bottom" so ROCKNIX's sway rules put it on DSI-1.
"""
import ctypes as C
import glob
import json
import math
import os
import re
import shlex
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sdlui  # noqa: E402
from sdlui import run_cmd, sdl  # noqa: E402
from thor_settings import conf  # noqa: E402
import playlog  # noqa: E402

CPUFREQ = "/sys/devices/system/cpu/cpufreq"
POLICIES = ("policy0", "policy3", "policy7")
BAT = "/sys/class/power_supply/battery"
STATE = "/run/thor-panel.json"  # panel-only state (rumble level to restore)
SHOTS = "/storage/roms/screenshots"  # RetroArch's screenshot_directory; Asgard Home lists them per game
HOME_BOTTOM_Q = '[title="^Asgard Home .Bottom.$"]'  # Asgard Home's bottom window steps aside while the panel is open

# palette, picked from the reference photo
BG = (14, 12, 18)
CARD = (38, 35, 44)
CARD2 = (48, 44, 55)
ON = (160, 64, 210)
ON_HI = (196, 92, 236)
OFF = (100, 97, 108)
TEXT = (244, 242, 248)
DIM = (170, 166, 178)
PILL = (58, 160, 205)
TRACK = (66, 63, 72)
ARC = {"CPU": (230, 50, 150), "GPU": (40, 180, 232), "PWR": (240, 120, 40), "RAM": (90, 205, 90)}
# Page 2 copies Asgard Home's volume/brightness OSD (asgard-home qml/Osd.qml, Theme.qml): dark pill with a light rim,
# accent-gradient icon bubble, thin gradient track, Nunito Black. Accent = Settings > Appearance (asgard.accent).
HOME_QML = "/usr/share/asgard-home/qml"
# rim and track are the OSD's translucent white, pre-blended over the panel background / the pill
OSD_PILL, OSD_RIM, OSD_TRACK, OSD_DIM = (24, 26, 38), (98, 96, 100), (70, 72, 81), (201, 200, 224)
ACCENTS = {"aurora": ("#47d1ff", "#8f7dff"), "sunset": ("#ffb35c", "#ff4f8b"),
           "mint": ("#3ee6b0", "#3fb8ff"), "gold": ("#ffd86b", "#f59e24")}


def accent():
    a, b = ACCENTS.get(conf.get("asgard.accent", "aurora"), ACCENTS["aurora"])
    return tuple(int(a[i:i + 2], 16) for i in (1, 3, 5)), tuple(int(b[i:i + 2], 16) for i in (1, 3, 5))


def lerp(c0, c1, t):
    t = min(1, max(0, t))
    return tuple(int(a + (b - a) * t) for a, b in zip(c0, c1))


class Vertex(C.Structure):
    _fields_ = [("x", C.c_float), ("y", C.c_float), ("r", C.c_uint8), ("g", C.c_uint8), ("b", C.c_uint8),
                ("a", C.c_uint8), ("u", C.c_float), ("v", C.c_float)]


sdl.SDL_RenderGeometry.restype = C.c_int
sdl.SDL_RenderGeometry.argtypes = [C.c_void_p, C.c_void_p, C.POINTER(Vertex), C.c_int, C.c_void_p, C.c_int]


class Canvas:
    """Shapes on top of sdlui: triangles via SDL_RenderGeometry (circles, arcs, rounded rects, lines) + sized fonts."""

    def __init__(self, ui):
        self.ui = ui
        self.fonts = {}
        self.svgs = {}

    def tris(self, pts, color, alpha=255):
        vs = (Vertex * len(pts))(*[Vertex(x, y, *color, alpha, 0, 0) for x, y in pts])
        sdl.SDL_RenderGeometry(self.ui.ren, None, vs, len(pts), None, 0)

    def tris_c(self, pts, cols, alpha=255):
        """Triangles with a colour per vertex (gradients)."""
        vs = (Vertex * len(pts))(*[Vertex(x, y, *c, alpha, 0, 0) for (x, y), c in zip(pts, cols)])
        sdl.SDL_RenderGeometry(self.ui.ren, None, vs, len(pts), None, 0)

    def grad_rrect(self, x, y, w, h, c0, c1):
        """Fully rounded bar (radius h/2) with a left-to-right gradient, like the OSD's bubble and track fill."""
        r = h / 2
        col = lambda px: lerp(c0, c1, (px - x) / max(1, w))  # noqa: E731
        pts, cols = [], []
        for cx in (x + r, x + w - r):
            for i in range(32):
                a0, a1 = 2 * math.pi * i / 32, 2 * math.pi * (i + 1) / 32
                tri = [(cx, y + r), (cx + r * math.cos(a0), y + r + r * math.sin(a0)),
                       (cx + r * math.cos(a1), y + r + r * math.sin(a1))]
                pts += tri
                cols += [col(px) for px, _ in tri]
        if w > h:
            q = [(x + r, y), (x + w - r, y), (x + r, y + h), (x + r, y + h), (x + w - r, y), (x + w - r, y + h)]
            pts += q
            cols += [col(px) for px, _ in q]
        self.tris_c(pts, cols)

    def svg(self, path, x, y, size):
        """An SVG file (Asgard Home's icons) at (x, y), size x size; nothing if it's missing."""
        key = (path, int(size))
        if key not in self.svgs:
            surf = None
            if os.path.exists(path):
                rw = sdl.SDL_RWFromFile(path.encode(), b"rb")
                surf = sdlui.img.IMG_LoadSizedSVG_RW(rw, int(size), int(size)) if rw else None
            self.svgs[key] = sdl.SDL_CreateTextureFromSurface(self.ui.ren, surf) if surf else None
            if surf:
                sdl.SDL_FreeSurface(surf)
        if self.svgs[key]:
            sdl.SDL_RenderCopy(self.ui.ren, self.svgs[key], None, C.byref(sdlui.Rect(int(x), int(y), int(size), int(size))))

    def circle(self, cx, cy, r, color, alpha=255, seg=48):
        pts = []
        for i in range(seg):
            a0, a1 = 2 * math.pi * i / seg, 2 * math.pi * (i + 1) / seg
            pts += [(cx, cy), (cx + r * math.cos(a0), cy + r * math.sin(a0)), (cx + r * math.cos(a1), cy + r * math.sin(a1))]
        self.tris(pts, color, alpha)

    def arc(self, cx, cy, r, w, a0, a1, color, seg=64):
        """Thick arc; degrees, 0 = up, clockwise."""
        if a1 <= a0:
            return
        n = max(2, int(seg * (a1 - a0) / 360))
        pts = []
        for i in range(n):
            t0 = math.radians(a0 + (a1 - a0) * i / n - 90)
            t1 = math.radians(a0 + (a1 - a0) * (i + 1) / n - 90)
            o0 = (cx + r * math.cos(t0), cy + r * math.sin(t0))
            o1 = (cx + r * math.cos(t1), cy + r * math.sin(t1))
            i0 = (cx + (r - w) * math.cos(t0), cy + (r - w) * math.sin(t0))
            i1 = (cx + (r - w) * math.cos(t1), cy + (r - w) * math.sin(t1))
            pts += [o0, o1, i0, i0, o1, i1]
        self.tris(pts, color)

    def rrect(self, x, y, w, h, r, color, alpha=255):
        """Rounded rect as one triangle fan (float geometry: no seams between pieces, no double-drawn overlaps)."""
        r = min(r, w / 2, h / 2)
        n = max(6, int(r / 4))  # segments per corner
        ring = []
        for cx, cy, a in ((x + w - r, y + r, -90), (x + w - r, y + h - r, 0), (x + r, y + h - r, 90), (x + r, y + r, 180)):
            for i in range(n + 1):
                t = math.radians(a + 90 * i / n)
                ring.append((cx + r * math.cos(t), cy + r * math.sin(t)))
        c = (x + w / 2, y + h / 2)
        pts = []
        for i in range(len(ring)):
            pts += [c, ring[i], ring[(i + 1) % len(ring)]]
        self.tris(pts, color, alpha)

    def line(self, x0, y0, x1, y1, w, color):
        dx, dy = x1 - x0, y1 - y0
        d = math.hypot(dx, dy) or 1
        nx, ny = -dy / d * w / 2, dx / d * w / 2
        a, b, c, e = (x0 + nx, y0 + ny), (x1 + nx, y1 + ny), (x0 - nx, y0 - ny), (x1 - nx, y1 - ny)
        self.tris([a, b, c, c, b, e], color)

    def font(self, px, bold=False):
        key = (int(px), bold)
        if key not in self.fonts:
            path = sdlui.FONT.replace("Regular", "Bold") if bold else sdlui.FONT
            if bold == "osd" and os.path.exists(f"{HOME_QML}/fonts/Nunito-Black.ttf"):
                path = f"{HOME_QML}/fonts/Nunito-Black.ttf"  # the OSD's typeface
            elif bold == "osd":
                path = sdlui.FONT.replace("Regular", "Bold")
            name = f"p{key[0]}{bold if isinstance(bold, str) else 'b' if bold else ''}"
            self.ui.fonts[name] = sdlui.ttf.TTF_OpenFont(path.encode(), key[0])
            self.fonts[key] = name
        return self.fonts[key]

    def text(self, s, x, y, px, color=TEXT, align="left", bold=False, maxw=None):
        if maxw:  # too wide: a smaller font (sdlui would squeeze the glyphs instead)
            w = self.width(s, px, bold)
            if w > maxw:
                px = px * maxw / w
        return self.ui.text(s, x, y, self.font(px, bold), color, align, maxw)

    def width(self, s, px, bold=False):
        return self.ui.text(s, -99999, -99999, self.font(px, bold))


def icon(cv, name, cx, cy, s, col=TEXT):
    """Simple white glyphs centred on (cx, cy), roughly s px wide."""
    w = max(2, s * 0.09)

    def L(x0, y0, x1, y1):
        cv.line(x0, y0, x1, y1, w, col)

    if name == "fan":
        for a in (0, 120, 240):
            t = math.radians(a)
            cv.circle(cx + s * .22 * math.cos(t), cy + s * .22 * math.sin(t), s * .2, col)
        cv.circle(cx, cy, s * .08, CARD2)
    elif name == "clean":
        cv.rrect(cx - s * .3, cy - s * .12, s * .6, s * .46, s * .06, col)
        cv.rrect(cx - s * .38, cy - s * .3, s * .76, s * .12, s * .04, col)
        cv.rrect(cx - s * .1, cy - s * .44, s * .2, s * .14, s * .03, col)
        for k in (-.12, 0, .12):
            cv.line(cx + k * s, cy - s * .02, cx + k * s, cy + s * .24, w, CARD2)
    elif name == "style":
        cv.rrect(cx - s * .45, cy - s * .25, s * .9, s * .5, s * .2, col)
        cv.rrect(cx - s * .3, cy - s * .04, s * .16, s * .06, 2, CARD2)
        cv.rrect(cx - s * .25, cy - s * .09, s * .06, s * .16, 2, CARD2)
        cv.circle(cx + s * .22, cy - s * .03, s * .05, CARD2)
        cv.circle(cx + s * .3, cy + s * .05, s * .05, CARD2)
    elif name == "wifi":
        for r in (.2, .38, .56):
            cv.arc(cx, cy + s * .3, s * r, w, -45, 45, col)
        cv.circle(cx, cy + s * .3, s * .07, col)
    elif name == "airplane":
        cv.rrect(cx - s * .06, cy - s * .46, s * .12, s * .9, s * .06, col)
        cv.tris([(cx, cy - s * .14), (cx - s * .46, cy + s * .12), (cx + s * .46, cy + s * .12)], col)
        cv.tris([(cx, cy + s * .24), (cx - s * .2, cy + s * .42), (cx + s * .2, cy + s * .42)], col)
    elif name == "vibrate":
        cv.rrect(cx - s * .16, cy - s * .32, s * .32, s * .64, s * .06, col)
        for k in (-1, 1):
            L(cx + k * s * .28, cy - s * .18, cx + k * s * .36, cy - s * .06)
            L(cx + k * s * .36, cy - s * .06, cx + k * s * .28, cy + s * .06)
            L(cx + k * s * .28, cy + s * .06, cx + k * s * .36, cy + s * .18)
    elif name == "led":
        cv.circle(cx, cy - s * .2, s * .16, col)
        L(cx, cy - s * .05, cx, cy + s * .2)
        cv.rrect(cx - s * .32, cy + s * .2, s * .64, s * .14, s * .04, col)
    elif name == "speaker":
        cv.rrect(cx - s * .4, cy - s * .14, s * .22, s * .28, s * .03, col)
        cv.tris([(cx - s * .2, cy - s * .14), (cx + s * .05, cy - s * .38), (cx + s * .05, cy + s * .38),
                 (cx - s * .2, cy - s * .14), (cx + s * .05, cy + s * .38), (cx - s * .2, cy + s * .14)], col)
        for r in (.2, .34):
            cv.arc(cx + s * .05, cy, s * r, w, 50, 130, col)
    elif name == "sun":
        cv.circle(cx, cy, s * .2, col)
        for a in range(0, 360, 45):
            t = math.radians(a)
            L(cx + s * .3 * math.cos(t), cy + s * .3 * math.sin(t), cx + s * .44 * math.cos(t), cy + s * .44 * math.sin(t))
    elif name in ("lock", "unlock"):
        cv.rrect(cx - s * .3, cy - s * .04, s * .6, s * .44, s * .06, col)
        cv.arc(cx + (0 if name == "lock" else s * .28), cy - s * .04, s * .22, w * 1.3, -90, 90, col)
    elif name == "shot":
        cv.rrect(cx - s * .42, cy - s * .24, s * .84, s * .58, s * .08, col)
        cv.rrect(cx - s * .16, cy - s * .36, s * .32, s * .14, s * .04, col)
        cv.circle(cx, cy + s * .05, s * .19, CARD2)
        cv.circle(cx, cy + s * .05, s * .11, col)
    elif name == "thermo":
        cv.rrect(cx - s * .1, cy - s * .45, s * .2, s * .6, s * .1, col)
        cv.circle(cx, cy + s * .25, s * .18, col)
    elif name == "mode":
        cv.rrect(cx - s * .3, cy - s * .36, s * .6, s * .3, s * .08, col)
        cv.rrect(cx - s * .3, cy + s * .06, s * .6, s * .3, s * .08, col)
    elif name == "task":
        for dx in (-.19, .19):
            for dy in (-.19, .19):
                cv.rrect(cx + dx * s - s * .15, cy + dy * s - s * .15, s * .3, s * .3, s * .07, col)


# --- data -------------------------------------------------------------------------------------------------------
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
    json.dump({k: v for k, v in st.items() if k != "toast"}, open(STATE, "w"))


_net = {"t": 0.0, "b": 0, "rate": 0.0}


def net_rate():
    b = sum(int(read(f"/sys/class/net/wlan0/statistics/{k}_bytes", "0")) for k in ("rx", "tx"))
    now = time.monotonic()
    if _net["t"]:
        _net["rate"] = (b - _net["b"]) / max(0.1, now - _net["t"]) / 1024
    _net["t"], _net["b"] = now, b
    return _net["rate"]


def current_fps():
    """FPS from the game window title where the emulator reports it (melonDS "[59/60]", "... 60 FPS"), else None.
    ponytail: title-based only; RetroArch/Azahar don't put FPS in their titles, so they show "--"."""
    rc, out = run_cmd("swaymsg -t get_tree -r")
    if rc:
        return None

    def walk(n):
        t = str(n.get("name") or "")
        m = re.search(r"\[(\d+)/\d+\]", t) or re.search(r"(\d+(?:\.\d+)?)\s*FPS", t, re.I)
        if m and n.get("pid") and "Thor Panel" not in t:
            return float(m.group(1))
        for c in n.get("nodes", []) + n.get("floating_nodes", []):
            r = walk(c)
            if r is not None:
                return r
        return None
    return walk(json.loads(out))


def stats():
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
    return {
        "temp": max(temps) / 1000 if temps else 0, "fan": int(pwm) * 100 // 255 if pwm.isdigit() else 0,
        "gauges": [("CPU", f"{cpu / 1e6:.2f}", "GHz", cpu / cpu_max),
                   ("GPU", f"{gpu / 1e6:.0f}", "MHz", gpu / max(1, gpu_max)),
                   ("PWR", f"{watts:.2f}", "W", min(1, watts / 12)),
                   ("RAM", f"{used / 1048576:.2f}", "GB", used / tot)],
        "bat": read(f"{BAT}/capacity", "?"), "charging": read(f"{BAT}/status") == "Charging",
        "net": net_rate(), "fps": current_fps(),
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
    led = conf.get("led.color", "off")
    return [
        ("wifi", "Wi-Fi", wifi_on()),
        ("airplane", "Airplane mode", airplane_on()),
        ("vibrate", "Vibration", ra_rumble() > 0),
        ("led", "Ambient LED", led != "off"),
        ("shot", "Screenshot", False),
        ("clean", "Clean Memory", False),
        ("task", "Quit game", False),
    ]


# --- page 2: sliders --------------------------------------------------------------------------------------------
# The same settings and scripts as Asgard Home's Settings > Audio / Display: `volume`, and ROCKNIX's `brightness`
# (screen 1 = DSI-1 bottom, 2 = DSI-2 top); asgard.brightness_split = 1 is "unlocked" (each screen on its own).
SLIDERS = [("vol", "speaker", "Volume"), ("top", "sun", "Top screen"), ("bottom", "sun", "Bottom screen")]
MIN_BRIGHT = 5  # a black panel can't be found again by touch


def locked():
    return conf.get("asgard.brightness_split", "0") != "1"


def slider_value(key):
    if key == "vol":
        return int(conf.get("audio.volume", "50") or 50)
    if locked():
        return int(conf.get("system.brightness", "50") or 50)
    return int(conf.get("display.brightness2" if key == "top" else "display.brightness", "50") or 50)


def set_slider(key, v):
    if key == "vol":
        run_cmd(f"volume {v}")
    elif locked():
        run_cmd(f"brightness set {max(MIN_BRIGHT, v)}")
    else:
        run_cmd(f"brightness set {2 if key == 'top' else 1} {max(MIN_BRIGHT, v)}")


class Applier:
    """set_slider() on a thread, newest value per slider first: the scripts take 33-81 ms each, and running them in
    the UI loop left a dragged slider trailing the finger (worst linked: both screens)."""

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
        """Before the panel exits (the thread dies with it): wait for the last values to be applied."""
        with self.cv:
            self.cv.wait_for(lambda: not self.want and not self.busy, timeout=2)


def toggle_lock():
    """Locking puts both screens at the top screen's level, as Asgard Home's switch does."""
    top = slider_value("top")
    conf.set("asgard.brightness_split", "0" if not locked() else "1")
    if locked():
        run_cmd(f"brightness set {max(MIN_BRIGHT, top)}")


def toast(st, msg):
    st["toast"] = (msg, time.monotonic() + 2)


def activate(key, st):
    if key in ("fan", "fan-"):
        i = (fan_now() + (-1 if key == "fan-" else 1)) % len(FAN)
        set_fan(i)
        toast(st, "Fan: " + FAN[i][0] + (" (fixed)" if FAN[i][2] else ""))
    elif key == "clean":
        before = int(read("/proc/meminfo").split("MemAvailable:")[1].split()[0])
        run_cmd("sync; echo 3 > /proc/sys/vm/drop_caches")
        after = int(read("/proc/meminfo").split("MemAvailable:")[1].split()[0])
        toast(st, f"Freed {max(0, after - before) // 1024} MB")
    elif key == "wifi":
        on = not wifi_on()
        if on and airplane_on():
            conf.set("asgard.airplane", "0")
            run_cmd("rfkill unblock all")
        conf.set("wifi.enabled", "1" if on else "0")
        run_cmd(f"wifictl {'enable' if on else 'disable'}", 60)
        toast(st, "Wi-Fi on" if on else "Wi-Fi off")
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
        toast(st, "Airplane mode on" if on else "Airplane mode off")
    elif key == "vibrate":
        cur = ra_rumble()
        if cur > 0:
            st["rumble"] = cur
        new = 0 if cur > 0 else st.get("rumble", 25) or 25
        cfg = re.sub(r'^input_rumble_gain = "\d+"', f'input_rumble_gain = "{new}"', read(RA_CFG), flags=re.M)
        open(RA_CFG, "w").write(cfg + "\n")
        toast(st, "RetroArch rumble " + ("off" if new == 0 else "on"))
    elif key == "led":
        run_cmd(f"ledcontrol {'off' if conf.get('led.color', 'off') != 'off' else 'rgb'}")
    elif key == "shot":
        # Top screen only (the panel itself is on the bottom one); named like RetroArch's so Asgard Home matches the game.
        p = playlog.playing()
        stem = os.path.splitext(os.path.basename(p["rom"]))[0] if p else "Thor"
        path = f"{SHOTS}/{stem}-{time.strftime('%y%m%d-%H%M%S')}.png"
        ok = run_cmd(f"mkdir -p {SHOTS} && grim -o DSI-2 {shlex.quote(path)}")[0] == 0
        toast(st, "Screenshot saved" if ok else "Screenshot failed")
    elif key in ("fpsmode", "mode"):
        # the same setting as Settings > Display; thor-sway-rotate.sh applies it at boot
        hz = 60 if conf.get("asgard.refresh", "120") == "120" else 120
        if run_cmd(f"swaymsg output DSI-2 mode 1080x1920@{hz}Hz")[0] == 0:
            conf.set("asgard.refresh", str(hz))
        else:
            toast(st, f"{hz} Hz not available")
    elif key == "task":
        target = [w for w in read("/tmp/.process-kill-data").split() if not w.startswith("-")]
        if target and target not in (["emulationstation"],):
            # the game is frozen while the panel is open (thor_ayn_button.py): CONT so it can act on the TERM
            run_cmd(f"killall -TERM {' '.join(target)}; killall -CONT {' '.join(target)}")
            return "close"
        toast(st, "No game running")
    save_state(st)
    return None


# --- main loop --------------------------------------------------------------------------------------------------
def main():
    run_cmd(f"swaymsg '{HOME_BOTTOM_Q} move container to workspace thor-park'")
    # The pad is grabbed but only L1/R1 do anything: the game is paused underneath and must not see the presses.
    ui = sdlui.UI("Thor Panel (Bottom)", display=1, grab_pad=True)
    ui.drags = True
    cv = Canvas(ui)
    st = load_state()
    page = 0
    cols = 4
    drag = None  # slider being dragged (key)
    live = {}  # key -> (value, time): what the user just set, shown before the scripts have saved it
    applier = Applier()
    sel, sel2 = ("tog", 0), 0  # d-pad selection: page 1 (pill / tile / fan), page 2 (slider index, 3 = the lock)
    last_stats, data, last_shown = 0.0, None, None
    while True:
        ui.resize()
        W, H = ui.w, ui.h
        if data is None or time.monotonic() - last_stats > 2:
            data, last_stats = stats(), time.monotonic()
        tiles = toggles()
        pad = W * 0.03
        sb = H * 0.075
        # page 1: two rows fill the screen
        r1y, r1h = sb + pad * 0.3, H * 0.53
        r2y = r1y + r1h + pad * 0.6
        r2h = H - r2y - pad * 0.5
        fpsw = (W - 3 * pad) * 0.40
        togx, togw = pad * 2 + fpsw, W - 3 * pad - fpsw
        cell_w, cell_h = togw / cols, (r1h - pad * 0.9) / 2
        tog_pos = [(togx + cell_w * (i % cols) + cell_w / 2, r1y + pad * 0.3 + cell_h * (i // cols) + cell_h * 0.38)
                   for i in range(len(tiles))]
        btn_r = min(cell_w, cell_h) * 0.27
        pill = (pad + fpsw * 0.12, r1y + r1h * 0.1, fpsw * 0.76, r1h * 0.15)
        # page 2: a card of three wide sliders; the lock sits right of the two brightness ones
        cardy, cardh = sb + pad * 0.3, H - sb - pad * 0.8
        dots_y = cardy + cardh - pad * 0.7 if page else r1y + r1h - pad * 0.55
        sh = cardh * 0.19
        gap = (cardh - 3 * sh - pad * 1.6) / 4
        lockw = sh * 1.5
        sl_rect, track = {}, {}  # pill rect; the track's x and width (where a touch maps to 0-100 %)
        for k, (key, _, _) in enumerate(SLIDERS):
            y = cardy + gap * (k + 1) + sh * k
            w = W - 2 * pad - (0 if key == "vol" else lockw + pad)
            sl_rect[key] = (pad, y, w, sh)
            t0 = pad + sh * 1.09
            track[key] = (t0, pad + w - sh * 0.31 - cv.width("100%", sh * 0.33, "osd") - sh * 0.2 - t0)
        lock_rect = (W - pad - lockw, sl_rect["top"][1], lockw, sl_rect["bottom"][1] + sh - sl_rect["top"][1])
        values = {key: live[key][0] if key in live and time.monotonic() - live[key][1] < 1.5 else slider_value(key)
                  for key, _, _ in SLIDERS}
        msg = st.get("toast")
        if msg and time.monotonic() > msg[1]:
            st.pop("toast", None)
            msg = None

        def status_bar():
            fs = int(sb * 0.5)
            cv.text(time.strftime("%-I:%M %p"), pad, sb * 0.2, fs, TEXT, bold=True)
            pct = f"{data['bat']}%"
            bx = W - pad - cv.width(pct, fs, True)
            cv.text(pct, W - pad, sb * 0.2, fs, TEXT, "right", bold=True)
            bw, bh = sb * 0.75, sb * 0.42
            ix = bx - bw - pad * 0.3
            cv.rrect(ix, sb * 0.3, bw, bh, 4, TEXT)
            cv.rrect(ix + 3, sb * 0.3 + 3, bw - 6, bh - 6, 3, BG)
            frac = (int(data["bat"]) if str(data["bat"]).isdigit() else 0) / 100
            ui.rect(ix + 5, sb * 0.3 + 5, (bw - 10) * frac, bh - 10, (90, 205, 90) if data["charging"] else TEXT)
            cv.text(f"{data['net']:.1f}KB/S", ix - pad * 0.6, sb * 0.2, fs, TEXT, "right", bold=True)

        def dots(cx):
            for k in range(2):
                cv.circle(cx + (k - 0.5) * 22, dots_y, 6, ON_HI if k == page else TEXT)

        def draw_sliders():
            a0, a1 = accent()
            for k, (key, _, label) in enumerate(SLIDERS):
                x, y, w, h = sl_rect[key]
                v = values[key]
                if sel2 == k:  # d-pad selection: a white ring around the pill
                    cv.rrect(x - 5, y - 5, w + 10, h + 10, h / 2 + 5, TEXT)
                cv.rrect(x, y, w, h, h / 2, OSD_RIM)  # rim, then the pill inside it
                cv.rrect(x + 3, y + 3, w - 6, h - 6, (h - 6) / 2, OSD_PILL)
                d = h * 0.7  # icon bubble
                cv.grad_rrect(x + h * 0.15, y + h * 0.15, d, d, a0, a1)
                name = "brightness" if key != "vol" else "volume" if v > 0 else "volume-mute"
                cv.svg(f"{HOME_QML}/icons/osd/{name}.svg", x + h * 0.15 + d * 0.21, y + h * 0.15 + d * 0.21, d * 0.58)
                tx, tw = track[key]
                cv.text(label, tx, y + h * 0.17, h * 0.2, OSD_DIM, bold="osd", maxw=tw)
                th = h * 0.15
                ty = y + h * 0.6 - th / 2
                cv.rrect(tx, ty, tw, th, th / 2, OSD_TRACK)
                if v > 0:
                    cv.grad_rrect(tx, ty, max(th, tw * v / 100), th, a0, a1)
                cv.text(f"{v}%", x + w - h * 0.31, y + h * 0.5 - h * 0.23, h * 0.33, TEXT, "right", bold="osd")
            x, y, w, h = lock_rect
            on = locked()
            if sel2 == 3:
                cv.rrect(x - 5, y - 5, w + 10, h + 10, w / 2 + 5, TEXT)
            cv.rrect(x, y, w, h, w / 2, OSD_RIM)  # same pill as the sliders, standing up
            cv.rrect(x + 3, y + 3, w - 6, h - 6, w / 2 - 3, OSD_PILL)
            d = w * 0.62  # the bubble: accent gradient when the screens are linked, grey when separate
            bx, by = x + (w - d) / 2, y + h * 0.42 - d / 2
            if on:
                cv.grad_rrect(bx, by, d, d, a0, a1)
            else:
                cv.circle(bx + d / 2, by + d / 2, d / 2, OFF)
            icon(cv, "lock" if on else "unlock", bx + d / 2, by + d / 2, d * 0.55)
            cv.text("Linked" if on else "Separate", x + w / 2, by + d + h * 0.06, w * 0.16, OSD_DIM, "center",
                    bold="osd", maxw=w * 0.86)
            dots(W / 2)

        def draw():
            sdl.SDL_SetRenderDrawColor(ui.ren, *BG, 255)
            sdl.SDL_RenderClear(ui.ren)
            status_bar()
            if page:
                draw_sliders()
            else:
                # FPS card
                cv.rrect(pad, r1y, fpsw, r1h, 28, CARD)
                cv.rrect(*pill, pill[3] / 2, ON_HI if sel == ("pill", 0) else PILL)
                cv.text(f"{conf.get('asgard.refresh', '120')} FPS MODE", pill[0] + pill[2] / 2,
                        pill[1] + pill[3] * 0.12, pill[3] * 0.62, TEXT, "center", maxw=pill[2] * 0.86)
                num = f"{data['fps']:.0f}" if data["fps"] is not None else "--"
                big = r1h * 0.36
                nw = cv.width(num, big, True)
                cx = pad + fpsw / 2 - big * 0.3
                cv.text(num, cx, r1y + r1h * 0.33, big, TEXT, "center", bold=True)
                cv.text("FPS", cx + nw / 2 + 8, r1y + r1h * 0.52, big * 0.3, TEXT, bold=True)
                cv.text("CURRENT FPS", pad + fpsw / 2, r1y + r1h * 0.80, r1h * 0.075, DIM, "center", bold=True)
                # quick toggles
                cv.rrect(togx, r1y, togw, r1h, 28, CARD)
                for i, ((ic, label, on), (x, y)) in enumerate(zip(tiles, tog_pos)):
                    if sel == ("tog", i):
                        cv.circle(x, y, btn_r * 1.22, TEXT)
                    cv.circle(x, y, btn_r, ON if on else OFF)
                    if on:
                        cv.arc(x, y, btn_r, btn_r * 0.12, 0, 360, ON_HI)
                    icon(cv, ic, x, y, btn_r * 1.05)
                    lines = label.split(" ", 1) if len(label) > 13 else [label]
                    for k, ln in enumerate(lines):
                        cv.text(ln, x, y + btn_r * 1.25 + k * btn_r * 0.5, btn_r * 0.5, TEXT, "center", bold=True,
                                maxw=cell_w - 8)
                dots(togx + togw / 2)
                # TEMP card; FAN card = fan control (mode + current speed)
                cw = (fpsw - pad) / 2
                fan_mode = FAN[fan_now()][0]
                for k, (ic, label, val) in enumerate((("thermo", "TEMP", f"{data['temp']:.0f}°C"),
                                                      ("fan", "FAN", fan_mode.upper()))):
                    x = pad + k * (cw + pad)
                    if k == 1 and sel == ("fan", 0):
                        cv.rrect(x - 5, r2y - 5, cw + 10, r2h + 10, 28, TEXT)
                    cv.rrect(x, r2y, cw, r2h, 24, ON if k == 1 and conf.get("asgard.fan_manual", "") else CARD)
                    icon(cv, ic, x + cw * 0.22, r2y + r2h * 0.25, r2h * 0.2)
                    cv.text(label, x + cw * 0.62, r2y + r2h * 0.15, r2h * 0.13, TEXT, "center", bold=True,
                            maxw=cw * 0.6)
                    cv.text(val, x + cw * 0.5, r2y + r2h * (0.47 if len(val) <= 4 else 0.5),
                            r2h * (0.24 if len(val) <= 4 else 0.16), TEXT, "center", bold=True, maxw=cw * 0.9)
                    if k == 1:
                        # the mode is what a tap changes; the speed it runs at now is underneath
                        cv.text(f"now {data['fan']}%", x + cw * 0.5, r2y + r2h * 0.8, r2h * 0.1, DIM, "center",
                                bold=True)
                # gauges
                cv.rrect(togx, r2y, togw, r2h, 24, CARD)
                gr = min(togw / 8.6, r2h * 0.42)
                for k, (name, val, unit, frac) in enumerate(data["gauges"]):
                    gx, gy = togx + togw * (k + 0.5) / 4, r2y + r2h / 2
                    cv.arc(gx, gy, gr, gr * 0.12, 0, 360, TRACK)
                    cv.arc(gx, gy, gr, gr * 0.12, 0, max(4, 360 * min(1, max(0, frac))), ARC[name])
                    cv.text(name, gx, gy - gr * 0.62, gr * 0.3, DIM, "center", bold=True)
                    cv.text(val, gx, gy - gr * 0.3, gr * 0.5, TEXT, "center", bold=True)
                    cv.text(unit, gx, gy + gr * 0.28, gr * 0.26, DIM, "center", bold=True)
            if msg:
                tw = W * 0.5
                cv.rrect(W / 2 - tw / 2, H * 0.45, tw, H * 0.1, 20, (60, 56, 66), 235)
                cv.text(msg[0], W / 2, H * 0.47, H * 0.04, TEXT, "center", bold=True)

        shown = (W, H, page, drag, sel, sel2, json.dumps(data, default=str), json.dumps(tiles), json.dumps(values), locked(),
                 conf.get("asgard.refresh", "120"), str(msg), time.strftime("%H:%M"))
        if shown != last_shown:  # redraw only when something visible changed
            ui.show(draw)
            last_shown = shown

        a, deadline = None, time.monotonic() + 2.0
        while a is None and time.monotonic() < deadline:
            a = ui.poll()
            if a is None:
                sdl.SDL_Delay(15)
        if a == "quit":  # AYN again (thor_ayn_button.py sends SIGTERM; SDL makes it a quit)
            break
        if a in ("pageup", "pagedown"):  # L1 / R1
            page, drag = 1 - page, None
            continue

        def slide(key, v):
            v = min(100, max(0, v))
            for k in (("top", "bottom") if key != "vol" and locked() else (key,)):
                live[k] = (v, time.monotonic())
            applier.set(key, v)

        if a in ("drag", "release") and drag:
            x, w = track[drag]
            slide(drag, round((ui.touch[0] - x) * 100 / w))
            if a == "release":
                drag = None
            continue
        if a in ("up", "down", "left", "right", "a"):
            if page:
                if a in ("up", "down"):
                    sel2 = (sel2 + (1 if a == "down" else -1)) % 4
                elif sel2 == 3:
                    toggle_lock()  # left / right / A on the lock
                elif a in ("left", "right"):
                    key = SLIDERS[sel2][0]
                    slide(key, values[key] + (5 if a == "right" else -5))
                continue
            kind, idx = sel
            if a == "left":
                if kind == "tog":
                    sel = ("pill", 0) if idx % cols == 0 else ("tog", idx - 1)
                elif kind == "fan":
                    activate("fan-", st)
            elif a == "right":
                if kind == "pill":
                    sel = ("tog", 0)
                elif kind == "tog" and idx + 1 < len(tiles) and (idx + 1) % cols:
                    sel = ("tog", idx + 1)
                elif kind == "fan":
                    activate("fan", st)
            elif a == "down":
                if kind == "tog" and idx + cols < len(tiles):
                    sel = ("tog", idx + cols)
                elif kind in ("tog", "pill"):
                    sel = ("fan", 0)
            elif a == "up":
                if kind == "fan":
                    sel = ("tog", 0)
                elif kind == "tog" and idx >= cols:
                    sel = ("tog", idx - cols)
            else:  # A
                if activate(tiles[idx][0] if kind == "tog" else "fpsmode" if kind == "pill" else "fan", st) == "close":
                    break
                last_stats = 0.0
            continue
        if a != "touch":  # B, Start, ...: nothing (only AYN closes)
            continue
        tx, ty = ui.touch
        if abs(ty - dots_y) <= pad and abs(tx - ((W / 2) if page else (togx + togw / 2))) <= 60:
            page, drag = 1 - page, None  # tap the page dots
            continue
        if page:
            for key, (x, y, w, h) in sl_rect.items():
                if x <= tx <= x + w and y - gap / 2 <= ty <= y + h + gap / 2:
                    drag, sel2 = key, [k for k, _, _ in SLIDERS].index(key)
                    t0, tw = track[key]
                    slide(key, round((tx - t0) * 100 / tw))
            x, y, w, h = lock_rect
            if x <= tx <= x + w and y <= ty <= y + h:
                sel2 = 3
                toggle_lock()
            continue
        hit = None
        # A tile is its whole grid cell (icon and label), not just the icon: taps on the label missed.
        cw = tog_pos[1][0] - tog_pos[0][0] if len(tog_pos) > 1 else btn_r * 3
        ch = tog_pos[cols][1] - tog_pos[0][1] if len(tog_pos) > cols else btn_r * 5
        for i, (x, y) in enumerate(tog_pos):
            if abs(tx - x) <= cw / 2 and -ch * 0.4 <= ty - y <= ch * 0.6:
                hit = tiles[i][0]
        fan_x = pad + (fpsw - pad) / 2 + pad
        if fan_x <= tx <= fan_x + (fpsw - pad) / 2 and r2y <= ty <= r2y + r2h:
            hit = "fan"
        if pill[0] <= tx <= pill[0] + pill[2] and pill[1] <= ty <= pill[1] + pill[3]:
            hit = "fpsmode"
        if sdlui.DEBUG:
            sdlui.DEBUG.write(f"tap {tx},{ty} -> {hit}\n"); sdlui.DEBUG.flush()
        if hit:  # the d-pad carries on from what was tapped
            sel = ("fan", 0) if hit == "fan" else ("pill", 0) if hit == "fpsmode" else \
                ("tog", [t[0] for t in tiles].index(hit))
        if hit and activate(hit, st) == "close":
            break
        last_stats = 0.0
    applier.flush()
    save_state(st)
    run_cmd("swaymsg focus output DSI-2")
    rc, out = run_cmd("swaymsg -t get_tree -r")
    if not rc:
        def busy(n, o=None):
            if n.get("type") == "output":
                o = n.get("name")
            if o == "DSI-1" and n.get("pid") and n.get("name") not in ("Thor Panel (Bottom)", "Asgard Home (Bottom)"):
                return True
            return any(busy(c, o) for c in n.get("nodes", []) + n.get("floating_nodes", []))
        if busy(json.loads(out)):
            pass  # a game owns the bottom screen; Asgard Home stays parked meanwhile
        elif '"Asgard Home (Bottom)"' in out:
            run_cmd(f"swaymsg '{HOME_BOTTOM_Q} move container to output DSI-1'")
            game = [w for w in read("/tmp/.process-kill-data").split() if not w.startswith("-")]
            if game and game != ["emulationstation"]:
                # In a game Home's bottom window is hidden: the panel would stay lit (and touchable, which
                # pauses RetroArch) until Home came back. Off, like thor-bottom-idle-off.sh does at game start.
                run_cmd("swaymsg output DSI-1 power off")
        else:
            run_cmd("swaymsg output DSI-1 power off")


if __name__ == "__main__":
    main()
