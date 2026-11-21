#!/usr/bin/env python3
"""Asgard OS updates from GitHub releases (UPD-9, UPD-10): find a newer release, download it, check it, stage it.

  asgard-update.py check      ask GitHub once; the answer goes to /run/asgard-update.json
  asgard-update.py boot       the check at boot (asgard-update-check.service): skipped when asgard.update.check_at_boot
                              is 0; without network, tries again every minute for ten minutes, then gives up quietly
  asgard-update.py download   download the release the check found to /storage/.update/<name>.part, resuming a partial
                              one; check it against its .sha256 and the .sha256 against its signature; only then
                              rename it to <name>.tar, which the installer takes at the next boot. Never restarts.
  asgard-update.py cancel     stop a download and delete its .part
  asgard-update.py status     the check's answer, the download's progress and what Home asked this boot, as one
                              JSON object (for Home)

A release counts when its tag is vX.Y.Z, newer than OS_VERSION in /etc/os-release, not a draft, not a pre-release
unless asgard.update.prerelease is on (the default), not the version the user skipped (asgard.update.skip), and it has
<OS_NAME>-<DISTRO_DEVICE>.<HW_ARCH>-X.Y.Z.tar with its .sha256 and .sig. The request carries no device data.
asgard.update.repo replaces the API's URL (tests, and a Thor check against a test server).
ASGARD_ROOT prefixes every path (host tests)."""
import hashlib
import json
import os
import re
import signal
import subprocess
import sys
import time

ROOT = os.environ.get("ASGARD_ROOT", "")
API = "https://api.github.com/repos/AsgardOperationSystem/asgardos/releases"
OS_RELEASE = ROOT + "/etc/os-release"
CFG = ROOT + "/storage/.config/system/configs/system.cfg"
KEY = ROOT + "/usr/share/asgard/release-key.pem"
UPDATE_DIR = ROOT + "/storage/.update"
WORK = UPDATE_DIR + "/.asgard-ota"          # the .sha256 and .sig; the installer clears dot-folders after an update
CHECK = ROOT + "/run/asgard-update.json"
PROGRESS = ROOT + "/run/asgard-update-progress.json"
ASKED = ROOT + "/run/asgard-update-asked"
AGENT = "AsgardOS-updater"                  # no version, no device: UPD-9
MARGIN = 64 << 20                           # free space kept beyond what the update needs
BOOT_TRIES, BOOT_WAIT = 10, 60
CURL_TRIES, CURL_WAIT = 10, 15


class NoNetwork(Exception):
    pass


def setting(key, default=""):
    try:
        with open(CFG) as f:
            for line in f:
                k, sep, v = line.rstrip("\n").partition("=")
                if sep and k.strip() == key:
                    return v.strip()
    except OSError:
        pass
    return default


def os_release():
    out = {}
    try:
        with open(OS_RELEASE) as f:
            for line in f:
                k, sep, v = line.strip().partition("=")
                if sep:
                    out[k] = v.strip('"')
    except OSError:
        pass
    return out


def version(text):
    """(major, minor, patch) for "X.Y.Z" or "vX.Y.Z", else None: date tags like v20261120 don't count."""
    m = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", text or "")
    return tuple(int(n) for n in m.groups()) if m else None


def tar_name(rel, ver):
    return f"{rel.get('OS_NAME', 'AsgardOS')}-{rel.get('DISTRO_DEVICE') or rel.get('HW_DEVICE', '')}." \
           f"{rel.get('HW_ARCH', '')}-{ver}.tar"


def pick(releases, current, rel, prerelease=True, skip=""):
    """The newest release this Thor should be offered, or None. releases: GitHub's list, as JSON."""
    now = version(current)
    if not now:
        return None   # a build without a release number can't tell what's newer
    best = None
    for r in releases:
        ver = version(r.get("tag_name"))
        if not ver or ver <= now or r.get("draft") or (r.get("prerelease") and not prerelease):
            continue
        text = ".".join(map(str, ver))
        if text == skip:
            continue
        name = tar_name(rel, text)
        assets = {a.get("name"): a for a in r.get("assets", [])}
        if not all(n in assets for n in (name, name + ".sha256", name + ".sig")):
            continue
        if best is None or ver > best[0]:
            best = (ver, {"version": text, "tag": r["tag_name"], "name": name, "size": assets[name].get("size", 0),
                          "tar": assets[name]["browser_download_url"],
                          "sha256": assets[name + ".sha256"]["browser_download_url"],
                          "sig": assets[name + ".sig"]["browser_download_url"],
                          "prerelease": bool(r.get("prerelease")), "notes": notes(r.get("body") or "")})
    return best[1] if best else None


