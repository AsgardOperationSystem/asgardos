#!/usr/bin/env python3
# spec: UPD-1 UPD-5
# requires: cmd:unsquashfs file:build/target
# Image check over the update .tar in build/target. It may be older than the source: rebuild before believing a result about
# recent changes. Nothing is written to build/: the squashfs is read in place and what's extracted goes to a temp dir.
#   UPD-5, the boot entry half: the entry an update installs names a kernel and a device tree that are there and are what they
#     should be, and its layout (paths, keys, labels) is the one installed Thors boot. A change here needs a migration, and
#     then this test changes with SPEC. That the Thor's /flash matches is a device check. The .img.gz's FAT isn't opened.
#     test_update_abl.py checks UPD-5's ABL half.
#   UPD-1: the root filesystem is a squashfs, which can't be written, with mount points for /storage and /flash, and init
#     mounts it and /flash read-only. That it's so on a running Thor is a device check.
import glob
import hashlib
import os
import re
import subprocess
import sys
import tarfile
import tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
ENTRY_NAME = "asgardos.conf"
KERNEL_PATH = "/KERNEL"
DTB_PATH = "/dtbs/qcs8550-ayn-thor.dtb"
LABELS = ("boot=LABEL=ASGARDOS", "disk=LABEL=STORAGE")
problems = []


def find_tar():
    override = os.environ.get("ASGARD_IMAGE_TAR")
    if override:
        return override
    tars = glob.glob(os.path.join(ROOT, "build", "target", "*.tar"))
    if not tars:
        sys.exit("FAIL: no .tar in build/target: this test needs a built image")
    return max(tars, key=os.path.getmtime)


def md5_of(path, offset, size):
    digest = hashlib.md5()
    with open(path, "rb") as f:
        f.seek(offset)
        while size:
            chunk = f.read(min(size, 1 << 20))
            if not chunk:
                break
            digest.update(chunk)
            size -= len(chunk)
    return digest.hexdigest()


