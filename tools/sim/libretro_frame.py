#!/usr/bin/env python3
"""A libretro frontend with no window, for the simulated Thor: runs a core on a ROM for some frames, pressing buttons on
a script, and writes the last frame as the top screen would show it (1920x1080, the game's aspect, black bars).
    python3 -I tools/sim/libretro_frame.py <core.so> <rom> <frames> <out.png> [button@first-last ...]
Buttons: b y select start up down left right a x l r (RetroPad). Standard library only (ctypes, zlib)."""
import ctypes as C
import os
import struct
import sys
import tempfile
import zlib

SCREEN = (1920, 1080)
BUTTONS = {n: i for i, n in enumerate("b y select start up down left right a x l r".split())}
ENV_GET_CAN_DUPE, ENV_GET_SYSTEM_DIRECTORY, ENV_SET_PIXEL_FORMAT, ENV_GET_SAVE_DIRECTORY = 3, 9, 10, 31


class GameInfo(C.Structure):
    _fields_ = [("path", C.c_char_p), ("data", C.c_void_p), ("size", C.c_size_t), ("meta", C.c_char_p)]


class SystemInfo(C.Structure):
    _fields_ = [("library_name", C.c_char_p), ("library_version", C.c_char_p), ("valid_extensions", C.c_char_p),
                ("need_fullpath", C.c_bool), ("block_extract", C.c_bool)]


class AVInfo(C.Structure):
    _fields_ = [("base_width", C.c_uint), ("base_height", C.c_uint), ("max_width", C.c_uint), ("max_height", C.c_uint),
                ("aspect_ratio", C.c_float), ("fps", C.c_double), ("sample_rate", C.c_double)]


ENV = C.CFUNCTYPE(C.c_bool, C.c_uint, C.c_void_p)
VIDEO = C.CFUNCTYPE(None, C.c_void_p, C.c_uint, C.c_uint, C.c_size_t)
SAMPLE = C.CFUNCTYPE(None, C.c_int16, C.c_int16)
BATCH = C.CFUNCTYPE(C.c_size_t, C.c_void_p, C.c_size_t)
POLL = C.CFUNCTYPE(None)
STATE = C.CFUNCTYPE(C.c_int16, C.c_uint, C.c_uint, C.c_uint, C.c_uint)


def rgb(raw, width, height, pitch, fmt):
    """The frame as packed RGB rows. fmt: 1 XRGB8888, 2 RGB565, 0 0RGB1555 (libretro's)."""
    out = bytearray(width * height * 3)
    for y in range(height):
        row = raw[y * pitch:y * pitch + width * (4 if fmt == 1 else 2)]
        o = y * width * 3
        if fmt == 1:   # little-endian B G R X
            out[o:o + width * 3:3], out[o + 1:o + width * 3:3], out[o + 2:o + width * 3:3] = row[2::4], row[1::4], row[0::4]
        else:
            for x, (v,) in enumerate(struct.iter_unpack("<H", row)):
                if fmt == 2:
                    r, g, b = (v >> 11) & 31, (v >> 5) & 63, v & 31
                    out[o + 3 * x:o + 3 * x + 3] = bytes((r << 3 | r >> 2, g << 2 | g >> 4, b << 3 | b >> 2))
                else:
                    r, g, b = (v >> 10) & 31, (v >> 5) & 31, v & 31
                    out[o + 3 * x:o + 3 * x + 3] = bytes((r << 3 | r >> 2, g << 3 | g >> 2, b << 3 | b >> 2))
    return out


def letterbox(pix, width, height, aspect):
    """Scaled (nearest) to the screen's height at the game's aspect, centred on black."""
    sw, sh = SCREEN
    h = sh
    w = min(sw, round(h * aspect))
    left = (sw - w) // 2
    cols = [min(width - 1, x * width // w) for x in range(w)]
    rows, cache = [], {}
    pad_l, pad_r = bytes(3 * left), bytes(3 * (sw - w - left))
    for y in range(h):
        sy = min(height - 1, y * height // h)
        if sy not in cache:
            src = pix[sy * width * 3:(sy + 1) * width * 3]
            cache[sy] = pad_l + b"".join(src[3 * c:3 * c + 3] for c in cols) + pad_r
        rows.append(cache[sy])
    return rows


def png(path, rows, width):
    chunk = lambda kind, data: (struct.pack(">I", len(data)) + kind + data  # noqa: E731
                                + struct.pack(">I", zlib.crc32(kind + data)))
    raw = b"".join(b"\0" + r for r in rows)
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, len(rows), 8, 2, 0, 0, 0))
                + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))


def run(core_path, rom, frames, out, presses=()):
    core = C.CDLL(os.path.abspath(core_path))
    scratch = tempfile.mkdtemp(prefix="asgard-sim-core-")   # system and save dirs: nothing lands beside the ROM
    state = {"fmt": 0, "frame": None, "n": 0}
    held = [(BUTTONS[b], int(a), int(z)) for b, span in (p.split("@") for p in presses) for a, z in [span.split("-")]]
    dir_c = C.c_char_p(scratch.encode())

    def env(cmd, data):
        if cmd == ENV_SET_PIXEL_FORMAT:
            state["fmt"] = C.cast(data, C.POINTER(C.c_int))[0]
            return state["fmt"] in (0, 1, 2)
        if cmd in (ENV_GET_SYSTEM_DIRECTORY, ENV_GET_SAVE_DIRECTORY):
            C.cast(data, C.POINTER(C.c_char_p))[0] = dir_c.value
            return True
        if cmd == ENV_GET_CAN_DUPE:
            C.cast(data, C.POINTER(C.c_bool))[0] = True
            return True
        return False

    def video(data, width, height, pitch):
        if data:   # NULL: the same frame again
            state["frame"] = (C.string_at(data, pitch * height), width, height, pitch)

    def input_state(port, device, index, button):
        return int(port == 0 and device == 1 and any(b == button and a <= state["n"] <= z for b, a, z in held))

    cbs = [ENV(env), VIDEO(video), SAMPLE(lambda left, right: None), BATCH(lambda data, n: n), POLL(lambda: None),
           STATE(input_state)]
    core.retro_set_environment(cbs[0])
    core.retro_init()
    for name, cb in zip(("video_refresh", "audio_sample", "audio_sample_batch", "input_poll", "input_state"), cbs[1:]):
        getattr(core, "retro_set_" + name)(cb)
    info = SystemInfo()
    core.retro_get_system_info(C.byref(info))
    data = open(rom, "rb").read()
    buf = C.create_string_buffer(data, len(data))
    game = GameInfo(rom.encode(), None if info.need_fullpath else C.cast(buf, C.c_void_p), len(data), None)
    core.retro_load_game.restype = C.c_bool
    if not core.retro_load_game(C.byref(game)):
        sys.exit(f"libretro_frame: {core_path} couldn't load {rom}")
    av = AVInfo()
    core.retro_get_system_av_info(C.byref(av))
    for state["n"] in range(frames):
        core.retro_run()
    raw, width, height, pitch = state["frame"]
    aspect = av.aspect_ratio if av.aspect_ratio > 0 else width / height
    png(out, letterbox(rgb(raw, width, height, pitch, state["fmt"]), width, height, aspect), SCREEN[0])
    core.retro_unload_game()
    core.retro_deinit()
    return f"{info.library_name.decode()} {info.library_version.decode()}: frame {frames}, {width}x{height}"


if __name__ == "__main__":
    if len(sys.argv) < 5:
        sys.exit(__doc__)
    print(run(sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4], sys.argv[5:]))