def notes(body, lines=8):
    """The release's "What's new", or its start: a few short lines for the screen."""
    text = body.split("## What's new", 1)
    keep = []
    for line in (text[1] if len(text) > 1 else text[0]).splitlines():
        line = line.strip()
        if line.startswith("## ") and keep:
            break
        if line.startswith("- "):
            line = "• " + re.sub(r"\*\*|`|\[([^]]*)\]\([^)]*\)", lambda m: m.group(1) or "", line[2:])
            keep.append(line.split(". ")[0].rstrip(".") if len(line) > 90 else line)
        if len(keep) >= lines:
            break
    return "\n".join(keep)


def write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f)
    os.replace(tmp, path)


def read_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def curl(*args):
    return ["curl", "-fsSL", "--proto", "=https,http", "-A", AGENT, "--connect-timeout", "15", *args]


def fetch_releases():
    url = setting("asgard.update.repo") or API
    r = subprocess.run(curl("--max-time", "30", "-H", "Accept: application/vnd.github+json", url + "?per_page=30"),
                       capture_output=True, text=True)
    if r.returncode in (6, 7, 28, 35):   # no DNS, no connection, timeout, TLS handshake: no network yet
        raise NoNetwork(r.stderr.strip())
    if r.returncode:
        raise RuntimeError(f"GitHub answered with an error (curl {r.returncode})")
    return json.loads(r.stdout)


def check():
    rel = os_release()
    current = rel.get("OS_VERSION", "")
    try:
        found = pick(fetch_releases(), current, rel, setting("asgard.update.prerelease", "1") != "0",
                     setting("asgard.update.skip"))
    except NoNetwork:
        write_json(CHECK, {"checked": int(time.time()), "current": current, "error": "No internet"})
        raise
    except (RuntimeError, ValueError) as e:
        write_json(CHECK, {"checked": int(time.time()), "current": current, "error": str(e)})
        return 1
    write_json(CHECK, {"checked": int(time.time()), "current": current, **(found or {})})
    return 0


def boot():
    if setting("asgard.update.check_at_boot", "1") == "0":
        return 0
    for n in range(BOOT_TRIES):
        try:
            return check()
        except NoNetwork:
            if n + 1 < BOOT_TRIES:
                time.sleep(BOOT_WAIT)
    return 0


def progress(**state):
    write_json(PROGRESS, {"pid": os.getpid(), **state})


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def free(path):
    st = os.statvfs(path)
    return st.f_bavail * st.f_frsize


def signed(name):
    """None if the release's .sha256 is for this file and its signature matches the image's release key. Checked
    before the .tar is downloaded: a release signed with another key costs two small files, not the whole update."""
    sums, sig = f"{WORK}/{name}.sha256", f"{WORK}/{name}.sig"
    if not os.path.exists(KEY):
        return "This image has no release key to check the update with"
    r = subprocess.run(["openssl", "pkeyutl", "-verify", "-pubin", "-inkey", KEY, "-rawin", "-in", sums, "-sigfile", sig],
                       capture_output=True)
    if r.returncode:
        return "The update's signature doesn't match Asgard's release key"
    fields = open(sums).read().split()
    if len(fields) < 2 or fields[1].lstrip("*") != name:
        return "The update's checksum file is for another file"
    return None


def verify(part, name):
    """None if the download is the release: the signature still holds and its sha256 matches. Else why not."""
    why = signed(name)
    if why:
        return why
    if sha256(part) != open(f"{WORK}/{name}.sha256").read().split()[0].lower():
        return "The download doesn't match its checksum"
    return None