def main():
    tar_path = find_tar()
    with tarfile.open(tar_path) as tar:
        members = {m.name.split("/", 1)[-1]: m for m in tar.getmembers() if "/" in m.name}

        def read(name):
            return tar.extractfile(members[name]).read()

        def head(name, count):
            return tar.extractfile(members[name]).read(count)

        for name in ("target/KERNEL", "target/SYSTEM", "target/KERNEL.md5", "target/SYSTEM.md5",
                     f"3rdparty/bootloader/loader/entries/{ENTRY_NAME}"):
            if name not in members:
                sys.exit(f"FAIL: {name} isn't in {tar_path}")
        for name in ("KERNEL", "SYSTEM"):
            member = members[f"target/{name}"]
            expected = read(f"target/{name}.md5").split()[0].decode()
            if md5_of(tar_path, member.offset_data, member.size) != expected:
                problems.append(f"target/{name} doesn't match its checksum (SPEC UPD-5)")
        if head("target/KERNEL", 64)[56:60] != b"ARMd":
            problems.append("target/KERNEL isn't an arm64 kernel image (SPEC UPD-5)")
        system = members["target/SYSTEM"]
        if head("target/SYSTEM", 4) != b"hsqs":
            sys.exit("FAIL: target/SYSTEM isn't a squashfs: the root filesystem must be read-only (SPEC UPD-1)")
        release_entry = read(f"3rdparty/bootloader/loader/entries/{ENTRY_NAME}")
        release_dtb = members.get("3rdparty/bootloader/dtbs" + DTB_PATH[len("/dtbs"):])
        release_dtb = tar.extractfile(release_dtb).read() if release_dtb else None

    # What the update installs comes from the squashfs: update.sh copies usr/share/bootloader to /flash.
    with tempfile.TemporaryDirectory() as tmp:
        fs = ["-o", str(system.offset_data), tar_path]
        listing = subprocess.run(["unsquashfs", *fs[:2], "-d", "squashfs-root", "-ls", fs[2]],
                                 capture_output=True, text=True, errors="replace")
        if listing.returncode != 0:
            sys.exit(f"FAIL: can't read the squashfs: {listing.stderr.strip()}")
        names = {line.split("squashfs-root/", 1)[1] for line in listing.stdout.splitlines() if "squashfs-root/" in line}
        for mount in ("storage", "flash"):
            if mount not in names:
                problems.append(f"the image has no /{mount} to mount on (SPEC UPD-1)")
        dest = os.path.join(tmp, "x")
        subprocess.run(["unsquashfs", *fs[:2], "-d", dest, "-no-progress", "-q", fs[2], "usr/share/bootloader/loader",
                        "usr/share/bootloader/dtbs", "usr/share/bootloader/update.sh"], capture_output=True)
        boot = os.path.join(dest, "usr", "share", "bootloader")
        entries_dir = os.path.join(boot, "loader", "entries")
        entries = sorted(os.listdir(entries_dir)) if os.path.isdir(entries_dir) else []
        if entries != [ENTRY_NAME]:
            sys.exit(f"FAIL: the image's boot entries are {entries}, not just {ENTRY_NAME} (SPEC UPD-5)")
        with open(os.path.join(entries_dir, ENTRY_NAME), "rb") as f:
            entry_bytes = f.read()
        fields = dict(line.split(None, 1) for line in entry_bytes.decode().splitlines() if line.strip())
        if entry_bytes != release_entry:
            problems.append("the entry in SYSTEM and the one beside it in the .tar differ (SPEC UPD-5)")
        if set(fields) != {"title", "linux", "devicetree", "options"}:
            problems.append(f"the boot entry's keys changed (SPEC UPD-5): {sorted(fields)}")
        if fields.get("linux", "").strip() != KERNEL_PATH:
            problems.append(f"the boot entry's kernel is {fields.get('linux')}, not {KERNEL_PATH} (SPEC UPD-5)")
        if fields.get("devicetree", "").strip() != DTB_PATH:
            problems.append(f"the boot entry's device tree is {fields.get('devicetree')}, not {DTB_PATH} (SPEC UPD-5)")
        options = fields.get("options", "").split()
        for label in LABELS:
            if label not in options:
                problems.append(f"the boot entry lost {label} (SPEC UPD-5)")
        dtb = fields.get("devicetree", "").strip().lstrip("/")
        dtb_file = os.path.join(boot, dtb)
        if not os.path.isfile(dtb_file):
            problems.append(f"the boot entry names {dtb}, which isn't in the image's usr/share/bootloader (SPEC UPD-5)")
        else:
            with open(dtb_file, "rb") as f:
                dtb_bytes = f.read()
            if dtb_bytes[:4] != b"\xd0\x0d\xfe\xed":
                problems.append(f"{dtb} isn't a device tree blob (SPEC UPD-5)")
            if dtb_bytes != release_dtb:
                problems.append(f"{dtb} in SYSTEM and beside it in the .tar differ (SPEC UPD-5)")
        update_sh = os.path.join(boot, "update.sh")
        with open(update_sh) as f:
            copied = re.search(r"^for d in (.*); do", f.read(), re.M)
        if not copied or not {"dtbs", "loader"} <= set(copied.group(1).split()):
            problems.append("update.sh doesn't copy dtbs and loader to /flash: the entry wouldn't arrive (SPEC UPD-5)")

    # init writes the kernel to the name the entry reads, and mounts the system read-only. It's inside the kernel's
    # initramfs, so this reads the source.
    with open(os.path.join(ROOT, "packages", "sysutils", "busybox", "scripts", "init")) as f:
        init = f.read()
    if not re.search(r'^IMAGE_KERNEL="@KERNEL_NAME@"', init, re.M):
        problems.append("init no longer installs the kernel under KERNEL_NAME (SPEC UPD-5)")
    with open(os.path.join(ROOT, "config", "options")) as f:
        options_file = f.read()
    if not re.search(r'^KERNEL_NAME="\$\{KERNEL_NAME:-' + KERNEL_PATH.lstrip("/") + r'\}"', options_file, re.M):
        problems.append(f"KERNEL_NAME isn't {KERNEL_PATH.lstrip('/')}, the name the entry reads (SPEC UPD-5)")
    if not re.search(r'mount_part "/flash/\$\{IMAGE_SYSTEM\}" "/sysroot" "ro,loop"', init):
        problems.append("init doesn't mount the system read-only (SPEC UPD-1)")
    if not re.search(r'mount_part "\$boot" "/flash" "ro,noatime"', init):
        problems.append("init doesn't mount /flash read-only (SPEC UPD-1)")
    if not re.search(r'mount_part "\$disk" "/storage" "rw,noatime"', init):
        problems.append("init doesn't mount /storage read-write (SPEC UPD-1)")
    if problems:
        sys.exit("FAIL: " + "\n".join(problems))
    print("OK")


if __name__ == "__main__":
    main()
