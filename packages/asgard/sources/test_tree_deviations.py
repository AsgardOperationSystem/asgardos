#!/usr/bin/env python3
# spec: DEV-2 DEV-9 DEV-11 DEV-15 DEV-16
# requires: cmd:git
# Tree check: nothing new. Each rule below has deviations today: the ones SPEC's known gaps list, and some found while writing
# this that it doesn't list yet. They're allowed here by file, and only those, so a new one fails. This doesn't say they're
# fine: the test_gap_* files assert each rule outright and fail until the deviation is gone. When one is fixed, its entry
# goes from here with its gap file. Scope:
#   DEV-2   other SoCs named in the tree, and quirks for other devices. Other handhelds named in prose aren't searched.
#   DEV-9   downloads from ROCKNIX's GitHub. The container's digest is test_build_env.py.
#   DEV-11  build paths default into build/, and the tree root holds nothing a build left there. A write elsewhere that
#           isn't at the root shows only if it changes a tracked file.
#   DEV-15  LAN hosts and this owner's paths, in anything but the docs.
#   DEV-16  key and credential files and text. A unit's calibration has no fixed form, so that part is a human check; what
#           actually went into an image is test_image_contents.py.
import os
import re
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
NOT_CODE = [":!*.md", ":!docs", ":!packages/asgard/sources/test_*", ":!test-device.sh", ":!tools/test"]
problems = []

# DEV-15. SPEC 16: the Makefile's build image (the URLs moved to GitHub 2026-11-20).
LAN = r"asgardos-owner|192\.168\.50\.|/mnt/(ConfigDisk|ServerDisk|SmallDisk)|Projects/asgard"
# Private host names stay out of the public tree: one regex per line in the git-ignored personal-patterns.local.
LOCAL_PATTERNS = os.path.join(ROOT, "personal-patterns.local")
if os.path.exists(LOCAL_PATTERNS):
    LAN = "|".join([LAN] + [l.strip() for l in open(LOCAL_PATTERNS) if l.strip() and not l.startswith("#")])
LAN_ALLOWED = {
    "Makefile": r"^docker-%: DOCKER_IMAGE := ",
    "test-device.sh": r"^#",  # not a build input: its usage line
}

# DEV-9. SPEC 16 and docs/plans/rocknix-sources.md: ten packages and DISTRO_MIRROR.
ROCKNIX_DOWNLOADS = {
    "packages/apps/rocknix-hotkey/package.mk", "packages/apps/commander/package.mk",
    "packages/apps/jstest-sdl/package.mk", "packages/linux-firmware/extra-firmware/package.mk",
    "packages/tools/sound/soundfont-generaluser/package.mk", "packages/emulators/standalone/aethersx2-sa/package.mk",
    "packages/emulators/standalone/drastic-sa/package.mk", "packages/compress/cabextract/package.mk",
    "packages/apps/portmaster/package.mk", "packages/emulators/libretro/idtech-lr/package.mk",
    "distribution/options",
    # Not in SPEC 16's count: these three download through PKG_SITE. Reported.
    "packages/ui/emulationstation/package.mk", "packages/textproc/textviewer/package.mk",
    "packages/linux-drivers/rocknix-joypad/package.mk",
}

# DEV-11. Git-ignored things a person or a tool outside the build keeps at the root, and what a build leaves there.
ROOT_LOCAL = {"build", "thor", "asgard.yml", "CLAUDE.local.md", "personal-patterns.local", ".git"}
ROOT_BUILD_LEFTOVERS = {
    ".cache", ".config",  # SPEC 16: a Go package's build
    "target",  # SPEC 16: scripts/image's RELEASE_DIR, empty after a build. Reported.
}
# SPEC 16: the emulators package regenerates this tracked file.
WRITES_ROOT = {"distribution/options": r'SYSDOCROOT|SYSDOC='}

# DEV-16: test_local_secrets.sh holds the rule. test_build_env.py checks build.sh's guard.
LOCAL_SECRETS = r"LOCAL_WIFI_|LOCAL_SSH_KEYS_FILE|usr/config/iwd|usr/config/ssh/authorized_keys"
LOCAL_SECRETS_ALLOWED = {
    "build.sh",
    # These copy what an image holds there onto /storage at boot.
    "packages/network/openssh/daemons/001-ssh",
    "packages/sysutils/systemd/scripts/userconfig-setup",
}
KEY_FILES = r"(^|/)(authorized_keys|id_(rsa|dsa|ecdsa|ed25519)(\.pub)?|asgard\.yml|[^/]*\.psk|[^/]*\.keystore)$"
KEY_TEXT = r"BEGIN [A-Z ]*PRIVATE KEY|ssh-(rsa|ed25519) AAAA"
KEY_TEXT_ALLOWED = {"asgard.yml.example", "packages/asgard/sources/asgard_config.py"}  # placeholder keys, as documentation

