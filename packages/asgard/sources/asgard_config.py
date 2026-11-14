#!/usr/bin/env python3
"""Asgard config layer: asgard.yml sits above the image defaults and below the user's own changes.

At every boot each yml key is written only if the user hasn't changed it: its current value is missing, still the
image default, or still what this script applied last time (APPLIED). Change a value in Thor Settings / ROCKNIX ES
and the yml never touches it again; edit the yml and the new value reaches every key you haven't changed.

Keys are ROCKNIX system.cfg keys written as YAML (wifi: {ssid: x} -> wifi.ssid=x), except
ssh.authorized_keys (a list), whose lines are appended to /storage/.ssh/authorized_keys, and
asgard.stick_calibration (rsinput parameter: integer), which becomes the stick calibration file when the device has
none of its own (--stick-calibration, run before InputPlumber starts: SPEC CAL-3).
Values are written verbatim. Quote a value that contains " #" or starts with a quote.

Usage: asgard_config.py            apply the first yml found in SOURCES
       asgard_config.py --stick-calibration [FILE]   write its stick calibration (asgard-gpcal-apply.sh runs this)
       asgard_config.py --test     self-check
"""
import json
import os
import re
import shutil
import sys

# ponytail: first file wins, no merging. /flash is the FAT boot partition (editable from any PC); installtointernal
# doesn't carry it over, so the /storage copy is the fallback for an internal install.
SOURCES = ["/flash/asgard.yml", "/storage/.config/asgard/asgard.yml"]
APPLIED = "/storage/.config/asgard/applied.json"
SYS_CFG = "/storage/.config/system/configs/system.cfg"
SYS_DEFAULT = "/usr/config/system/configs/system.cfg"
AUTH_KEYS = "/storage/.ssh/authorized_keys"
GPCAL_SAVED = "/storage/.config/asgard/gpcal.sh"  # asgard-gpcal-apply.sh's saved calibration (CAL-2)
GPCAL_MARK = "# from asgard.yml: asgard.stick_calibration"
STICK_KEY = "asgard.stick_calibration"


# --- YAML subset: nested mappings, scalars, block lists of scalars, # comments ------------------------------------

def _uncomment(line):
    quote = None
    for i, c in enumerate(line):
        if quote:
            quote = None if c == quote else quote
        elif c in "\"'" and (i == 0 or line[i - 1] in " :-"):
            quote = c
        elif c == "#" and (i == 0 or line[i - 1] in " \t"):
            return line[:i]
    return line


def _scalar(s):
    if len(s) >= 2 and s[0] == s[-1] == '"':
        return json.loads(s)
    if len(s) >= 2 and s[0] == s[-1] == "'":
        return s[1:-1].replace("''", "'")
    return s


def parse_yaml(text):
    lines = []
    for n, raw in enumerate(text.splitlines(), 1):
        line = _uncomment(raw).rstrip()
        if line.strip() and line.strip() != "---":
            if "\t" in line[:len(line) - len(line.lstrip())]:
                raise ValueError(f"line {n}: tabs aren't allowed for indentation")
            lines.append((n, len(line) - len(line.lstrip()), line.strip()))
    root = {}
    stack = [(-1, root)]  # (indent that owns the container, container)
    for i, (n, ind, body) in enumerate(lines):
        while ind <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        if body == "-" or body.startswith("- "):
            if not isinstance(parent, list):
                raise ValueError(f"line {n}: list item outside a list")
            parent.append(_scalar(body[1:].strip()))
            continue
        key, sep, val = body.partition(":")
        if not sep or isinstance(parent, list) or (val and not val.startswith(" ")):
            raise ValueError(f"line {n}: expected 'key: value'")
        key, val = _scalar(key.strip()), val.strip()
        if val:
            parent[key] = _scalar(val)
            continue
        nxt = lines[i + 1] if i + 1 < len(lines) else None
        if nxt and nxt[2].startswith("-") and nxt[1] >= ind:
            parent[key] = []
            stack.append((ind - 0.5, parent[key]))  # "- item" may sit at the key's own indent
        elif nxt and nxt[1] > ind:
            parent[key] = {}
            stack.append((ind, parent[key]))
        else:
            parent[key] = ""
    return root


