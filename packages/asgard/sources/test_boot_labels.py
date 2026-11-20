#!/usr/bin/env python3
# spec: UPD-8
# requires: cmd:bash cmd:sed cmd:grep cmd:tr
# A card and an internal install never mount each other's partitions. The SD image labels its own (IMAGE_* in
# distribution/options), the installed ones stay ASGARDOS/STORAGE, and nothing that writes a boot entry mixes them:
#   - mkimage_abl (distribution/bootloader/mkimage) puts the card's labels into the card's copy of the entry. Run here
#     with mcopy faked; that the built .img.gz carries them is a device check (flash a card, read its labels).
#   - update.sh keeps the boot=/disk= the device boots with: run against a fake /flash for a card, an internal install
#     and a hand-edited entry.
#   - installtointernal's half (the copied entry names ASGARDOS/STORAGE) is in test_install_to_internal.py.
# On 2026-11-20 a card flashed with the release image booted the internal install's partitions: both carried
# ASGARDOS/STORAGE and init took the first match.
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
problems = []

SHIPPED = ("title      AsgardOS\nlinux      /KERNEL\ndevicetree /dtbs/qcs8550-ayn-thor.dtb\n"
           "options    boot=LABEL=ASGARDOS disk=LABEL=STORAGE quiet rootwait new_option=1\n")


def options_value(name):
    text = open(os.path.join(ROOT, "distribution", "options")).read()
    m = re.search(rf'^\s*{name}="([^"]*)"', text, re.M)
    if not m:
        sys.exit(f"FAIL: {name} isn't set in distribution/options")
    return m.group(1)


def entry_options(text):
    line = next((l for l in text.splitlines() if l.startswith("options")), "")
    return line.split()[1:]


def check_labels():
    boot, disk = options_value("DISTRO_BOOTLABEL"), options_value("DISTRO_DISKLABEL")
    card_boot, card_disk = options_value("IMAGE_BOOTLABEL"), options_value("IMAGE_DISKLABEL")
    if (boot, disk) != ("ASGARDOS", "STORAGE"):
        problems.append(f"the installed labels are {boot}/{disk}: installed Thors boot ASGARDOS/STORAGE (UPD-5)")
    if len({boot, disk, card_boot, card_disk}) != 4:
        problems.append(f"the card's labels {card_boot}/{card_disk} clash with the installed {boot}/{disk} (UPD-8)")
    if len(card_boot) > 11 or not re.fullmatch(r"[A-Z0-9_]+", card_boot):
        problems.append(f"{card_boot} isn't a FAT label (11 upper-case characters at most)")
    if len(card_disk) > 16:
        problems.append(f"{card_disk} is longer than an ext4 label (16)")
    return card_boot, card_disk


def check_mkimage(card_boot, card_disk):
    mkimage = open(os.path.join(ROOT, "scripts", "mkimage")).read()
    if 'mformat -i "${IMG_TMP}/part1.fat" -v "${IMAGE_BOOTLABEL}"' not in mkimage:
        problems.append("mkimage doesn't format the card's boot partition with IMAGE_BOOTLABEL (UPD-8)")
    if 'tune2fs -L "${IMAGE_DISKLABEL}"' not in mkimage:
        problems.append("mkimage doesn't label the card's storage partition IMAGE_DISKLABEL (UPD-8)")
    image = open(os.path.join(ROOT, "scripts", "image")).read()
    for name in ("IMAGE_BOOTLABEL", "IMAGE_DISKLABEL"):
        if f'{name}="${{{name}}}"' not in image:
            problems.append(f"scripts/image doesn't pass {name} to mkimage, which runs with a clean env (UPD-8)")

    # The real mkimage_abl, with mcopy writing into a directory instead of a FAT image.
    hook = open(os.path.join(ROOT, "distribution", "bootloader", "mkimage")).read()
    m = re.search(r"^mkimage_abl\(\) \{\n.*?^\}\n", hook, re.M | re.S)
    if not m:
        problems.append("distribution/bootloader/mkimage has no mkimage_abl")
        return
    with tempfile.TemporaryDirectory() as t:
        release, fat, img_tmp = f"{t}/release", f"{t}/fat", f"{t}/img"
        for d in (f"{release}/3rdparty/bootloader/loader/entries", f"{release}/3rdparty/bootloader/dtbs", fat, img_tmp):
            os.makedirs(d)
        open(f"{release}/3rdparty/bootloader/loader/entries/asgardos.conf", "w").write(SHIPPED)
        fake_mcopy = f'''mcopy() {{
  local args=() a
  for a in "$@"; do case "$a" in -s|-o) ;; *) args+=("$a") ;; esac; done
  local dest="{fat}/${{args[-1]#::}}"
  if [ -d "${{args[0]}}" ]; then mkdir -p "$dest"; cp -r "${{args[0]}}" "$dest/"; else mkdir -p "$(dirname "$dest")"; cp "${{args[0]}}" "$dest"; fi
}}
'''
        script = fake_mcopy + m.group(0) + "mkimage_abl\n"
        env = dict(os.environ, RELEASE_DIR=release, IMG_TMP=img_tmp, IMAGE_BOOTLABEL=card_boot,
                   IMAGE_DISKLABEL=card_disk)
        proc = subprocess.run(["bash", "-c", script], capture_output=True, text=True, env=env, timeout=30)
        card = f"{fat}/loader/entries/asgardos.conf"
        if proc.returncode != 0 or not os.path.isfile(card):
            problems.append(f"mkimage_abl failed: {proc.stdout}{proc.stderr}")
            return
        opts = entry_options(open(card).read())
        if f"boot=LABEL={card_boot}" not in opts or f"disk=LABEL={card_disk}" not in opts:
            problems.append(f"the card's boot entry names {opts}, not the card's labels (UPD-8)")
        if "new_option=1" not in opts:
            problems.append("mkimage_abl lost the entry's other options")
        if open(f"{release}/3rdparty/bootloader/loader/entries/asgardos.conf").read() != SHIPPED:
            problems.append("mkimage_abl changed the release's entry, which updates install (UPD-5)")


