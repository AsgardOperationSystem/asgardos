"""Tiny controller-driven UI on top of the system SDL2 + SDL2_ttf + SDL2_image (ctypes, no extra deps).

Menus are drawn to look like ES-DE's own (dark menu scheme): blurred dimmed backdrop, centred #191919 panel,
uppercase Akrobat title and rows, black selection bar, ES-DE's own SVGs (chevron, option arrows, switches,
Switch-style help glyphs) loaded from the ES-DE install on the Thor. Measured from ES-DE 3.5.0 screenshots.

Buttons follow the Thor's printed Nintendo layout as InputPlumber reports it positionally:
physical A = SDL "b" (east) confirms, physical B = SDL "a" (south) goes back (matches ES-DE on this Thor).
"""
import ctypes as C
import fcntl
import os
import struct
import subprocess
import time

# ROCKNIX forces Zink (GL on Vulkan) for SM8550; for this app its EGL swap blocked forever on a GPU sync object
# (gdb, 2026-10-09). Mesa's native Adreno GL driver works. Must be set before SDL/EGL load.
os.environ["MESA_LOADER_DRIVER_OVERRIDE"] = "msm"
sdl = C.CDLL("libSDL2-2.0.so.0")
ttf = C.CDLL("libSDL2_ttf-2.0.so.0")
img = C.CDLL("libSDL2_image-2.0.so.0")

INIT_VIDEO, INIT_GAMECONTROLLER, INIT_EVENTS = 0x20, 0x2000, 0x4000
WINDOW_FULLSCREEN_DESKTOP = 0x1001
RENDERER_SOFTWARE = 0x1
QUIT, KEYDOWN, FINGERDOWN, FINGERUP, FINGERMOTION = 0x100, 0x300, 0x700, 0x701, 0x702
CONTROLLERAXISMOTION, CONTROLLERBUTTONDOWN, CONTROLLERBUTTONUP, CONTROLLERDEVICEADDED = 0x650, 0x651, 0x652, 0x653
BTN = {0: "south", 1: "east", 2: "west", 3: "north", 4: "select", 6: "start", 9: "l1", 10: "r1",
       11: "up", 12: "down", 13: "left", 14: "right"}
ACTION = {"east": "a", "south": "b", "north": "x", "west": "y", "up": "up", "down": "down",
          "left": "left", "right": "right", "start": "start", "select": "select", "l1": "pageup", "r1": "pagedown"}
# evdev codes of InputPlumber's virtual DualSense (positional, so east is the Thor's A), for grab_pad.
PAD_NAME = "Sony Interactive Entertainment DualSense Wireless Controller"
EV_BTN = {305: "east", 304: "south", 307: "north", 308: "west", 314: "select", 315: "start", 310: "l1", 311: "r1"}
KEYS = {1073741906: "up", 1073741905: "down", 1073741904: "left", 1073741903: "right",
        13: "a", 8: "b", 27: "b", 9: "x"}  # keyboard, for testing over SSH


def hint(action, text):
    """Help-bar entry: (glyph, label). Glyphs: a b x y start lr updown."""
    return (action, text)


class Color(C.Structure):
    _fields_ = [("r", C.c_uint8), ("g", C.c_uint8), ("b", C.c_uint8), ("a", C.c_uint8)]


class Rect(C.Structure):
    _fields_ = [("x", C.c_int), ("y", C.c_int), ("w", C.c_int), ("h", C.c_int)]


