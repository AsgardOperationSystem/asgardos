# spec: DEV-18
"""Run: python -I test_sim_libretro_frame.py  (no Thor, no core): tools/sim/libretro_frame.py's own logic, the
simulated Thor's top screen of a game in play. libretro's three pixel formats come out as the right RGB, the frame is
scaled to the screen's height at the game's aspect and centred on black, and the PNG it writes decodes to that."""
import os
import struct
import sys
import tempfile
import zlib

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../../tools/sim"))
import libretro_frame as lf  # noqa: E402

# 2x1 frames, pitch wider than the row (cores pad): red then blue
xrgb = bytes([0, 0, 255, 0, 255, 0, 0, 0]) + bytes(8)                         # B G R X, little-endian
assert lf.rgb(xrgb, 2, 1, 16, 1) == bytes([255, 0, 0, 0, 0, 255])
rgb565 = struct.pack("<HH", 0xF800, 0x001F) + bytes(4)
assert lf.rgb(rgb565, 2, 1, 8, 2) == bytes([255, 0, 0, 0, 0, 255])
rgb1555 = struct.pack("<HH", 0x7C00, 0x001F)
assert lf.rgb(rgb1555, 2, 1, 4, 0) == bytes([255, 0, 0, 0, 0, 255])

# 4:3 on 1920x1080: 1440 wide, 240 black each side; the left half red, the right blue
rows = lf.letterbox(bytes([255, 0, 0, 0, 0, 255]), 2, 1, 4 / 3)
assert len(rows) == 1080 and all(len(r) == 1920 * 3 for r in rows)
px = lambda x, y: tuple(rows[y][3 * x:3 * x + 3])  # noqa: E731
assert px(0, 0) == (0, 0, 0) and px(239, 500) == (0, 0, 0) and px(1680, 500) == (0, 0, 0)
assert px(240, 0) == (255, 0, 0) and px(959, 1079) == (255, 0, 0) and px(960, 0) == (0, 0, 255) and px(1679, 0) == (0, 0, 255)

# The PNG: its header and pixels, read back the plain way (filter 0 rows)
with tempfile.TemporaryDirectory() as tmp:
    lf.png(f"{tmp}/f.png", rows, 1920)
    data = open(f"{tmp}/f.png", "rb").read()
    assert data[:8] == b"\x89PNG\r\n\x1a\n" and struct.unpack(">II", data[16:24]) == (1920, 1080)
    idat = data.index(b"IDAT")
    raw = zlib.decompress(data[idat + 4:idat + 4 + struct.unpack(">I", data[idat - 4:idat])[0]])
    line = 1 + 1920 * 3
    assert raw[0] == 0 and raw[1 + 3 * 240:1 + 3 * 241] == bytes([255, 0, 0]) and len(raw) == line * 1080
print("ok")