# DEV-2. SPEC 16 lists device/config.xml and device/filesystem/ for other handhelds; the SoC list below isn't in it. Reported.
OTHER_SOCS = r"RK[0-9]{4}[A-Z]*|S922X|H700|SM8250|SM8650|SM8750|SM6115|SM4450|RPi[0-9]?"
OTHER_SOCS_FILES = {
    "Makefile", "distribution/bootloader/mkimage", "packages/apps/gamecontrollerdb/config/gamecontrollerdb.txt",
    "packages/apps/oga_controls/package.mk", "packages/apps/qterminal/scripts/qterminal.sh",
    "packages/asgardos/profile.d/101-gpu-functions", "packages/asgardos/sources/scripts/asgardos-fake-suspend",
    "packages/asgardos/sources/scripts/asgardos-memory-manager", "packages/asgardos/sources/scripts/handle-hdmi-hotplug",
    "packages/asgardos/sources/scripts/installtointernal", "packages/asgardos/sources/scripts/updateabl",
    "packages/asgardos/sources/scripts/usbgadget",
    "packages/audio/alsa-ucm-conf/sources/ucm2/Qualcomm/sm6115/HiFi-MangmiAirX.conf",
    "packages/audio/alsa-ucm-conf/sources/ucm2/Qualcomm/sm6115/HiFi-MangmiAirY.conf",
    "packages/audio/alsa-ucm-conf/sources/ucm2/Qualcomm/sm6125/HiFi-RetroidPocketDuoLite.conf",
    "packages/audio/alsa-ucm-conf/sources/ucm2/Qualcomm/sm8250/AYN-Thor-Lite-HiFi.conf",
    "packages/audio/alsa-ucm-conf/sources/ucm2/Qualcomm/sm8250/AYN-Thor-Lite.conf",
    "packages/audio/alsa-ucm-conf/sources/ucm2/Rockchip/rockchip,es8388-codec/HiFi.conf",
    "packages/devel/glibc/package.mk", "packages/emulators/libretro/retroarch/retroarch-joypads/gamepads/H700 Gamepad.cfg",
    "packages/emulators/standalone/armsx2-sa/package.mk", "packages/emulators/standalone/azahar-sa/scripts/start_azahar.sh",
    "packages/emulators/standalone/mednafen/scripts/start_mednafen.sh",
    "packages/emulators/standalone/melonds-sa/scripts/start_melonds.sh",
    "packages/emulators/standalone/yabasanshiro-sa/scripts/start_yabasanshiro.sh",
    "packages/hardware/quirks/devices/AYANEO Pocket S2/400-set_gpu_overclock",
    "packages/hardware/quirks/devices/Anbernic RG DS/bin/battery_led_status",
    "packages/hardware/quirks/system.d/volume-fixup.service", "packages/multimedia/gstreamer/gst-plugins-good/package.mk",
    "packages/sysutils/busybox/scripts/init", "packages/sysutils/system-utils/sources/config/fancontrol.conf",
    "packages/sysutils/system-utils/sources/scripts/hdmi_sense", "packages/sysutils/system-utils/sources/scripts/output_monitor",
    "packages/sysutils/systemd/scripts/systemd-machine-id-setup", "packages/sysutils/udevil/package.mk",
    "packages/tools/gamepadcalibration/scripts/GPcal.sh", "packages/ui/emulationstation/config/common/es_input.cfg",
    "packages/ui/emulationstation/package.mk", "packages/virtual/emulators/sources/Start MelonDS.sh",
    "scripts/create_addon", "scripts/create_docker_package", "scripts/uboot_helper", "tools/imgburn.sh", "tools/repo-tool",
}
OTHER_SOC_DIRS = r"(^|/)(RK[0-9]{4}[A-Z]*|S922X|H700|SM8250|SM8650|SM8750|SM6115|SM4450|RPi[0-9]?)/"
OTHER_SOC_DIRS_ALLOWED = (
    "packages/emulators/standalone/mupen64plus-sa/", "packages/emulators/standalone/melonds-sa/config/",
    "packages/emulators/standalone/duckstation-sa/config/", "packages/emulators/standalone/azahar-sa/config/",
    "packages/emulators/standalone/aethersx2-sa/config/", "packages/emulators/standalone/ppsspp-sa/patches/",
    "packages/hardware/quirks/platforms/SM8750/", "packages/apps/mangohud/patches/SM8750/",
)
OTHER_QUIRKS_COUNT = 88  # packages/hardware/quirks/devices/, the Thor's own included: new ones raise it


