"""Minimal Qualcomm SSC (sensors over QMI/QRTR) client: find sensor SUIDs, stream accel/gyro. Prototype."""
import socket, struct, sys, time

SNS_CLIENT_SVC = 400
QMI_REQ, QMI_RESP, QMI_IND = 0, 2, 4
MSG_CLIENT_REQ, MSG_REPORT_IND, MSG_JUMBO_IND = 0x20, 0x21, 0x22
SUID_LOOKUP = (0xabababababababab, 0xabababababababab)
SUID_REQ, SUID_EVENT = 512, 768
SENSOR_CONFIG, SENSOR_EVENT = 513, 1025


# --- protobuf (just what SSC needs) -------------------------------------------------------------------------
def varint(n):
    out = bytearray()
    while True:
        b = n & 0x7f; n >>= 7
        out.append(b | (0x80 if n else 0))
        if not n: return bytes(out)

def f_varint(field, n): return varint(field << 3) + varint(n)
def f_fixed64(field, n): return varint(field << 3 | 1) + struct.pack("<Q", n)
def f_fixed32(field, n): return varint(field << 3 | 5) + struct.pack("<I", n)
def f_float(field, x): return varint(field << 3 | 5) + struct.pack("<f", x)
def f_bytes(field, b): return varint(field << 3 | 2) + varint(len(b)) + b

def parse(buf):
    """-> list of (field, wiretype, value) ; value is int, bytes or raw 4/8 bytes."""
    out, i = [], 0
    while i < len(buf):
        key = 0; shift = 0
        while True:
            b = buf[i]; i += 1; key |= (b & 0x7f) << shift; shift += 7
            if not b & 0x80: break
        f, wt = key >> 3, key & 7
        if wt == 0:
            v = 0; shift = 0
            while True:
                b = buf[i]; i += 1; v |= (b & 0x7f) << shift; shift += 7
                if not b & 0x80: break
        elif wt == 1: v = buf[i:i + 8]; i += 8
        elif wt == 5: v = buf[i:i + 4]; i += 4
        elif wt == 2:
            n = 0; shift = 0
            while True:
                b = buf[i]; i += 1; n |= (b & 0x7f) << shift; shift += 7
                if not b & 0x80: break
            v = buf[i:i + n]; i += n
        else: raise ValueError(f"wiretype {wt}")
        out.append((f, wt, v))
    return out

def suid_msg(suid): return f_fixed64(1, suid[0]) + f_fixed64(2, suid[1])

def client_request(suid, msg_id, payload, wakeup=False):
    susp = f_varint(1, 1) + f_varint(2, 0 if wakeup else 1)          # client_proc_type APSS, delivery no-wakeup
    req = f_bytes(2, payload)                                          # sns_std_request.payload
    return f_bytes(1, suid_msg(suid)) + f_fixed32(2, msg_id) + f_bytes(3, susp) + f_bytes(4, req)