def run_update(t, old_entry):
    """update.sh against a fake /flash holding old_entry (None: no entry), with the shipped entry as the update's."""
    boot, system, storage, bin_dir = f"{t}/flash", f"{t}/update", f"{t}/storage", f"{t}/bin"
    for d in (boot, f"{system}/usr/share/bootloader/loader/entries", storage, bin_dir):
        os.makedirs(d, exist_ok=True)
    entries = f"{boot}/loader/entries"
    os.makedirs(entries, exist_ok=True)
    if old_entry is None:
        if os.path.exists(f"{entries}/asgardos.conf"):
            os.remove(f"{entries}/asgardos.conf")
    else:
        open(f"{entries}/asgardos.conf", "w").write(old_entry)
    open(f"{system}/usr/share/bootloader/loader/entries/asgardos.conf", "w").write(SHIPPED)
    for name in ("mount", "sync"):
        with open(f"{bin_dir}/{name}", "w") as f:
            f.write("#!/bin/sh\nexit 0\n")
        os.chmod(f"{bin_dir}/{name}", 0o755)
    with open(f"{bin_dir}/df", "w") as f:
        f.write("#!/bin/sh\necho 'Filesystem 1K-blocks Used Available Use% Mounted on'\necho '/dev/sda18 1 1 1 1% /flash'\n")
    os.chmod(f"{bin_dir}/df", 0o755)
    script = open(os.path.join(ROOT, "device", "bootloader", "update.sh")).read().replace("/storage/", f"{storage}/")
    with open(f"{t}/update.sh", "w") as f:
        f.write(script)
    env = dict(os.environ, PATH=f"{bin_dir}:{os.environ['PATH']}", BOOT_ROOT=boot, SYSTEM_ROOT=system)
    proc = subprocess.run(["sh", f"{t}/update.sh"], capture_output=True, text=True, env=env, timeout=30)
    if proc.returncode != 0:
        problems.append(f"update.sh failed: {proc.stdout}{proc.stderr}")
    return entry_options(open(f"{entries}/asgardos.conf").read())


def check_update(card_boot, card_disk):
    cases = [
        ("a card", SHIPPED.replace("LABEL=ASGARDOS", f"LABEL={card_boot}").replace("LABEL=STORAGE", f"LABEL={card_disk}")
         .replace(" new_option=1", ""), f"boot=LABEL={card_boot}", f"disk=LABEL={card_disk}"),
        ("an internal install", SHIPPED.replace(" new_option=1", ""), "boot=LABEL=ASGARDOS", "disk=LABEL=STORAGE"),
        ("a hand-edited entry", SHIPPED.replace("LABEL=ASGARDOS", "/dev/mmcblk0p1").replace("LABEL=STORAGE", "/dev/mmcblk0p2"),
         "boot=/dev/mmcblk0p1", "disk=/dev/mmcblk0p2"),
        ("an entry from before the label change, tab-separated", SHIPPED.replace("options    ", "options\t"),
         "boot=LABEL=ASGARDOS", "disk=LABEL=STORAGE"),
        ("no entry yet", None, "boot=LABEL=ASGARDOS", "disk=LABEL=STORAGE"),
    ]
    for what, old, want_boot, want_disk in cases:
        with tempfile.TemporaryDirectory() as t:
            opts = run_update(t, old)
        if want_boot not in opts or want_disk not in opts:
            problems.append(f"update.sh on {what}: the entry names {opts}, not {want_boot} {want_disk} (UPD-8)")
        if "new_option=1" not in opts:
            problems.append(f"update.sh on {what}: the update's new options didn't arrive ({opts})")
        if sum(o.startswith("boot=") for o in opts) != 1 or sum(o.startswith("disk=") for o in opts) != 1:
            problems.append(f"update.sh on {what}: boot=/disk= not exactly once each ({opts})")


def main():
    card_boot, card_disk = check_labels()
    check_mkimage(card_boot, card_disk)
    check_update(card_boot, card_disk)
    for p in problems:
        print(p)
    if problems:
        sys.exit("FAIL")
    print("OK")


if __name__ == "__main__":
    main()
