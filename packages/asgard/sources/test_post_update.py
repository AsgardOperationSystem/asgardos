#!/usr/bin/env python3
# spec: UPD-4 SCR-2
# requires: cmd:bash cmd:rsync cmd:awk
# Runs the real post-update against a fake /storage and image: the user's saves, ROMs, settings, state and SSH keys come
# through two updates untouched, emulators' settings keep their values and gain new shipped keys, old keys convert, and
# a default added to the image later reaches system.cfg once, never over the user's value or after they cleared it.
# It runs a copy with its paths rewritten into a temp dir, so it needs no root or namespaces and leaves the host alone.
import os
import re
import subprocess
import sys
import tempfile

SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "asgardos", "sources", "post-update")
SYSTEM_CFG = ".config/system/configs/system.cfg"
CORE_OPTIONS = ".config/retroarch/retroarch-core-options.cfg"
MELONDS_INI = ".config/melonDS/melonDS.ini"
# Shipped values that were wrong: each converts where the user still has it, and stays where they changed it (UPD-4).
CONVERTED = {
    ".config/drastic/config/drastic.cfg": (
        "controls_a[CONTROL_INDEX_UP] = 1035\ncontrols_a[CONTROL_INDEX_MENU] = 1032\n"
        "controls_b[CONTROL_INDEX_START] = 1031\ncontrols_b[CONTROL_INDEX_SELECT] = 1028\n",
        "controls_a[CONTROL_INDEX_UP] = 105\ncontrols_a[CONTROL_INDEX_MENU] = 65535\n"
        "controls_b[CONTROL_INDEX_START] = 1033\ncontrols_b[CONTROL_INDEX_SELECT] = 1028\n"),
    ".config/drastic/drastic.gptk": ("up = \\\\\ndown = w\nleft=\\\\\n", "up = i\ndown = w\nleft=j\n"),
    ".config/duckstation/settings.ini": ("[Pad1]\nRLeft = SDL-0/+RightX\nRRight = SDL-0/-RightX\n",
                                         "[Pad1]\nRLeft = SDL-0/-RightX\nRRight = SDL-0/+RightX\n"),
    ".config/aethersx2/inis/PCSX2.ini": ("[Hotkeys]\nOpenPauseMenu = SDL-0/Guide & SDL-0/Y\n[Pad1]\nAnalog = SDL-0/Guide\n",
                                         "[Hotkeys]\nOpenPauseMenu = Keyboard/Escape\nOpenPauseMenu = SDL-0/Guide & SDL-0/Y\n"
                                         "[Pad1]\nAnalog = \n"),
}

IMAGE = {
    "system/configs/system.cfg": "system.hostname=ASGARD\nwifi.enabled=0\n",
    "system/shipped.conf": "shipped\n",
    "game/shipped": "shipped\n",
    "modules/tool.sh": "shipped\n",
    "locale/en": "shipped\n",
    "ppsspp/assets/ui_images/a": "shipped\n",
    "ppsspp/assets/NotoSansJP-Regular.ttf": "shipped\n",
    "retroarch/retroarch-core-options.cfg": 'kept_core = "shipped"\nnew_core = "shipped"\n',
    "melonDS/melonDS.ini": "Key_A=-1\nNew_Hotkey=5\n",
    "melonDS/melonDS.gptk": "shipped\n",
    "melonDS/new.qss": "shipped\n",
    "dolphin-emu/Hotkeys.ini": "shipped\n",
}

# Must come out byte for byte as they went in.
USER_FILES = {
    "roms/nds/game.nds": "rom\n",
    "roms/nds/game.sav": "save\n",
    "roms/savestates/nds/game.ml1": "state\n",
    "roms/bios/bios7.bin": "bios\n",
    ".config/asgard/asgard.yml": "wifi: {ssid: mine}\n",
    ".config/asgard/state": "state\n",
    ".config/thor/crashes/one.log": "log\n",
    ".ssh/authorized_keys": "ssh-ed25519 AAAA mine\n",
    ".config/system/configs/asgardos-boot.conf": "mine\n",
    ".config/melonDS/melonDS.gptk": "mine\n",
    ".config/dolphin-emu/Hotkeys.ini": "mine\n",
    ".config/game/mine": "mine\n",
    ".config/ppsspp/assets/ui_images/a": "shipped\n",
    ".config/ppsspp/assets/NotoSansJP-Regular.ttf": "shipped\n",
}

USER_SYSTEM_CFG = """# my comment
system.hostname=MINE
wifi.enabled=1
3ds["Pokemon X.3ds"].cpu_cap_mid=60
rocknix.old=kept
"""


