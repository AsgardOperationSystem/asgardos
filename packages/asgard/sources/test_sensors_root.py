#!/usr/bin/env python3
# spec: INP-1 CFG-7
# requires: cmd:python3
"""asgard-sensors-root.py on fakes: reading super's liblp metadata (a synthetic image laid out as Android writes it), the
slot choice, the root it assembles from mounted trees, and when it leaves things alone. Mounting the real partitions
is the device check."""
import importlib.util
import json
import os
import struct
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location("sensors_root", os.path.join(HERE, "asgard-sensors-root.py"))
sr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sr)
T = tempfile.mkdtemp()


def write(path, text=""):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)


def read(path):
    with open(path) as f:
        return f.read()


def fake_super(path, partitions):
    """A super image with slot 0's metadata where liblp puts it. partitions: [(name, [(sectors, target, data, source)])]."""
    extents, entries = b"", b""
    for name, exts in partitions:
        first = len(extents) // 24
        for e in exts:
            extents += struct.pack("<QIQI", *e)
        entries += struct.pack("<36sIIII", name.encode(), 0, first, len(exts), 0)
    header_size = 128
    tables = entries + extents
    head = struct.pack("<IHHI", sr.LP_MAGIC, 10, 2, header_size) + b"\0" * 32 + struct.pack("<I", len(tables)) + b"\0" * 32
    head += struct.pack("<6I", 0, len(partitions), 52, len(entries), len(extents) // 24, 24)
    head = head.ljust(header_size, b"\0")
    with open(path, "wb") as f:
        f.write(b"\0" * sr.LP_HEADER + head + tables)


# ---- liblp: one linear extent on super each, empty and odd ones left out, and sectors become bytes
sup = os.path.join(T, "super")
fake_super(sup, [("odm_a", [(2048, 0, 4096, 0)]), ("odm_b", []), ("vendor_a", [(8192, 0, 10240, 0)]),
                 ("split_a", [(8, 0, 1, 0), (8, 0, 9, 0)]), ("zero_a", [(8, 1, 0, 0)]), ("other_a", [(8, 0, 2, 1)])])
parts = sr.lp_partitions(sup)
assert parts == {"odm_a": (4096 * 512, 2048 * 512), "vendor_a": (10240 * 512, 8192 * 512)}, parts
write(os.path.join(T, "notsuper"), "x" * 20000)
try:
    sr.lp_partitions(os.path.join(T, "notsuper"))
    raise AssertionError("read metadata from a file that has none")
except ValueError:
    pass

# ---- slot: the one whose vendor, odm and dsp are all there, _a first
pd = os.path.join(T, "by-partlabel")
write(os.path.join(pd, "dsp_b"))
assert sr.pick_slot({"vendor_a": 1, "odm_a": 1, "vendor_b": 1, "odm_b": 1}, pd) == "_b"   # no dsp_a
write(os.path.join(pd, "dsp_a"))
assert sr.pick_slot({"vendor_a": 1, "odm_a": 1, "vendor_b": 1, "odm_b": 1}, pd) == "_a"
assert sr.pick_slot({"vendor_a": 1}, pd) is None

# ---- the root, from mounted trees
src = {k: os.path.join(T, "src", k) for k in ("dsp", "persist", "vendor", "odm")}
write(os.path.join(src["dsp"], "adsp/sensors.mbn"), "dsp")
os.makedirs(os.path.join(src["dsp"], "lost+found"))
write(os.path.join(src["vendor"], "etc/sensors/config/sns_gyro_cal.json"), "{}")
write(os.path.join(src["vendor"], "etc/other.conf"), "not for the DSP")
for name in sr.RFSA_KEEP + ("libvpp_frc.so", "bm3a68v08s11n29.bin"):
    write(os.path.join(src["vendor"], "lib/rfsa/adsp", name), name)
write(os.path.join(src["odm"], "etc/build.prop"), "odm")
write(os.path.join(src["persist"], "sensors/registry/registry/sns_reg_config"), "calibration")
write(os.path.join(src["persist"], "other/secret"), "not for the DSP")
root = os.path.join(T, "storage/.config/asgard/sensors-root")
os.makedirs(os.path.dirname(root))
sr.build(root, src, "1234567890")
assert read(os.path.join(root, "dsp/adsp/sensors.mbn")) == "dsp"
assert not os.path.exists(os.path.join(root, "dsp/lost+found"))
assert os.path.exists(os.path.join(root, "vendor/etc/sensors/config/sns_gyro_cal.json"))
assert not os.path.exists(os.path.join(root, "vendor/etc/other.conf"))
assert sorted(os.listdir(os.path.join(root, "vendor/lib/rfsa/adsp"))) == sorted(sr.RFSA_KEEP)   # no camera/NPU models
assert read(os.path.join(root, "odm/etc/build.prop")) == "odm"
assert read(os.path.join(root, "persist/sensors/registry/registry/sns_reg_config")) == "calibration"
assert not os.path.exists(os.path.join(root, "persist/other"))
assert read(os.path.join(root, "socinfo/serial_number")) == "1234567890\n"     # this unit's, from the kernel
assert read(os.path.join(root, "socinfo/hw_platform")) == "HDK\n"
assert read(os.path.join(root, "socinfo/uevent")) == "\n"                      # as sysfs reads it
maps = {m["virtual"]: m["physical"] for m in json.load(open(os.path.join(root, "hexagonrpc.json")))["path_mappings"]}
assert maps["/mnt/vendor/persist"] == "persist" and maps["/sys/devices/soc0"] == "socinfo" and maps["/vendor/dsp"] == "dsp"
assert not os.path.exists(root + ".new")
# the persist copy is writable (the DSP rewrites its registry): Android's own partition is mounted read-only
assert os.access(os.path.join(root, "persist/sensors/registry/registry/sns_reg_config"), os.W_OK)

# ---- a failure leaves no root behind, so thor-sensorspd never starts on half a tree
broken = dict(src, odm=os.path.join(T, "missing"))
root2 = os.path.join(T, "root2")
try:
    sr.build(root2, broken, "1")
    raise AssertionError("built from a missing odm")
except OSError:
    pass
assert not os.path.exists(root2) and not os.path.exists(root2 + ".new")

# ---- main leaves things alone: a root already there (one copied by hand) is never touched, and no Android is no error
hand = os.path.join(T, "hand")
write(os.path.join(hand, "hexagonrpc.json"), "mine")
assert sr.main(root=hand, part_dir=os.path.join(T, "nowhere"), wait=0) == 0
assert read(os.path.join(hand, "hexagonrpc.json")) == "mine"
assert sr.main(root=os.path.join(T, "none"), part_dir=os.path.join(T, "nowhere"), wait=0) == 0
assert not os.path.exists(os.path.join(T, "none"))
write(os.path.join(pd, "super"), "x" * 20000)                                   # super, but not liblp: an error, no root
assert sr.main(root=os.path.join(T, "bad"), part_dir=pd, wait=0) == 1 and not os.path.exists(os.path.join(T, "bad"))

# ---- the units: the builder runs before the sensors service, once, and the service waits for it
unit = read(os.path.join(HERE, "..", "system.d", "asgard-sensors-root.service"))
assert "ConditionPathExists=!/storage/.config/asgard/sensors-root/hexagonrpc.json" in unit
assert "Before=thor-sensorspd.service" in unit and "Type=oneshot" in unit
pd_unit = read(os.path.join(HERE, "..", "system.d", "thor-sensorspd.service"))
assert "After=asgard-sensors-root.service" in pd_unit
assert "asgard-sensors-root" in read(os.path.join(HERE, "..", "package.mk"))   # enabled
print("ok")