def flatten(d, prefix=""):
    out = {}
    for k, v in d.items():
        if isinstance(v, dict):
            out.update(flatten(v, f"{prefix}{k}."))
        else:
            out[f"{prefix}{k}"] = v
    return out


# --- targets --------------------------------------------------------------------------------------------------------

def read_cfg(path):
    out = {}
    try:
        for line in open(path, encoding="utf-8"):
            k, sep, v = line.rstrip("\n").partition("=")
            if sep:
                out[k] = v
    except FileNotFoundError:
        pass
    return out


def write_cfg(path, updates):
    lines = open(path, encoding="utf-8").read().splitlines()
    done = set()
    for i, line in enumerate(lines):
        k = line.partition("=")[0]
        if k in updates:
            lines[i] = f"{k}={updates[k]}"
            done.add(k)
    lines += [f"{k}={v}" for k, v in updates.items() if k not in done]
    _atomic(path, "\n".join(lines) + "\n")


def _atomic(path, text):
    tmp = path + ".asgard-tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    if os.path.exists(path):
        shutil.copymode(path, tmp)
    os.replace(tmp, path)


def _seed(path, default):
    """ROCKNIX copies the default system.cfg in on first use; do the same so a missing file keeps its defaults."""
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        shutil.copy(default, path) if os.path.exists(default) else open(path, "w").close()


def apply(conf):
    """Write every yml key the user hasn't overridden. Returns {key: value} actually written."""
    try:
        applied = json.load(open(APPLIED))
    except (OSError, ValueError):
        applied = {}
    wrote, updates = {}, {}
    sys_cur, sys_def = read_cfg(SYS_CFG), read_cfg(SYS_DEFAULT)
    for key, val in flatten(conf).items():
        if key.startswith(STICK_KEY + "."):
            continue  # a file, not system.cfg keys: stick_calibration()
        if key == "ssh.authorized_keys":
            add_keys(val if isinstance(val, list) else [val])
            continue
        val = str(val)
        cur, default = sys_cur.get(key), sys_def.get(key)
        if cur in (None, default, applied.get(key)) and cur != val:
            updates[key] = val
            wrote[key] = val
        if cur in (None, default, applied.get(key), val):
            applied[key] = val  # still ours; a key the user changed stays theirs (not recorded)
    if updates:
        _seed(SYS_CFG, SYS_DEFAULT)
        write_cfg(SYS_CFG, updates)
    os.makedirs(os.path.dirname(APPLIED), exist_ok=True)
    _atomic(APPLIED, json.dumps(applied, indent=1, sort_keys=True))
    return wrote


def add_keys(keys):
    os.makedirs(os.path.dirname(AUTH_KEYS), mode=0o700, exist_ok=True)
    have = set(open(AUTH_KEYS).read().splitlines()) if os.path.exists(AUTH_KEYS) else set()
    new = [k for k in keys if k and k not in have]
    if new:
        with open(AUTH_KEYS, "a") as f:
            f.writelines(k + "\n" for k in new)
    os.chmod(AUTH_KEYS, 0o600) if os.path.exists(AUTH_KEYS) else None


def stick_calibration(yml):
    """CAL-3: write the yml's calibration as GPCAL_SAVED, in GPcal's own line format, unless the device has its own
    (a file without our mark: made on the device, so it wins). Returns True if the file was written."""
    section = yml.get("asgard")
    cal = section.get("stick_calibration") if isinstance(section, dict) else None
    if not isinstance(cal, dict) or not cal:
        return False
    try:
        with open(GPCAL_SAVED, encoding="utf-8") as f:
            old = f.read()
    except FileNotFoundError:
        old = None
    if old is not None and not old.startswith(GPCAL_MARK + "\n"):
        return False
    lines = [GPCAL_MARK]
    for name, val in cal.items():
        if not re.fullmatch(r"[a-z_]+", str(name)) or name == "update_params" or not re.fullmatch(r"-?[0-9]+", str(val)):
            raise ValueError(f"{STICK_KEY}.{name}: expected an rsinput parameter name and a whole number")
        lines.append(f"echo {int(val)} > /sys/module/rsinput/parameters/{name}")
    lines.append("echo 1 > /sys/module/rsinput/parameters/update_params")
    text = "\n".join(lines) + "\n"
    if text == old:
        return False
    os.makedirs(os.path.dirname(GPCAL_SAVED), exist_ok=True)
    _atomic(GPCAL_SAVED, text)
    return True


