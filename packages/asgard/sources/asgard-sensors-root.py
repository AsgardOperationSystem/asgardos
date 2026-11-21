#!/usr/bin/env python3
"""Gyro (INP-1): builds the ADSP sensors' HexagonFS root, /storage/.config/asgard/sensors-root, from the Thor's own
Android partitions, once. Nothing of Qualcomm's ships in the image: the DSP libraries, sensor configs and this unit's
calibration are read from dsp_a, persist, and vendor and odm inside super, all mounted read-only (ro,noload: no journal
replay, so Android's partitions are never written). The DSP gets a writable copy of persist/sensors.

Runs at boot from asgard-sensors-root.service, before thor-sensorspd. Does nothing when the root is already there (a
copy made by hand is never replaced) or when Android's partitions are gone. The root appears only when complete: it's
built in <root>.new and renamed, because thor-sensorspd starts as soon as hexagonrpc.json exists."""
import contextlib
import fnmatch
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import time

ROOT = "/storage/.config/asgard/sensors-root"
PARTS = "/dev/disk/by-partlabel"
SOC0 = "/sys/devices/soc0"

# Android's liblp metadata: the primary copy of slot 0's header sits after 4 KiB reserved and two 4 KiB geometries.
LP_HEADER = 12288
LP_MAGIC = 0x414C5030
LP_LINEAR = 0

# Of vendor/lib/rfsa/adsp's 74 files (350 MB, mostly camera and NPU models), the three the working root has had since
# 2026-10-10. The sensors PD loads nothing else from there.
RFSA_KEEP = ("libDspIOProxy_skel.so", "libQ6MSFR_manager_skel.so", "libvpt_action_recognition.so")

# Where the sensors PD's paths are served from (hexagonrpcd -R <root>). From the SM8550 Xiaomi Pad 6S Pro port
# (lzxcr/arch-xiaomi-sheng), whose layout ours follows.
PATH_MAP = {"/odm": "odm", "/vendor/etc": "vendor/etc", "/vendor/dsp": "dsp", "/vendor/lib/rfsa": "vendor/lib/rfsa",
            "/vendor/firmware": "vendor/firmware", "/usr/lib/qcom": "dsp", "/dsp": "dsp", "/persist": "persist",
            "/mnt/vendor/persist": "persist", "/sys/devices/soc0": "socinfo"}

# Android's /sys/devices/soc0 on a Thor (stock firmware 20260206): the DSP reads the board from it, and mainline's soc0
# has only five of these. The same on every Thor but the serial, which comes from the running kernel.
SOCINFO = {
    "accessory_chip": "0", "audio": "0x0", "camera": "0x0", "chip_family": "0x7f", "chip_id": "QCS_KAILUA", "comp": "0x0",
    "comp1": "0x0", "display": "0x0", "display1": "0x0", "eva": "0x0", "family": "Snapdragon", "feature_code": "AC",
    "foundry_id": "1", "gpu": "0x0", "hw_platform": "HDK", "image_crm_version": "REL", "image_variant": "kalama-user",
    "image_version": "10:TKQ1.231222.001:eng.Thor.20260206.163241", "machine": "QCS_KALAMAP", "modem": "0x2", "nav": "0x0",
    "ncluster_array_offset": "0xcc", "nmodem_supported": "0x0", "nproduct_id": "0x437", "npu": "0x0", "nsp": "0x1",
    "nsubset_parts_array_offset": "0xd0", "num_clusters": "0x1", "num_subset_parts": "0x11", "pcode": "0x3",
    "platform_oem_variant": "QC", "platform_oem_variant_id": "0", "platform_subtype": "Unknown", "platform_subtype_id": "0",
    "platform_version": "65536", "pmic_die_revision": "131073", "pmic_model": "65610", "raw_device_family": "0xa",
    "raw_device_number": "0x3", "raw_id": "594", "raw_version": "2", "revision": "2.0", "select_image": "10",
    "sensors": "0x0", "sku": "QCS_KALAMAP-3-AC", "soc_id": "603", "spss": "0x0", "subset_cores": "0", "subset_parts": "8000",
    "uevent": "", "video": "0x0", "wlan": "0x0",
}


def log(msg):
    print(msg, flush=True)


def lp_partitions(super_path):
    """{name: (byte offset, byte length)} of super's non-empty logical partitions that are one linear extent on super
    itself (all of a stock Thor's). Raises ValueError if it isn't liblp metadata."""
    with open(super_path, "rb") as f:
        f.seek(LP_HEADER)
        head = f.read(128)
        magic, _major, _minor, header_size = struct.unpack_from("<IHHI", head, 0)
        if magic != LP_MAGIC:
            raise ValueError("no liblp metadata in %s" % super_path)
        tables_size, = struct.unpack_from("<I", head, 44)
        p_off, p_num, p_size, e_off, e_num, e_size = struct.unpack_from("<6I", head, 80)
        f.seek(LP_HEADER + header_size)
        tables = f.read(tables_size)
    extents = [struct.unpack_from("<QIQI", tables, e_off + i * e_size) for i in range(e_num)]
    parts = {}
    for i in range(p_num):
        name, _attrs, first, count, _group = struct.unpack_from("<36sIIII", tables, p_off + i * p_size)
        if count != 1:
            continue
        sectors, target, data, source = extents[first]
        if target == LP_LINEAR and source == 0:
            parts[name.rstrip(b"\0").decode()] = (data * 512, sectors * 512)
    return parts