def download():
    found = read_json(CHECK)
    if not found.get("version"):
        progress(state="error", error="No update to download")
        return 1
    name, size = found["name"], int(found.get("size") or 0)
    tar, part = f"{UPDATE_DIR}/{name}", f"{UPDATE_DIR}/{name}.part"
    os.makedirs(WORK, exist_ok=True)
    if os.path.exists(tar):
        progress(state="ready", version=found["version"], tar=tar)
        return 0
    for old in os.listdir(UPDATE_DIR):   # a .part of another version, left by an older check
        if old.endswith(".part") and old != name + ".part":
            os.remove(f"{UPDATE_DIR}/{old}")
    have = os.path.getsize(part) if os.path.exists(part) else 0
    # The installer unpacks the .tar's KERNEL and SYSTEM beside it, so the update needs about twice its size.
    need = (size - have) + size + MARGIN
    if free(UPDATE_DIR) < need:
        progress(state="error", error=f"Needs {need >> 20} MB free in /storage, has {free(UPDATE_DIR) >> 20} MB")
        return 1

    curl_proc = None

    def stop(*_):
        if curl_proc and curl_proc.poll() is None:
            curl_proc.terminate()
        sys.exit(1)
    signal.signal(signal.SIGTERM, stop)

    for what in ("sha256", "sig"):
        r = subprocess.run(curl("--max-time", "60", "-o", f"{WORK}/{name}.{what}", found[what]), capture_output=True)
        if r.returncode:
            progress(state="error", error="Couldn't download the update's checksum and signature")
            return 1
    why = signed(name)
    if why:
        if os.path.exists(part):
            os.remove(part)
        progress(state="error", error=why)
        return 1
    for n in range(CURL_TRIES):
        # -C -: resume where the .part ends, so a dropped connection or a sleep doesn't start over. A stall of a minute
        # counts as dropped.
        curl_proc = subprocess.Popen(curl("-C", "-", "--speed-limit", "1024", "--speed-time", "60", "-o", part,
                                          found["tar"]), stderr=subprocess.DEVNULL)
        while curl_proc.poll() is None:
            progress(state="downloading", version=found["version"],
                     done=os.path.getsize(part) if os.path.exists(part) else 0, total=size)
            time.sleep(1)
        if curl_proc.returncode == 0 or (size and os.path.exists(part) and os.path.getsize(part) >= size):
            break
        if curl_proc.returncode == 33 and os.path.exists(part):   # the server won't resume: start this file over
            os.remove(part)
        progress(state="downloading", version=found["version"], done=os.path.getsize(part) if os.path.exists(part)
                 else 0, total=size, retry=n + 1)
        time.sleep(CURL_WAIT)
    else:
        progress(state="error", error="The download kept failing; it resumes from where it stopped next time")
        return 1
    progress(state="verifying", version=found["version"])
    why = verify(part, name)
    if why:
        os.remove(part)   # UPD-10: never staged, and not resumed from either
        progress(state="error", error=why)
        return 1
    os.replace(part, tar)  # UPD-2: only now does it look like an update
    progress(state="ready", version=found["version"], tar=tar)
    return 0


def cancel():
    state = read_json(PROGRESS)
    pid = state.get("pid")
    if pid and state.get("state") in ("downloading", "verifying"):
        try:
            os.kill(pid, signal.SIGTERM)
            for _ in range(50):
                os.kill(pid, 0)
                time.sleep(0.1)
        except ProcessLookupError:
            pass
    for f in os.listdir(UPDATE_DIR) if os.path.isdir(UPDATE_DIR) else []:
        if f.endswith(".part"):
            os.remove(f"{UPDATE_DIR}/{f}")
    write_json(PROGRESS, {"state": "cancelled"})
    return 0


def status():
    found, state = read_json(CHECK), read_json(PROGRESS)
    try:
        with open(ASKED) as f:   # what Home already asked this boot (its prompt, once a boot)
            found["asked"] = f.read().strip()
    except OSError:
        pass
    pid = state.get("pid")
    if state.get("state") in ("downloading", "verifying") and pid:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            state = {"state": "stopped"}   # Home or the Thor restarted under it: Download resumes it
        except PermissionError:
            pass
    print(json.dumps({**found, "download": state}))
    return 0


def main(argv):
    commands = {"check": check, "boot": boot, "download": download, "cancel": cancel, "status": status}
    if len(argv) != 2 or argv[1] not in commands:
        print(__doc__, file=sys.stderr)
        return 2
    try:
        return commands[argv[1]]()
    except NoNetwork:
        print("asgard-update: no internet", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
