#!/usr/bin/env python3
"""asgard-motiond: the Thor's accelerometer and gyro (in the ADSP sensor core, read over QMI/QRTR from the SSC
service that thor-sensorspd brings up) served as a cemuhook/DSU motion source on 127.0.0.1:26760, pad 0.
Azahar (3DS) and Dolphin read motion from DSU servers.

Axes: asgard.motion_map in system.cfg, e.g. "x,y,z" (default) or "-y,x,z": which sensor axis (and sign) feeds the
DSU x, y and z. Accel is sent in g, gyro in degrees per second (pitch, yaw, roll = rotation about x, y, z).
"""
import math
import os
import select
import socket
import struct
import sys
import time
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ssc  # noqa: E402

PORT = 26760
G = 9.80665
CFG = "/storage/.config/system/configs/system.cfg"


def setting(key, default=""):
    try:
        for line in reversed(open(CFG).read().splitlines()):
            if line.startswith(key + "="):
                return line.split("=", 1)[1]
    except OSError:
        pass
    return default


def axis_map(spec):
    """'x,-z,y' -> [(index, sign)] for the DSU x, y, z."""
    out = []
    for part in (spec or "x,y,z").split(","):
        part = part.strip()
        sign = -1.0 if part.startswith("-") else 1.0
        out.append(("xyz".index(part.lstrip("+-")), sign))
    return out


def remap(v, m):
    return [v[i] * s for i, s in m]


# --- DSU (cemuhook) server -------------------------------------------------------------------------------------
SERVER_ID = 0x41534744  # "ASGD"


def packet(msg_type, payload):
    body = struct.pack("<I", msg_type) + payload
    hdr = struct.pack("<4sHHII", b"DSUS", 1001, len(body), 0, SERVER_ID)
    crc = zlib.crc32(hdr + body) & 0xffffffff
    return struct.pack("<4sHHII", b"DSUS", 1001, len(body), crc, SERVER_ID) + body


def shared_header(slot):
    # slot, state 2 = connected, model 2 = full gyro, connection 1 = USB, MAC, battery 5 = full
    return struct.pack("<BBBB6sB", slot, 2 if slot == 0 else 0, 2, 1, b"\x00\x00\x00\x00\x00\x01", 5)


def pad_data(number, ts_us, accel_g, gyro_dps):
    p = shared_header(0) + struct.pack("<BI", 1, number)
    p += bytes([0, 0, 0, 0]) + bytes([128, 128, 128, 128]) + bytes(12)   # buttons, home/touch, sticks, analog
    p += bytes(12)                                                         # two touch points, inactive
    p += struct.pack("<Q", ts_us) + struct.pack("<3f", *accel_g) + struct.pack("<3f", *gyro_dps)
    return packet(0x100002, p)


def main():
    amap, gmap = axis_map(setting("asgard.motion_map", "x,y,z")), None
    gmap = amap
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", PORT))
    sock.setblocking(False)
    clients = {}   # addr -> last request time (clients re-request about every second)

    while True:   # (re)connect to the sensor core: it can restart (sleep, thor-sensorspd restarts)
        try:
            c = ssc.Ssc()
            suids = {"accel": ssc.lookup(c, "accel")[0], "gyro": ssc.lookup(c, "gyro")[0]}
        except (SystemExit, IndexError, OSError) as e:
            print("motiond: sensors not ready:", e, file=sys.stderr, flush=True)
            time.sleep(3)
            continue
        print("motiond: streaming", {k: f"{v[0]:x}" for k, v in suids.items()}, flush=True)
        accel, gyro, number, last_rx = [0.0, 0.0, G], [0.0, 0.0, 0.0], 0, time.time()
        for name, ts, vals in ssc.stream(c, suids):
            if len(vals) < 3:
                continue
            last_rx = time.time()
            if name == "accel":
                accel = remap(vals[:3], amap)
            else:
                gyro = remap(vals[:3], gmap)
            # client requests
            while select.select([sock], [], [], 0)[0]:
                try:
                    data, addr = sock.recvfrom(1024)
                except BlockingIOError:
                    break
                if len(data) < 20 or data[:4] != b"DSUC":
                    continue
                mtype = struct.unpack("<I", data[16:20])[0]
                if mtype == 0x100000:      # protocol version
                    sock.sendto(packet(0x100000, struct.pack("<H", 1001)), addr)
                elif mtype == 0x100001:    # ports info
                    n = struct.unpack("<i", data[20:24])[0]
                    for slot in data[24:24 + max(0, min(n, 4))]:
                        sock.sendto(packet(0x100001, shared_header(slot) + b"\x00"), addr)
                elif mtype == 0x100002:    # subscribe to pad data
                    clients[addr] = time.time()
            if name != "gyro":
                continue                    # one packet per gyro sample, with the latest accel
            now = time.time()
            for addr, t in list(clients.items()):
                if now - t > 5:
                    del clients[addr]
                    continue
                number += 1
                try:
                    sock.sendto(pad_data(number, int(now * 1e6), [a / G for a in accel],
                                         [math.degrees(g) for g in gyro]), addr)
                except OSError:
                    pass


if __name__ == "__main__":
    main()
