#!/usr/bin/env python3
# spec: INP-1
# requires: cmd:python3
"""asgard-motiond's stream() with a fake sensor core and a UDP client on loopback, on a free port so nothing else on the
host is disturbed: it serves DSU where INP-1 says, a client gets the samples, and the same samples go to the pad. That the
real sensors and InputPlumber's DualSense answer is the device and human checks. The sensors-root half: test_perf_profile.py."""
import importlib.util
import math
import os
import socket
import struct
import sys
import threading
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location("motiond", os.path.join(HERE, "asgard-motiond.py"))
motiond = importlib.util.module_from_spec(spec)
spec.loader.exec_module(motiond)

assert motiond.PORT == 26760, motiond.PORT


class Stop(Exception):
    pass


bound = []


class Socket(socket.socket):
    def bind(self, address):
        bound.append(address[0])
        super().bind((address[0], 0))
        ports.append(self.getsockname()[1])


ports = []
samples = threading.Event()   # set once the client has subscribed
done = threading.Event()


class FakeSsc:
    @staticmethod
    def Ssc():
        return object()

    @staticmethod
    def lookup(_conn, name):
        return [(1 if name == "accel" else 2, 0)]

    @staticmethod
    def stream(_conn, _suids):
        # Requests are served between samples: keep them coming until the client has what it wants.
        while not done.is_set():
            yield "accel", 0, [1.0, 2.0, motiond.G]
            yield "gyro", 0, [0.1, 0.2, 0.3]
        raise Stop


class Pad:
    sent = []

    def send(self, accel, gyro):
        self.sent.append((accel, gyro))


motiond.ssc = FakeSsc
real = socket.socket
fake_socket = type("S", (), {"socket": Socket, "AF_INET": socket.AF_INET, "SOCK_DGRAM": socket.SOCK_DGRAM})
motiond.socket = fake_socket
identity = motiond.axis_map("x,y,z")
pad_map = motiond.axis_map("-y,z,-x")
errors = []


def serve():
    try:
        motiond.stream(identity, identity, pad_map, Pad())
    except Stop:
        pass
    except Exception as e:  # noqa: BLE001
        errors.append(e)


thread = threading.Thread(target=serve, daemon=True)
thread.start()
for _ in range(200):
    if ports:
        break
    threading.Event().wait(0.01)
assert bound == ["127.0.0.1"], f"the DSU server isn't on loopback only: {bound}"


def request(sock, msg_type, payload=b""):
    body = struct.pack("<I", msg_type) + payload
    sock.sendto(struct.pack("<4sHHII", b"DSUC", 1001, len(body), 0, 1) + body, ("127.0.0.1", ports[0]))


def reply(sock, want):
    """The next packet of this type, its checksum checked."""
    for _ in range(4000):
        data = sock.recv(256)
        magic, _version, length, crc, _server = struct.unpack("<4sHHII", data[:16])
        assert magic == b"DSUS" and length == len(data) - 16, data
        assert crc == zlib.crc32(data[:8] + b"\0\0\0\0" + data[12:]) & 0xffffffff, "bad checksum"
        if struct.unpack("<I", data[16:20])[0] == want:
            return data
    raise AssertionError(f"no {want:#x}")


client = real(socket.AF_INET, socket.SOCK_DGRAM)
client.settimeout(5)
try:
    request(client, 0x100000)
    assert struct.unpack("<H", reply(client, 0x100000)[20:22])[0] == 1001
    request(client, 0x100001, struct.pack("<i", 1) + b"\0")
    port = reply(client, 0x100001)
    assert port[20] == 0 and port[21] == 2 and port[22] == 2, "slot 0 isn't a connected pad with a full gyro"
    request(client, 0x100002, bytes(8))
    data = reply(client, 0x100002)
    accel = struct.unpack("<3f", data[-24:-12])
    gyro = struct.unpack("<3f", data[-12:])
    assert all(math.isclose(a, b, abs_tol=1e-4) for a, b in zip(accel, (1.0 / motiond.G, 2.0 / motiond.G, 1.0))), accel   # g
    assert all(math.isclose(a, math.degrees(b), abs_tol=1e-3) for a, b in zip(gyro, (0.1, 0.2, 0.3))), gyro                # deg/s
    # The DualSense's motion: the same samples through the pad's own axis map.
    pad_accel, pad_gyro = Pad.sent[-1]
    assert pad_accel == [-2.0, motiond.G, -1.0], pad_accel
    assert pad_gyro == [-0.2, 0.3, -0.1], pad_gyro
finally:
    done.set()
    client.close()
thread.join(5)
assert not errors, errors
print("motiond: ok")