def git(*args):
    proc = subprocess.run(["git", "-C", ROOT, *args], capture_output=True, text=True, errors="replace")
    if proc.returncode > 1:
        sys.exit(f"FAIL: git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout


def grep(pattern, *paths):
    """(path, line text) of each match, in tracked and new files."""
    out = git("grep", "--untracked", "-z", "-nIE", pattern, "--", *(paths or ["."]), *NOT_CODE)
    hits = []
    for line in out.splitlines():
        path, _, text = line.split("\0", 2)
        hits.append((path, text))
    return hits


def tree_files():
    return git("ls-files", "--cached", "--others", "--exclude-standard").splitlines()


def check_lan_hosts():
    """DEV-15"""
    if not grep(r"^docker-%: DOCKER_IMAGE := ", "Makefile"):   # a scan that finds nothing proves nothing
        problems.append("the scan didn't find what it knows is there (DEV-15)")
    hits = grep(LAN)
    for path, text in hits:
        allowed = LAN_ALLOWED.get(path)
        if not allowed or not re.search(allowed, text):
            problems.append(f"a LAN host or personal path (DEV-15): {path}: {text.strip()[:120]}")


def check_rocknix_downloads(files):
    """DEV-9"""
    found = set()
    with open(os.path.join(ROOT, "distribution/options")) as f:
        if re.search(r'DISTRO_MIRROR="[^"]*github\.com/ROCKNIX', f.read()):
            found.add("distribution/options")
    for path in files:
        if not (path.startswith("packages/") and path.endswith("/package.mk")):
            continue
        with open(os.path.join(ROOT, path), errors="replace") as f:
            text = f.read()
        site = re.search(r'^PKG_SITE="([^"]*)"', text, re.M)
        site = site.group(1) if site else ""
        for name, value in re.findall(r'^\s*([A-Z_]*(?:URL|SHAREWARE))="([^"]*)"', text, re.M):
            if "github.com/ROCKNIX" in value.replace("${PKG_SITE}", site):
                found.add(path)
    if "distribution/options" not in found:
        problems.append("the scan didn't find DISTRO_MIRROR: it's broken, or remove the entry and its gap (DEV-9)")
    extra = found - ROCKNIX_DOWNLOADS
    if extra:
        problems.append(f"new downloads from ROCKNIX's GitHub (DEV-9): {sorted(extra)}")


def check_build_output():
    """DEV-11"""
    with open(os.path.join(ROOT, "config/path")) as f:
        paths = f.read()
    for name, default in (("SOURCES", "SOURCES_DIR"), ("BUILD_ROOT", "BUILD_DIR"), ("TARGET_IMG", "TARGET_DIR")):
        if not re.search(rf"^\s*{name}=\$\{{{default}:-\$ROOT/build(/\w+)?\}}", paths, re.M):
            problems.append(f"{name} doesn't default into build/ (DEV-11)")
    tracked = {f.split("/", 1)[0] for f in tree_files()}
    for entry in sorted(set(os.listdir(ROOT)) - tracked - ROOT_LOCAL - ROOT_BUILD_LEFTOVERS):
        problems.append(f"{entry} at the tree root isn't part of the tree: a build's output? (DEV-11)")
    for path, text in grep(r"\$\{?ROOT\}?/docs|SYSDOCROOT=", "scripts", "config", "distribution", "packages"):
        if path not in WRITES_ROOT:
            problems.append(f"writes into docs/ (DEV-11): {path}: {text.strip()[:120]}")


def check_nothing_personal(files):
    """DEV-16"""
    named = [f for f in files if re.search(KEY_FILES, f)]
    if named:
        problems.append(f"key or personal config files in the tree (DEV-16): {named}")
    for path, _ in grep(KEY_TEXT):
        if path not in KEY_TEXT_ALLOWED:
            problems.append(f"a key in the tree (DEV-16): {path}")
    for path, text in grep(LOCAL_SECRETS):
        if path not in LOCAL_SECRETS_ALLOWED:
            problems.append(f"a new way to bake secrets into an image (DEV-16): {path}: {text.strip()[:120]}")
    with open(os.path.join(ROOT, ".gitignore")) as f:
        ignored = f.read().split()
    for entry in ("asgard.yml", "/thor/"):
        if entry not in ignored:
            problems.append(f"{entry} isn't git-ignored (DEV-16)")


def check_other_devices(files):
    """DEV-2"""
    named = {path for path, _ in grep(rf"\b({OTHER_SOCS})\b", ".", ":!*.patch", ":!packages/security/openssl/cert/cacert.pem")}
    named -= {path for path in named if path.startswith(("device/config.xml", "device/filesystem/"))}
    if not named & OTHER_SOCS_FILES:
        problems.append("the scan found none of what it knows is there (DEV-2)")
    for path in sorted(named - OTHER_SOCS_FILES):
        problems.append(f"a new branch or file for another device (DEV-2): {path}")
    for path in files:
        if re.search(OTHER_SOC_DIRS, path) and not path.startswith(OTHER_SOC_DIRS_ALLOWED):
            problems.append(f"a new directory for another device (DEV-2): {path}")
    quirks = {f.split("/")[4] for f in files if f.startswith("packages/hardware/quirks/devices/")}
    if len(quirks) > OTHER_QUIRKS_COUNT:
        problems.append(f"new device quirks (DEV-2): {len(quirks)} devices, was {OTHER_QUIRKS_COUNT}")


def main():
    files = tree_files()
    check_lan_hosts()
    check_rocknix_downloads(files)
    check_build_output()
    check_nothing_personal(files)
    check_other_devices(files)
    if problems:
        sys.exit("FAIL: " + "\n".join(problems))
    print("OK")


if __name__ == "__main__":
    main()