def main(stick=False):
    src = next((p for p in SOURCES if os.path.exists(p)), None)
    if not src:
        return
    try:
        conf = parse_yaml(open(src, encoding="utf-8").read())
        if stick:
            if stick_calibration(conf):
                print(f"asgard-config: {src}: stick calibration written")
            return
    except ValueError as e:
        print(f"asgard-config: {src}: {e}; nothing applied")
        return
    wrote = apply(conf)
    # Never log values: the yml holds passwords.
    print(f"asgard-config: {src}: applied {', '.join(sorted(wrote)) or 'nothing (all set or user-overridden)'}")


def test():
    import tempfile
    global APPLIED, SYS_CFG, SYS_DEFAULT, AUTH_KEYS
    y = parse_yaml("""
# comment
wifi:
  enabled: 1
  ssid: My Net   # trailing comment
  key: "p#ss \\"x\\""
global:
  retroachievements:
    username: me
screenscraper:
  password: 'a<b>&"c'
ssh:
  authorized_keys:
  - ssh-ed25519 AAAA one
  - ssh-ed25519 BBBB two
empty:
""")
    f = flatten(y)
    assert f["wifi.ssid"] == "My Net" and f["wifi.key"] == 'p#ss "x"', f
    assert f["global.retroachievements.username"] == "me" and f["empty"] == ""
    assert f["ssh.authorized_keys"] == ["ssh-ed25519 AAAA one", "ssh-ed25519 BBBB two"]
    for bad in ("a:\n\tb: 1", "- x", "a:b"):
        try:
            parse_yaml(bad)
            raise AssertionError(bad)
        except ValueError:
            pass
    d = tempfile.mkdtemp()
    APPLIED, SYS_CFG, SYS_DEFAULT = f"{d}/applied.json", f"{d}/user/system.cfg", f"{d}/system.cfg"
    AUTH_KEYS = f"{d}/ssh/authorized_keys"
    open(SYS_DEFAULT, "w").write("wifi.enabled=0\nwifi.ssid=\nsystem.hostname=SM8550\n")
    # 1st boot: no user files yet -> everything applied, defaults kept
    w = apply({"wifi": {"enabled": "1", "ssid": "Net"}, "screenscraper": {"username": "u", "password": 'a&"b'},
               "ssh": {"authorized_keys": ["k1"]}})
    assert set(w) == {"wifi.enabled", "wifi.ssid", "screenscraper.username", "screenscraper.password"}, w
    assert read_cfg(SYS_CFG) == {"wifi.enabled": "1", "wifi.ssid": "Net", "system.hostname": "SM8550",
                                 "screenscraper.username": "u", "screenscraper.password": 'a&"b'}
    # user changes the ssid on the device; the yml changes ssid and enabled
    write_cfg(SYS_CFG, {"wifi.ssid": "Phone"})
    w = apply({"wifi": {"enabled": "0", "ssid": "Net2"}, "ssh": {"authorized_keys": ["k1", "k2"]}})
    assert w == {"wifi.enabled": "0"}, w
    assert read_cfg(SYS_CFG)["wifi.ssid"] == "Phone"
    assert open(AUTH_KEYS).read() == "k1\nk2\n" and os.stat(AUTH_KEYS).st_mode & 0o777 == 0o600
    # nothing changed -> nothing written; user value back to the default -> yml owns it again
    assert apply({"wifi": {"enabled": "0", "ssid": "Net2"}}) == {}
    write_cfg(SYS_CFG, {"wifi.ssid": ""})
    assert apply({"wifi": {"ssid": "Net2"}}) == {"wifi.ssid": "Net2"}
    shutil.rmtree(d)
    print("asgard_config: ok")


if __name__ == "__main__":
    if sys.argv[1:] == ["--test"]:
        test()
    elif sys.argv[1:2] == ["--stick-calibration"]:
        GPCAL_SAVED = sys.argv[2] if len(sys.argv) > 2 else GPCAL_SAVED  # the caller's $SAVED
        main(stick=True)
    else:
        main()