def pick_slot(parts, part_dir):
    """The slot whose vendor, odm and dsp are all there, _a first."""
    for slot in ("_a", "_b"):
        if "vendor" + slot in parts and "odm" + slot in parts and os.path.exists(os.path.join(part_dir, "dsp" + slot)):
            return slot
    return None


def _ignore(_dir, names):
    return [n for n in names if n == "lost+found"]


def build(dest, src, serial):
    """Assemble the root at dest from mounted trees src = {"dsp", "persist", "vendor", "odm": dir}. Built beside dest
    and renamed into place, so a failure leaves no root behind."""
    tmp = dest + ".new"
    shutil.rmtree(tmp, ignore_errors=True)
    try:
        shutil.copytree(src["dsp"], os.path.join(tmp, "dsp"), symlinks=True, ignore=_ignore)
        shutil.copytree(os.path.join(src["vendor"], "etc/sensors"), os.path.join(tmp, "vendor/etc/sensors"), symlinks=True)
        rfsa = os.path.join(tmp, "vendor/lib/rfsa/adsp")
        os.makedirs(rfsa)
        for name in RFSA_KEEP:
            path = os.path.join(src["vendor"], "lib/rfsa/adsp", name)
            if os.path.exists(path):
                shutil.copy2(path, rfsa)
        shutil.copytree(os.path.join(src["odm"], "etc"), os.path.join(tmp, "odm/etc"), symlinks=True)
        shutil.copytree(os.path.join(src["persist"], "sensors"), os.path.join(tmp, "persist/sensors"), symlinks=True)
        os.makedirs(os.path.join(tmp, "socinfo"))
        for key, value in dict(SOCINFO, serial_number=serial).items():
            with open(os.path.join(tmp, "socinfo", key), "w") as f:
                f.write(value + "\n")   # as sysfs reads, the empty uevent too
        with open(os.path.join(tmp, "hexagonrpc.json"), "w") as f:
            json.dump({"path_mappings": [{"virtual": v, "physical": p} for v, p in PATH_MAP.items()]}, f, indent=4)
        os.rename(tmp, dest)
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise


def run(*cmd):
    return subprocess.run(cmd, check=True, capture_output=True, text=True).stdout.strip()


@contextlib.contextmanager
def mounted(part_dir, slot, parts):
    """Android's four partitions mounted read-only under a scratch dir, unmounted (and loop devices freed) after."""
    base = tempfile.mkdtemp(prefix="asgard-sensors-", dir="/run")
    mounts, loops = [], []
    try:
        super_dev = os.path.join(part_dir, "super")
        for name, dev in (("dsp", os.path.join(part_dir, "dsp" + slot)), ("persist", os.path.join(part_dir, "persist")),
                          ("vendor", None), ("odm", None)):
            if dev is None:
                offset, length = parts[name + slot]
                dev = run("losetup", "-f", "--show", "-r", "-o", str(offset), "--sizelimit", str(length), super_dev)
                loops.append(dev)
            target = os.path.join(base, name)
            os.mkdir(target)
            run("mount", "-t", "ext4", "-o", "ro,noload", dev, target)
            mounts.append(target)
        yield {name: os.path.join(base, name) for name in ("dsp", "persist", "vendor", "odm")}
    finally:
        for target in reversed(mounts):
            subprocess.run(["umount", target], capture_output=True)
        for dev in loops:
            subprocess.run(["losetup", "-d", dev], capture_output=True)
        shutil.rmtree(base, ignore_errors=True)


def main(root=ROOT, part_dir=PARTS, soc0=SOC0, wait=15):
    if os.path.exists(os.path.join(root, "hexagonrpc.json")):
        return 0
    super_dev = os.path.join(part_dir, "super")
    for _ in range(wait):           # by-partlabel links come from udev, which may still be settling at boot
        if os.path.exists(super_dev):
            break
        time.sleep(1)
    if not os.path.exists(super_dev):
        log("no Android super partition: the gyro needs sensors-root copied by hand")
        return 0
    try:
        parts = lp_partitions(super_dev)
    except (OSError, ValueError, struct.error) as e:
        log("can't read super: %s" % e)
        return 1
    slot = pick_slot(parts, part_dir)
    if not slot or not os.path.exists(os.path.join(part_dir, "persist")):
        log("Android's vendor, odm, dsp or persist partition is missing")
        return 0
    try:
        with open(os.path.join(soc0, "serial_number")) as f:
            serial = f.read().strip()
    except OSError:
        serial = ""
    try:
        os.makedirs(os.path.dirname(root), exist_ok=True)
        with mounted(part_dir, slot, parts) as src:
            build(root, src, serial)
    except (OSError, subprocess.CalledProcessError) as e:
        log("couldn't build %s: %s" % (root, getattr(e, "stderr", "") or e))
        return 1
    log("built %s from Android's partitions (slot %s)" % (root, slot))
    return 0


if __name__ == "__main__":
    sys.exit(main())
