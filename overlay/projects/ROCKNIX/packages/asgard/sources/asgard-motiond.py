#!/usr/bin/env python3
"""asgard-motiond: the Thor's accelerometer and gyro (in the ADSP sensor core, read over QMI/QRTR from the SSC
service that thor-sensorspd brings up) served as a cemuhook/DSU motion source on 127.0.0.1:26760, pad 0.
Azahar (3DS) and Dolphin read motion from DSU servers. The same samples also go to InputPlumber's virtual pad (its
DualSense target's motion report, CompositeDevice.SendEvent over D-Bus), which is where Steam Input and SDL games
(Dusklight) read a gyro from.

Axes: asgard.motion_map in system.cfg, which sensor axis (and sign) feeds the DSU x, y and z. The default "-y,z,-x"
was measured on the Thor (2026-10-10): the sensor sits in the base with x towards the hinge, y to the left and z out of
the face; DSU wants x right, y out of the face, z towards the player. Accel in g, gyro in degrees per second (pitch,
yaw, roll = rotation about x, y, z). Checked in Azahar (Ocarina of Time 3D aiming). The pad gets the same axes unless
asgard.motion_map_pad says otherwise (same syntax; DualSense uses DSU's frame, but its signs are untested).
"""
import math
import os
import select
import signal
import socket
import struct
import sys
import time
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ssc  # noqa: E402

try:
    import dbussy
    from dbussy import DBUS
except ImportError:   # no D-Bus binding: DSU only
    dbussy = None

PORT = 26760
DEFAULT_MAP = "-y,z,-x"
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
    for part in (spec or DEFAULT_MAP).split(","):
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


# --- InputPlumber (Steam Input, SDL games) -------------------------------------------------------------------
IP = "org.shadowblip.InputPlumber"
IP_ROOT = "/org/shadowblip/InputPlumber"
ACCEL_LSB = 1632.6530612244898   # m/s² -> the units InputPlumber's own IIO IMU source sends (iio/accel_gyro_3d.rs)
GYRO_LSB = 916.7324722093172     # rad/s -> the same


class Pad:
    """Sends accel/gyro to the built-in pad's composite device. Fire and forget (no replies, so a slow InputPlumber
    never stalls the DSU stream); the device path is looked up again every few seconds, as InputPlumber recreates it
    when it restarts or the pad reconnects after sleep."""

    def __init__(self):
        self.conn = dbussy.Connection.bus_get(DBUS.BUS_SYSTEM, private=False) if dbussy else None
        self.path, self.found_at = None, 0.0
        self.accel = [0.0, 0.0, G]

    def find(self):
        msg = dbussy.Message.new_method_call(IP, IP_ROOT, DBUS.INTERFACE_INTROSPECTABLE, "Introspect")
        xml = self.conn.send_with_reply_and_block(msg, timeout=1000).expect_return_objects("s")[0]
        # ponytail: the first composite device is the built-in pad (it exists from boot; a Bluetooth pad comes later)
        names = sorted((n for n in (x.split('"')[1] for x in xml.split("<node name=")[1:])
                        if n.startswith("CompositeDevice")), key=lambda n: int(n[15:] or 0))
        return f"{IP_ROOT}/{names[0]}" if names else None

    def send(self, accel, gyro):
        self.accel = accel
        if not self.conn:
            return
        now = time.time()
        if now - self.found_at > 5:
            self.found_at = now
            try:
                self.path = self.find()
            except Exception as e:   # InputPlumber not up (yet): try again later
                self.path = None
                print("motiond: no InputPlumber pad:", e, file=sys.stderr, flush=True)
        if not self.path:
            return
        try:
            for cap, v in (("Gamepad:Accelerometer", [a * ACCEL_LSB for a in accel]),
                           ("Gamepad:Gyro", [g * GYRO_LSB for g in gyro])):
                msg = dbussy.Message.new_method_call(IP, self.path, "org.shadowblip.Input.CompositeDevice", "SendEvent")
                msg.append_objects("sv", cap, ("ad", v))
                msg.no_reply = True
                self.conn.send(msg)
            self.conn.flush()
        except Exception as e:   # never stop the DSU stream over it; look the pad up again
            self.path, self.found_at = None, 0.0
            print("motiond: InputPlumber send failed:", e, file=sys.stderr, flush=True)


def main():
    amap = gmap = axis_map(setting("asgard.motion_map", DEFAULT_MAP))   # one frame for both sensors
    pmap = axis_map(setting("asgard.motion_map_pad") or setting("asgard.motion_map", DEFAULT_MAP))
    pad = Pad()
    # InputPlumber's pad keeps the last values it was sent: on stop (Gyro switched off), leave it still, not turning
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    try:
        stream(amap, gmap, pmap, pad)
    finally:
        pad.found_at = 0.0
        pad.send(pad.accel, [0.0, 0.0, 0.0])


def stream(amap, gmap, pmap, pad):
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
        raw_accel = [0.0, 0.0, G]
        for name, ts, vals in ssc.stream(c, suids):
            if len(vals) < 3:
                continue
            last_rx = time.time()
            if name == "accel":
                accel = remap(vals[:3], amap)
                raw_accel = vals[:3]
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
            pad.send(remap(raw_accel, pmap), remap(vals[:3], pmap))
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
