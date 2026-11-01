#!/usr/bin/env python3
# spec: DEV-5 DEV-10 DEV-16 DEV-18
# requires: cmd:grep cmd:git file:build/AsgardOS-SM8550.aarch64/image/system
# Image check, read-only over the tree the squashfs is made from. It may be older than the source: rebuild before believing
# a result about recent changes. Parts:
#   DEV-5   the generated es_systems.cfg and the other interfaces are in the image.
#   DEV-10  no personal paths in any file, binaries included: the owner's home and user name, the LAN.
#   DEV-16  no Wi-Fi or SSH keys or asgard.yml, by name; no owner's name or email in any file. A unit's calibration and Android
#           blobs have no fixed form: human check.
#   DEV-18  test files don't ship: nothing from the tree's test_*, no test scripts or ROMs. (This is TEST-9 too; test.sh
#           only takes SPEC.md's IDs.)
import os
import re
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
IMAGE = os.environ.get("ASGARD_IMAGE_SYSTEM",
                       os.path.join(ROOT, "build", "AsgardOS-SM8550.aarch64", "image", "system"))
PERSONAL = [r"asgardos-owner", r"lan\.example", r"192\.168\.50\.", r"/mnt/(ConfigDisk|ServerDisk|SmallDisk)", r"Projects/asgard"]
PERSONAL_ALLOWED = {
    "etc/os-release",  # SPEC 16, DEV-15: distribution/options' URLs
    "usr/bin/asgard-home",  # SPEC 16, DEV-15: its RetroAchievements user agent
    "etc/avahi/avahi-daemon.conf",  # avahi's own example, in a comment, happens to use this subnet
}
SECRET_NAMES = re.compile(r"^(authorized_keys|id_(rsa|dsa|ecdsa|ed25519)|asgard\.yml|.*\.psk|.*\.apk)$")
SECRET_DIRS = ("usr/config/iwd", "usr/config/ssh")
ROM = re.compile(r"\.(nes|sfc|smc|gb|gbc|gba|nds|n64|z64|sms|gg|md|bin|iso|cue|chd|pce|zip|7z)$", re.I)
# Other projects' files that happen to be called test_*: libretro's core list and KDE's cmake modules. Reported: sdljoytest's
# test_gamepad_SDL2 is a real gamepad tester the image ships on purpose (packages/apps/sdljoytest).
THIRD_PARTY_TEST_NAMES = {
    "usr/bin/test_gamepad_SDL2",
    "usr/lib/libretro/test_libretro.info", "usr/lib/libretro/test_netplay_libretro.info",
    "usr/lib32/libretro/test_libretro.info", "usr/lib32/libretro/test_netplay_libretro.info",
    "usr/share/ECM/test-modules/test_execute_and_compare.cmake",
}
INTERFACES = ("usr/bin/runemu.sh", "usr/config/emulationstation/es_systems.cfg", "usr/share/asgard/es_features.cfg",
              "usr/config/system/configs/system.cfg")
problems = []


def main():
    tree_tests = {n for n in os.listdir(os.path.dirname(os.path.abspath(__file__))) if n.startswith("test_")}
    if len(tree_tests) < 2:
        sys.exit("FAIL: found no test_* beside this one: the scan is broken")
    count = 0
    for folder, dirs, files in os.walk(IMAGE):
        relative = os.path.relpath(folder, IMAGE)
        for name in dirs + files:
            path = os.path.normpath(os.path.join(relative, name))
            count += 1
            if name in files and SECRET_NAMES.match(name):
                problems.append(f"{path} is in the image (SPEC DEV-16)")
            if path in SECRET_DIRS:
                problems.append(f"{path} is in the image: something baked in keys (SPEC DEV-16)")
            if name in tree_tests:
                problems.append(f"{path} is one of the tree's test files (SPEC DEV-18)")
            elif name.startswith("test_") and path not in THIRD_PARTY_TEST_NAMES:
                problems.append(f"{path} is a test file in the image (SPEC DEV-18)")
            if name in files and ROM.search(name) and re.search(r"(^|[-_. ])test", name, re.I):
                problems.append(f"{path} looks like a test ROM (SPEC DEV-18)")
    if count < 1000:
        sys.exit(f"FAIL: {IMAGE} holds only {count} files: not an image")

    for path in INTERFACES:
        if not os.path.exists(os.path.join(IMAGE, path)):
            problems.append(f"{path} isn't in the image (SPEC DEV-5)")
    functions = os.path.join(IMAGE, "etc", "profile.d", "001-functions")
    if not os.path.exists(functions) or "set_kill()" not in open(functions, errors="replace").read():
        problems.append("set_kill isn't in the image (SPEC DEV-5)")

    patterns = list(PERSONAL)
    home = os.path.expanduser("~")
    if home.startswith("/home/"):
        patterns.append(re.escape(home))
    email = subprocess.run(["git", "-C", ROOT, "log", "-1", "--format=%ce"], capture_output=True, text=True).stdout.strip()
    if email:
        patterns.append(re.escape(email))
    proc = subprocess.run(["grep", "-rlaE", "-e", "|".join(patterns), "."], cwd=IMAGE, capture_output=True, text=True,
                          errors="replace")
    if proc.returncode > 1:
        # grep exits 2 for a dangling link too, and still searches the rest: only an unreadable file is a hole in the scan.
        unreadable = [line for line in proc.stderr.splitlines() if "No such file" not in line]
        if unreadable:
            problems.append(f"the scan couldn't read everything: {unreadable[:3]}")
    for path in proc.stdout.splitlines():
        path = os.path.normpath(path)
        if path not in PERSONAL_ALLOWED:
            problems.append(f"{path} holds a personal path or name (SPEC DEV-10, DEV-16)")
    for path in PERSONAL_ALLOWED:
        if not os.path.exists(os.path.join(IMAGE, path)):
            problems.append(f"{path} is gone: drop it from this test's list")
    if problems:
        sys.exit("FAIL: " + "\n".join(problems))
    print("OK")


if __name__ == "__main__":
    main()