for fn, res, args in [
    ("SDL_CreateWindow", C.c_void_p, [C.c_char_p, C.c_int, C.c_int, C.c_int, C.c_int, C.c_uint32]),
    ("SDL_CreateRenderer", C.c_void_p, [C.c_void_p, C.c_int, C.c_uint32]),
    ("SDL_SetRenderDrawColor", C.c_int, [C.c_void_p, C.c_uint8, C.c_uint8, C.c_uint8, C.c_uint8]),
    ("SDL_SetRenderDrawBlendMode", C.c_int, [C.c_void_p, C.c_int]),
    ("SDL_RenderClear", C.c_int, [C.c_void_p]),
    ("SDL_RenderFillRect", C.c_int, [C.c_void_p, C.POINTER(Rect)]),
    ("SDL_RenderCopy", C.c_int, [C.c_void_p, C.c_void_p, C.c_void_p, C.POINTER(Rect)]),
    ("SDL_RenderCopyEx", C.c_int, [C.c_void_p, C.c_void_p, C.c_void_p, C.POINTER(Rect), C.c_double, C.c_void_p, C.c_int]),
    ("SDL_RenderPresent", None, [C.c_void_p]),
    ("SDL_GetRendererOutputSize", C.c_int, [C.c_void_p, C.POINTER(C.c_int), C.POINTER(C.c_int)]),
    ("SDL_CreateTextureFromSurface", C.c_void_p, [C.c_void_p, C.c_void_p]),
    ("SDL_SetTextureColorMod", C.c_int, [C.c_void_p, C.c_uint8, C.c_uint8, C.c_uint8]),
    ("SDL_DestroyTexture", None, [C.c_void_p]),
    ("SDL_FreeSurface", None, [C.c_void_p]),
    ("SDL_PollEvent", C.c_int, [C.c_void_p]),
    ("SDL_GameControllerOpen", C.c_void_p, [C.c_int]),
    ("SDL_ShowCursor", C.c_int, [C.c_int]),
    ("SDL_Delay", None, [C.c_uint32]),
    ("SDL_GetDisplayBounds", C.c_int, [C.c_int, C.c_void_p]),
    ("SDL_NumJoysticks", C.c_int, []),
    ("SDL_IsGameController", C.c_int, [C.c_int]),
    ("SDL_RWFromFile", C.c_void_p, [C.c_char_p, C.c_char_p]),
    ("SDL_SetHint", C.c_int, [C.c_char_p, C.c_char_p]),
]:
    getattr(sdl, fn).restype, getattr(sdl, fn).argtypes = res, args
ttf.TTF_OpenFont.restype, ttf.TTF_OpenFont.argtypes = C.c_void_p, [C.c_char_p, C.c_int]
ttf.TTF_RenderUTF8_Blended.restype = C.c_void_p
ttf.TTF_RenderUTF8_Blended.argtypes = [C.c_void_p, C.c_char_p, Color]
img.IMG_Load.restype, img.IMG_Load.argtypes = C.c_void_p, [C.c_char_p]
img.IMG_LoadSizedSVG_RW.restype, img.IMG_LoadSizedSVG_RW.argtypes = C.c_void_p, [C.c_void_p, C.c_int, C.c_int]

# Held d-pad repeat (ES-DE-like). 0.4 s / 0.07 s turned slightly long taps into multi-row skips.
REPEAT_DELAY, REPEAT_RATE = 0.5, 0.12
DEBUG = (open("/tmp/thor-settings-events.log", "a")
         if os.environ.get("THOR_SETTINGS_DEBUG") or os.path.exists("/tmp/thor-settings-debug") else None)
FONT = "/usr/share/fonts/liberation/LiberationSans-Regular.ttf"  # Thor Panel's font
ESDE_RES = "/usr/share/asgard/res"  # ES-DE 3.5.0 fonts + SVGs (MIT / OFL), vendored: the image has no ES-DE
MENU_FONT = f"{ESDE_RES}/fonts/Akrobat-Regular.ttf" if os.path.exists(f"{ESDE_RES}/fonts/Akrobat-Regular.ttf") else FONT
GFX = f"{ESDE_RES}/graphics"

# ES-DE dark menu scheme (measured): panel, selection, title, rows, separators, help text
M_PANEL, M_SEL, M_TITLE, M_TEXT, M_SEP, M_HELP = (25, 25, 25), (0, 0, 0), (144, 144, 144), (128, 128, 128), (48, 48, 48), (224, 224, 224)
# legacy names (Thor Panel)
BG, PANEL, SEL, TEXT, DIM, ACCENT = (18, 20, 26), (32, 36, 46), (52, 92, 160), (235, 238, 245), (150, 156, 170), (120, 180, 255)
GLYPH = {"a": "help/button_a_switch.svg", "b": "help/button_b_switch.svg", "x": "help/button_x_switch.svg",
         "y": "help/button_y_switch.svg", "start": "help/button_start_switch.svg", "lr": "help/dpad_leftright.svg",
         "updown": "help/dpad_updown.svg"}