# --- QMI over QRTR --------------------------------------------------------------------------------------------
class Ssc:
    def __init__(self):
        self.s = socket.socket(socket.AF_QIPCRTR, socket.SOCK_DGRAM)
        self.s.settimeout(2)
        self.node = self.port = None
        me = self.s.getsockname()
        self.s.sendto(struct.pack("<5I", 10, SNS_CLIENT_SVC, 0, 0, 0), (me[0], 0xfffffffe))   # NEW_LOOKUP
        while True:
            cmd, svc, vi, node, port = struct.unpack("<5I", self.s.recvfrom(64)[0][:20])
            if cmd == 4 and svc == SNS_CLIENT_SVC and node:
                self.node, self.port = node, port
                break
            if cmd == 4 and node == 0: break
        if self.node is None: raise SystemExit("SSC service 400 not found")
        self.txn = 1

    def send(self, msg_id, tlvs):
        body = b"".join(struct.pack("<BH", t, len(v)) + v for t, v in tlvs)
        hdr = struct.pack("<BHHH", QMI_REQ, self.txn, msg_id, len(body))
        self.txn += 1
        self.s.sendto(hdr + body, (self.node, self.port))

    def request(self, suid, msg_id, payload):
        pb = client_request(suid, msg_id, payload)
        self.send(MSG_CLIENT_REQ, [(0x01, struct.pack("<H", len(pb)) + pb), (0x10, b"\x01")])  # payload, jumbo ok

    def recv(self):
        data = self.s.recv(65536)
        typ, txn, msg, ln = struct.unpack("<BHHH", data[:7])
        tlvs, i = {}, 7
        while i < 7 + ln:
            t, l = struct.unpack("<BH", data[i:i + 3]); tlvs[t] = data[i + 3:i + 3 + l]; i += 3 + l
        return typ, msg, tlvs

    def events(self, tlvs):
        """report indication -> (suid, [(msg_id, timestamp, payload)])"""
        raw = tlvs.get(0x02) or tlvs.get(0x01)
        if raw is None: return None, []
        if len(raw) >= 2 and struct.unpack("<H", raw[:2])[0] == len(raw) - 2: raw = raw[2:]
        suid, evs = None, []
        for f, wt, v in parse(raw):
            if f == 1: s = {ff: vv for ff, _, vv in parse(v)}; suid = (struct.unpack("<Q", s[1])[0], struct.unpack("<Q", s[2])[0])
            if f == 2:
                e = {ff: vv for ff, _, vv in parse(v)}
                evs.append((struct.unpack("<I", e[1])[0], struct.unpack("<Q", e[2])[0] if 2 in e else 0, e.get(3, b"")))
        return suid, evs


def lookup(ssc, data_type, wait=3):
    ssc.request(SUID_LOOKUP, SUID_REQ, f_bytes(1, data_type.encode()) + f_varint(3, 1))   # default_only
    found, end = [], time.time() + wait
    while time.time() < end:
        try: typ, msg, tlvs = ssc.recv()
        except socket.timeout: break
        if typ == QMI_IND:
            _, evs = ssc.events(tlvs)
            for mid, ts, pl in evs:
                if mid == SUID_EVENT:
                    for f, wt, v in parse(pl):
                        if f == 2:
                            s = {ff: vv for ff, _, vv in parse(v)}
                            found.append((struct.unpack("<Q", s[1])[0], struct.unpack("<Q", s[2])[0]))
            if found: break
        elif typ == QMI_RESP and msg == MSG_CLIENT_REQ:
            res = tlvs.get(0x02, b"")
            if res and struct.unpack("<HH", res[:4]) != (0, 0): print("request error", res.hex(), file=sys.stderr)
    return found


if __name__ == "__main__":
    ssc = Ssc()
    print("SSC at node", ssc.node, "port", ssc.port)
    for t in sys.argv[1:] or ["accel", "gyro"]:
        print(t, [f"{lo:016x}:{hi:016x}" for lo, hi in lookup(ssc, t)])


def stream(ssc, suids, rate=100.0):
    """suids: {name: suid}. Yields (name, timestamp, [floats])."""
    names = {v: k for k, v in suids.items()}
    for suid in suids.values():
        ssc.request(suid, SENSOR_CONFIG, f_float(1, rate))
    while True:
        try: typ, msg, tlvs = ssc.recv()
        except socket.timeout: continue
        if typ != QMI_IND: continue
        suid, evs = ssc.events(tlvs)
        for mid, ts, pl in evs:
            if mid == SENSOR_EVENT:
                vals = [struct.unpack("<f", v)[0] for f, wt, v in parse(pl) if f == 1 and wt == 5]
                packed = [v for f, wt, v in parse(pl) if f == 1 and wt == 2]          # packed repeated float
                for p in packed: vals += list(struct.unpack(f"<{len(p) // 4}f", p))
                yield names.get(suid, "?"), ts, vals