def write(root, files):
    for name, text in files.items():
        path = os.path.join(root, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(text)


def read(root, name):
    with open(os.path.join(root, name)) as f:
        return f.read()


def snapshot(root):
    found = {}
    for top, _, names in os.walk(root):
        for name in names:
            path = os.path.join(top, name)
            if os.path.isfile(path) and not os.path.islink(path):
                found[os.path.relpath(path, root)] = read(root, os.path.relpath(path, root))
    return found


def prepared_script(tmp):
    """post-update with the paths it writes moved into tmp, and refusing to run if one was missed."""
    with open(SCRIPT) as f:
        text = f.read()
    rewrite = r"(?<![\w./-])/(storage|usr/config|var/log|etc/profile)(?![\w-])"
    out = re.sub(rewrite, lambda m: f"{tmp}/{m.group(1)}", text)
    code = re.sub(r"^\s*#.*$", "", out, flags=re.M)
    if re.search(r"(?<![\w./-])/(storage|usr/config|flash)(?![\w-])", code):
        sys.exit("FAIL: a path wasn't rewritten, refusing to run post-update on this host")
    path = f"{tmp}/post-update"
    with open(path, "w") as f:
        f.write(out)
    return path


def update(tmp, script):
    env = {"PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "HOME": tmp, "LC_ALL": "C"}
    proc = subprocess.run(["bash", script], cwd=tmp, env=env, capture_output=True, text=True, timeout=60)
    return proc.stdout + proc.stderr


def check(tmp, storage, failures):
    for name, want in USER_FILES.items():
        path = os.path.join(storage, name)
        if not os.path.isfile(path):
            failures.append(f"lost: {name}")
        elif read(storage, name) != want:
            failures.append(f"changed: {name}")

    cfg = read(storage, SYSTEM_CFG)
    for line in ("# my comment", "system.hostname=MINE", "wifi.enabled=1", '3ds["Pokemon X.3ds"].cpu_cap_mid=60'):
        if line not in cfg.splitlines():
            failures.append(f"system.cfg lost: {line}")
    if "asgardos.old=kept" not in cfg.splitlines() or "rocknix.old" in cfg:
        failures.append("system.cfg: rocknix.old wasn't converted to asgardos.old")
    if cfg.splitlines().count("switch.top_refresh=60") != 1:
        failures.append("system.cfg: the Switch's 60 Hz top screen wasn't added once")

    if not os.path.isfile(os.path.join(storage, ".config/system/shipped.conf")):
        failures.append("the image's new file in .config/system wasn't synced")

    options = read(storage, CORE_OPTIONS).splitlines()
    if 'kept_core = "mine"' not in options:
        failures.append("core options: the user's value was lost")
    if 'new_core = "shipped"' not in options:
        failures.append("core options: a new shipped key wasn't added")

    ini = read(storage, MELONDS_INI).splitlines()
    if "Key_A=7" not in ini:
        failures.append("melonDS: the user's value was lost")
    if "New_Hotkey=5" not in ini:
        failures.append("melonDS: a new shipped key wasn't added")
    if not os.path.isfile(os.path.join(storage, ".config/melonDS/new.qss")):
        failures.append("melonDS: a new shipped file wasn't added")

    for name, (_, want) in CONVERTED.items():
        if read(storage, name) != want:
            failures.append(f"{name}: wrong after the conversion:\n{read(storage, name)}")


def image_defaults(failures):
    """Each one-time default in post-update is also in the image's system.cfg, with the same value, so a new install and
    an updated one start alike. The Switch's top screen at 60 Hz is one (SCR-2)."""
    image = read(os.path.dirname(SCRIPT), "../config/system/configs/system.cfg").splitlines()
    once = re.findall(r"^add_default_once \S+ (\S+) (\S+)$", read(os.path.dirname(SCRIPT), "post-update"), re.M)
    if ("switch.top_refresh", "60") not in once:
        failures.append("post-update doesn't add the Switch's 60 Hz top screen")
    for key, value in once:
        if f"{key}={value}" not in image:
            failures.append(f"the image's system.cfg lacks post-update's default {key}={value}")


def main():
    with tempfile.TemporaryDirectory() as tmp:
        write(f"{tmp}/usr/config", IMAGE)
        write(tmp, {"etc/profile": "tocon() { :; }\nldconfig() { :; }\n", "var/log/boot.log": ""})
        storage = f"{tmp}/storage"
        write(storage, USER_FILES)
        write(storage, {SYSTEM_CFG: USER_SYSTEM_CFG,
                        CORE_OPTIONS: 'kept_core = "mine"',  # no newline at the end: a new key must not join this line
                        MELONDS_INI: "Key_A=7\nMy_Own=1\n"})
        write(storage, {name: old for name, (old, _) in CONVERTED.items()})
        script = prepared_script(tmp)

        output = update(tmp, script)
        failures = []
        image_defaults(failures)
        check(tmp, storage, failures)
        first = snapshot(storage)
        update(tmp, script)
        check(tmp, storage, failures)
        second = snapshot(storage)
        for name in sorted(set(first) | set(second)):
            if first.get(name) != second.get(name):
                failures.append(f"the second update changed: {name}")

        # A fresh install has no melonDS settings: it gets the shipped ones whole.
        subprocess.run(["rm", "-rf", f"{storage}/.config/melonDS"], check=True)
        update(tmp, script)
        if read(storage, MELONDS_INI) != IMAGE["melonDS/melonDS.ini"]:
            failures.append("melonDS: a missing config wasn't installed from the image")

        # A one-time default stays away once the user clears it, and never replaces their own value.
        cfg_path = os.path.join(storage, SYSTEM_CFG)
        write(storage, {SYSTEM_CFG: read(storage, SYSTEM_CFG).replace("switch.top_refresh=60\n", "")})
        update(tmp, script)
        if "switch.top_refresh" in read(storage, SYSTEM_CFG):
            failures.append("system.cfg: a default the user cleared came back")
        subprocess.run(["rm", "-f", os.path.join(storage, ".config/asgard/defaults-applied")], check=True)
        with open(cfg_path, "a") as f:
            f.write("switch.top_refresh=120")   # no newline at the end: the default must not join or replace it
        update(tmp, script)
        if read(storage, SYSTEM_CFG).splitlines()[-1] != "switch.top_refresh=120":
            failures.append("system.cfg: a default replaced the user's own value")

        if failures:
            print(output[-1500:])
            sys.exit("FAIL:\n  " + "\n  ".join(dict.fromkeys(failures)))
    print("OK")


if __name__ == "__main__":
    main()