class UI:
    def __init__(self, title="Thor Settings", display=0, grab_pad=False):
        bg_png = None
        if display == 0 and os.environ.get("WAYLAND_DISPLAY"):
            # Backdrop like ES-DE's menu: what was on screen, tiny (blur-by-upscale), captured before our window maps.
            bg_png = "/tmp/thor-ui-bg.png"
            subprocess.run(["grim", "-s", "0.0625", "-o", "DSI-2", bg_png], capture_output=True, timeout=5)
        if sdl.SDL_Init(INIT_VIDEO | INIT_GAMECONTROLLER | INIT_EVENTS) != 0 or ttf.TTF_Init() != 0:
            raise RuntimeError("SDL init failed")
        sdl.SDL_SetHint(b"SDL_RENDER_SCALE_QUALITY", b"linear")
        b = Rect()
        sdl.SDL_GetDisplayBounds(display, C.byref(b))  # 0 = top (DSI-2), 1 = bottom (DSI-1) via SDL_VIDEO_DISPLAY_PRIORITY
        self.win = sdl.SDL_CreateWindow(title.encode(), b.x, b.y, b.w, b.h, WINDOW_FULLSCREEN_DESKTOP)
        # Software renderer: menus don't need the GPU (and ROCKNIX's Zink GL hung us before).
        self.ren = (os.environ.get("THOR_UI_ACCEL") and sdl.SDL_CreateRenderer(self.win, -1, 0x2)) or \
            sdl.SDL_CreateRenderer(self.win, -1, RENDERER_SOFTWARE)
        sdl.SDL_SetRenderDrawBlendMode(self.ren, 1)
        sdl.SDL_ShowCursor(0)
        # Wayland applies fullscreen asynchronously: pump events until the compositor's size arrives.
        w, h = C.c_int(), C.c_int()
        ev = C.create_string_buffer(64)
        for _ in range(100):
            while sdl.SDL_PollEvent(ev):
                pass
            sdl.SDL_GetRendererOutputSize(self.ren, C.byref(w), C.byref(h))
            if w.value and h.value:
                break
            sdl.SDL_Delay(10)
        self.w, self.h = w.value, h.value
        # The settle loop above swallowed CONTROLLERDEVICEADDED, so open pads already present here.
        for i in range(sdl.SDL_NumJoysticks()):
            if sdl.SDL_IsGameController(i):
                sdl.SDL_GameControllerOpen(i)
        s = self.s = self.h / 1080
        self.fonts = {k: ttf.TTF_OpenFont(FONT.encode(), int(v * s)) for k, v in
                      {"title": 54, "item": 38, "small": 28}.items()}
        # ES-DE font sizes: LARGE 0.085, MEDIUM 0.045, SMALL 0.035 of screen height
        for k, v in {"m_title": 0.085, "m_item": 0.045, "m_small": 0.035}.items():
            self.fonts[k] = ttf.TTF_OpenFont(MENU_FONT.encode(), int(v * self.h))
        self.fonts["m_help"] = ttf.TTF_OpenFont(MENU_FONT.replace("Regular", "SemiBold").encode(), int(0.035 * self.h))
        self.row = int(68 * s)
        self.pad = int(60 * s)
        self.cache = {}
        self.icons = {}
        self.held = None  # (action, next_repeat_time)
        self.last_action = None
        self.touch = None  # (x, y) in window pixels of the last tap, when poll() returns "touch"
        self.drags = False  # also return "drag" / "release" (finger moved / lifted; self.touch updated), for sliders
        self.ev = C.create_string_buffer(64)
        # grab_pad: take the pad for ourselves (EVIOCGRAB) so the frontend and the running game don't also act on
        # the presses meant for this window; we then read it from evdev, as SDL no longer sees it. Released on exit.
        self.pad_fd = open_pad_grabbed() if grab_pad else None
        self.bg = None
        if bg_png and os.path.exists(bg_png):
            surf = img.IMG_Load(bg_png.encode())
            if surf:
                self.bg = sdl.SDL_CreateTextureFromSurface(self.ren, surf)
                sdl.SDL_FreeSurface(surf)

    # --- drawing primitives -------------------------------------------------------------------------------------
    def rect(self, x, y, w, h, color, alpha=255):
        sdl.SDL_SetRenderDrawColor(self.ren, *color, alpha)
        sdl.SDL_RenderFillRect(self.ren, C.byref(Rect(int(x), int(y), int(w), int(h))))

    def _text_tex(self, s, font, color):
        key = (s, font, color)
        if key not in self.cache:
            if len(self.cache) > 400:
                for t, _, _ in self.cache.values():
                    sdl.SDL_DestroyTexture(t)
                self.cache.clear()
            surf = ttf.TTF_RenderUTF8_Blended(self.fonts[font], (s or " ").encode(), Color(*color, 255))
            if not surf:
                return None
            w, h = C.cast(surf, C.POINTER(C.c_int))[4], C.cast(surf, C.POINTER(C.c_int))[5]
            tex = sdl.SDL_CreateTextureFromSurface(self.ren, surf)
            sdl.SDL_FreeSurface(surf)
            self.cache[key] = (tex, w, h)
        return self.cache[key]

    def text(self, s, x, y, font="item", color=TEXT, align="left", maxw=None, vcenter=False):
        t = self._text_tex(s, font, color)
        if not t:
            return 0
        tex, w, h = t
        dw = min(w, int(maxw)) if maxw else w  # ponytail: overlong text is squeezed, not ellipsized
        if align == "right":
            x -= dw
        elif align == "center":
            x -= dw // 2
        if vcenter:
            y -= h // 2
        sdl.SDL_RenderCopy(self.ren, tex, None, C.byref(Rect(int(x), int(y), dw, h)))
        return dw

    def text_w(self, s, font):
        t = self._text_tex(s, font, (255, 255, 255))
        return t[1] if t else 0

    def icon(self, name, x, y, w, h, color=None, flip=False):
        """ES-DE SVG at (x, y) sized w x h, tinted. Returns w (0 if the asset is missing)."""
        key = (name, int(w), int(h))
        if key not in self.icons:
            path = f"{GFX}/{name}"
            surf = None
            if os.path.exists(path):
                rw = sdl.SDL_RWFromFile(path.encode(), b"rb")
                surf = img.IMG_LoadSizedSVG_RW(rw, int(w), int(h)) if rw else None
            self.icons[key] = sdl.SDL_CreateTextureFromSurface(self.ren, surf) if surf else None
            if surf:
                sdl.SDL_FreeSurface(surf)
        tex = self.icons[key]
        if not tex:
            return 0
        if color:
            sdl.SDL_SetTextureColorMod(tex, *color)
        sdl.SDL_RenderCopyEx(self.ren, tex, None, C.byref(Rect(int(x), int(y), int(w), int(h))), 0.0, None, 1 if flip else 0)
        return w

    # --- ES-DE style chrome ----------------------------------------------------------------------------------------
    def backdrop(self):
        sdl.SDL_SetRenderDrawColor(self.ren, 0, 0, 0, 255)
        sdl.SDL_RenderClear(self.ren)
        if self.bg:
            sdl.SDL_RenderCopy(self.ren, self.bg, None, None)  # tiny capture upscaled with linear filtering = blur
            self.rect(0, 0, self.w, self.h, (0, 0, 0), 170)

    def help_bar(self, hints):
        s, gh = self.s, int(30 * self.s)
        items = [(g, t) for g, t in hints if g in GLYPH] if hints else []
        widths = [gh + int(8 * s) + self.text_w(t, "m_help") for _, t in items]
        total = sum(widths) + int(26 * s) * max(0, len(items) - 1)
        x, y = (self.w - total) // 2, int(self.h - 52 * s)
        for (g, t), wdt in zip(items, widths):
            self.icon(GLYPH[g], x, y - gh // 2, gh, gh, M_HELP)
            self.text(t, x + gh + int(8 * s), y, "m_help", M_HELP, vcenter=True)
            x += wdt + int(26 * s)

    def panel(self, title, n_rows, footer=0):
        """Draw the backdrop + menu panel; returns (x0, rows_y0, width, row_h)."""
        s = self.s
        pw = min(int(1132 * s), int(self.w * 0.92))
        x0, y0 = (self.w - pw) // 2, int(140 * s)
        title_h, row_h = int(136 * s), int(74 * s)
        ph = title_h + n_rows * row_h + int(footer * s) + int(14 * s)
        self.backdrop()
        self.rect(x0, y0, pw, ph, M_PANEL)
        self.text(title.upper(), self.w // 2, y0 + title_h // 2, "m_title", M_TITLE, "center", maxw=pw - 40, vcenter=True)
        return x0, y0 + title_h, pw, row_h

    def frame(self, title, hints):  # legacy (kept for callers that draw their own body)
        self.panel(title, 0)
        self.help_bar(hints)

    def resize(self):
        """Re-read the window size (sway may rotate/resize an output after the window was created)."""
        w, h = C.c_int(), C.c_int()
        sdl.SDL_GetRendererOutputSize(self.ren, C.byref(w), C.byref(h))
        if w.value and h.value:
            self.w, self.h = w.value, h.value

    def present(self):
        sdl.SDL_RenderPresent(self.ren)

    def show(self, draw):
        """Draw + present twice. The panel can show the previous commit until the next one arrives; a
        second present after each change makes sure the latest state is what's on the glass."""
        for _ in range(2):
            draw()
            self.present()

    # --- input -----------------------------------------------------------------------------------------------------
    def poll(self):
        """Return the next action ('a', 'b', 'up', ...) or None. Held d-pad/stick repeats."""
        act = self._poll_pad()
        if act:
            return act
        ev = self.ev
        moved = False  # finger motion is merged: only the latest position counts (a slider can't keep up with each)
        while sdl.SDL_PollEvent(ev):
            t = C.cast(ev, C.POINTER(C.c_uint32))[0]
            if DEBUG:
                DEBUG.write(f"{time.monotonic():.3f} type={t:#x} b12={ev.raw[12]} raw={ev.raw[:20].hex()}\n"); DEBUG.flush()
            if t == QUIT:
                return "quit"
            if t == CONTROLLERDEVICEADDED:
                sdl.SDL_GameControllerOpen(C.cast(ev, C.POINTER(C.c_int32))[2])
            elif t == CONTROLLERBUTTONDOWN:
                act = ACTION.get(BTN.get(ev.raw[12], ""))
                if act:
                    if act in ("up", "down", "left", "right", "pageup", "pagedown"):
                        self.held = (act, time.monotonic() + REPEAT_DELAY)
                    return act
            elif t == CONTROLLERBUTTONUP:
                self.held = None
            elif t == CONTROLLERAXISMOTION and ev.raw[12] == 1:  # left stick Y
                v = C.cast(C.addressof(ev) + 16, C.POINTER(C.c_int16))[0]
                if abs(v) > 20000:
                    act = "down" if v > 0 else "up"
                    if not self.held or self.held[0] != act:
                        self.held = (act, time.monotonic() + REPEAT_DELAY)
                        return act
                elif self.held and self.held[0] in ("up", "down"):
                    self.held = None
            elif t == FINGERDOWN:
                fx, fy = C.cast(C.addressof(ev) + 24, C.POINTER(C.c_float))[0:2]
                self.touch = (int(fx * self.w), int(fy * self.h))
                return "touch"
            elif t in (FINGERMOTION, FINGERUP) and self.drags:
                fx, fy = C.cast(C.addressof(ev) + 24, C.POINTER(C.c_float))[0:2]
                self.touch = (int(fx * self.w), int(fy * self.h))
                if t == FINGERUP:
                    return "release"
                moved = True
            elif t == KEYDOWN:
                act = KEYS.get(C.cast(C.addressof(ev) + 20, C.POINTER(C.c_int32))[0])
                if act:
                    return act
        if moved:
            return "drag"
        if self.held and time.monotonic() >= self.held[1]:
            self.held = (self.held[0], time.monotonic() + REPEAT_RATE)
            return self.held[0]
        return None

    def _poll_pad(self):
        while self.pad_fd is not None:
            try:
                data = os.read(self.pad_fd, 24)
            except BlockingIOError:
                return None
            except OSError:  # pad gone (InputPlumber restarted): fall back to SDL's events
                self.pad_fd = None
                return None
            _, _, etype, code, value = struct.unpack("llHHi", data)
            if etype == 1 and value == 1 and code in EV_BTN:
                return ACTION[EV_BTN[code]]
            if etype == 3 and code in (16, 17):  # ABS_HAT0X / ABS_HAT0Y: the d-pad
                if value == 0:
                    self.held = None
                    continue
                act = {(16, -1): "left", (16, 1): "right", (17, -1): "up", (17, 1): "down"}[(code, value)]
                self.held = (act, time.monotonic() + REPEAT_DELAY)
                return act
        return None

    def wait(self):
        while True:
            a = self.poll()
            if a:
                return a
            sdl.SDL_Delay(10)

    # --- widgets ---------------------------------------------------------------------------------------------------
    def _row(self, x0, y, pw, rh, label, value, selected, lr):
        s = self.s
        if selected:
            self.rect(x0, y, pw, rh, M_SEL)
        self.rect(x0, y + rh - 1, pw, 1, M_SEP)
        cy = y + rh // 2
        pad = int(10 * s)
        right = x0 + pw - pad
        fh = int(0.045 * self.h)
        if value in ("On", "Off"):  # ES-DE switch
            sw_h = int(fh * 0.62)
            sw_w = sw_h * 2
            self.icon("on.svg" if value == "On" else "off.svg", right - sw_w, cy - sw_h // 2, sw_w, sw_h, M_TEXT)
            vw = sw_w
        elif value and lr:  # ◁ VALUE ▷
            ah = int(fh * 0.78)
            aw = int(ah * 36 / 64)
            gap = int(10 * s)
            self.icon("option_arrow.svg", right - aw, cy - ah // 2, aw, ah, M_TEXT)
            tw = self.text(value.upper(), right - aw - gap, cy, "m_item", M_TEXT, "right", maxw=pw * 0.45, vcenter=True)
            self.icon("option_arrow.svg", right - aw - gap - tw - gap - aw, cy - ah // 2, aw, ah, M_TEXT, flip=True)
            vw = tw + 2 * aw + 2 * gap
        elif value:
            vw = self.text(value.upper(), right, cy, "m_item", M_TEXT, "right", maxw=pw * 0.45, vcenter=True)
        else:  # submenu / action: chevron
            ah = int(fh * 0.72)
            aw = int(ah * 0.55)
            self.icon("arrow.svg", right - aw, cy - ah // 2, aw, ah, M_TEXT)
            vw = aw
        self.text(label.upper(), x0 + pad, cy, "m_item", M_TEXT, maxw=pw - vw - 4 * pad, vcenter=True)

    def menu(self, title, items, sel=0, hints=None, lr=False):
        """items: list of (label, value_text). Returns chosen index, or None on back.
        With lr=True, left/right also return the index; self.last_action says which ('a', 'left', 'right')."""
        if hints is None:
            hints = ([hint("lr", "Change")] if lr else []) + [hint("a", "Select"), hint("b", "Back")]
        top = 0
        while True:
            visible = max(1, int((self.h - 140 * self.s - 136 * self.s - 120 * self.s) // (74 * self.s)))
            sel = max(0, min(sel, len(items) - 1)) if items else 0
            top = min(max(top, sel - visible + 1), sel)

            def draw():
                n = min(visible, max(1, len(items)))
                x0, y0, pw, rh = self.panel(title, n)
                for i, (label, value) in enumerate(items[top:top + visible]):
                    adj = lr is True or (bool(lr) and (top + i) in lr)
                    self._row(x0, y0 + i * rh, pw, rh, label, value, top + i == sel, adj)
                if not items:
                    self.text("NOTHING HERE", x0 + int(10 * self.s), y0 + rh // 2, "m_item", M_TEXT, vcenter=True)
                if top > 0:
                    self.icon("scroll_up.svg", x0 + pw // 2 - int(14 * self.s), y0 - int(30 * self.s), int(28 * self.s), int(14 * self.s), M_TEXT)
                if top + visible < len(items):
                    self.icon("scroll_down.svg", x0 + pw // 2 - int(14 * self.s), y0 + n * rh + int(2 * self.s), int(28 * self.s), int(14 * self.s), M_TEXT)
                self.help_bar(hints)
            self.show(draw)
            if DEBUG:
                DEBUG.write(f"{time.monotonic():.3f} frame drawn sel={sel}\n"); DEBUG.flush()
            a = self.wait()
            if DEBUG:
                DEBUG.write(f"{time.monotonic():.3f} action={a}\n"); DEBUG.flush()
            # Like ES-DE's menus: stop at the ends, never wrap (wrapping read as the list jumping).
            if a == "up":
                sel = max(0, sel - 1)
            elif a == "down":
                sel = min(max(0, len(items) - 1), sel + 1)
            elif a == "pageup":
                sel = max(0, sel - visible)
            elif a == "pagedown":
                sel = min(len(items) - 1, sel + visible)
            elif a == "a" and items:
                self.last_action = "a"
                return sel
            elif lr and a in ("left", "right") and items and (lr is True or sel in lr):
                self.last_action = a
                return sel
            elif a in ("b", "quit"):
                return None

    def _textbox(self, title, lines, hints):
        x0, y0, pw, rh = self.panel(title, max(1, len(lines)))
        for i, line in enumerate(lines):
            self.text(line.upper(), self.w // 2, y0 + i * rh + rh // 2, "m_item", M_TEXT, "center", maxw=pw - 40, vcenter=True)
        self.help_bar(hints)

    def message(self, title, lines, hints=None):
        hints = hints or [hint("a", "OK")]
        lines = [ln for ln in lines if ln]
        self.show(lambda: self._textbox(title, lines, hints))
        while self.wait() not in ("a", "b", "quit"):
            pass

    def busy(self, title, line):
        self.show(lambda: self._textbox(title, [line], []))

    def confirm(self, title, line=""):
        return self.menu(f"{title}: {line}" if line else title, [("No", ""), ("Yes", "")],
                         hints=[hint("a", "Choose"), hint("b", "Cancel")]) == 1

    def keyboard(self, title, initial="", secret=False):
        """On-screen keyboard. Returns the string, or None if cancelled. Start = done, (logical) y = backspace, x = shift."""
        rows_lower = ["1234567890-=", "qwertyuiop[]", "asdfghjkl;'\\", "zxcvbnm,./`@", "     "]
        rows_upper = ["!@#$%^&*()_+", "QWERTYUIOP{}", "ASDFGHJKL:\"|", "ZXCVBNM<>?~#", "     "]
        s, shift, r, c = initial, False, 0, 0
        hints = [hint("a", "Type"), hint("y", "Delete"), hint("x", "Shift"), hint("start", "Done"), hint("b", "Cancel")]
        while True:
            rows = rows_upper if shift else rows_lower
            r = max(0, min(r, len(rows) - 1))
            c = max(0, min(c, len(rows[r]) - 1))

            def draw():
                x0, y0, pw, rh = self.panel(title, 6)
                pad = int(14 * self.s)
                self.rect(x0 + pad, y0 + pad // 2, pw - 2 * pad, rh - pad, (38, 38, 38))
                shown = ("•" * len(s)) if secret else s
                self.text(shown + "_", x0 + 2 * pad, y0 + rh // 2, "m_item", (200, 200, 200), maxw=pw - 4 * pad, vcenter=True)
                cell_w = (pw - 2 * pad) / 12
                cell_h = rh * 0.98
                ky = y0 + rh
                for ri, row in enumerate(rows):
                    for ci, ch in enumerate(row if ri < 4 else ["SPACE"]):
                        w = cell_w * 12 if ri == 4 else cell_w
                        x, y = x0 + pad + ci * cell_w, ky + ri * cell_h
                        on = (ri, ci) == (r, c)
                        self.rect(x + 3, y + 3, w - 6, cell_h - 6, (0, 0, 0) if on else (38, 38, 38))
                        self.text(ch, x + w / 2, y + cell_h / 2, "m_item", M_HELP if on else M_TEXT, "center", vcenter=True)
                self.help_bar(hints)
            self.show(draw)
            a = self.wait()
            if a == "up":
                r = (r - 1) % len(rows)
            elif a == "down":
                r = (r + 1) % len(rows)
            elif a == "left":
                c = (c - 1) % (1 if r == 4 else 12)
            elif a == "right":
                c = (c + 1) % (1 if r == 4 else 12)
            elif a == "a":
                s += " " if r == 4 else rows[r][c]
            elif a == "y":
                s = s[:-1]
            elif a == "x":
                shift = not shift
            elif a == "start":
                return s
            elif a in ("b", "quit"):
                return None


def open_pad_grabbed():
    """The virtual pad's evdev node, opened non-blocking and grabbed (None if it isn't there)."""
    name = None
    try:
        for line in open("/proc/bus/input/devices"):
            if line.startswith("N: Name="):
                name = line[9:].strip().strip('"')
            elif line.startswith("H: Handlers=") and name == PAD_NAME:
                ev = next((h for h in line[12:].split() if h.startswith("event")), None)
                if ev:
                    fd = os.open("/dev/input/" + ev, os.O_RDONLY | os.O_NONBLOCK)
                    fcntl.ioctl(fd, 0x40044590, 1)  # EVIOCGRAB
                    return fd
    except OSError:
        pass
    return None


def run_cmd(cmd, timeout=60):
    """Run a shell command, return (rc, combined output)."""
    try:
        p = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout,
                           env={**os.environ, "SDL_GAMECONTROLLERCONFIG": ""})
        return p.returncode, (p.stdout + p.stderr).strip()
    except subprocess.TimeoutExpired:
        return 124, "timed out"
