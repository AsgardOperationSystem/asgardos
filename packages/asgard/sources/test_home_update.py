#!/usr/bin/env python3
# spec: SET-3 UPD-9 UPD-10 XFER-1
# requires: file:build/AsgardOS-SM8550.aarch64/toolchain/usr/local/qt6/lib/libQt6Quick.so cmd:cmake
"""Home's side of the OTA, pressed through on the host with asgard-update.py's answers faked (the script itself is
test_asgard_update.py). Settings > About > Updates: what a check found, Download, the progress and Cancel, the release
notes, the two settings, and the install row, which restarts only on the charger or at 30% or more (SET-3). Home's
prompt: once a boot, Download / Later / Skip this version, then Restart when it's ready, never with a low battery."""
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "../../../tools/test"))
import home_harness as hh  # noqa: E402
from home_harness import CFG, Root  # noqa: E402

ABOUT, UPDATES = 5, 5        # About is the sixth category; Updates its sixth row
FOUND = {"checked": 1, "current": "0.0.1", "version": "0.0.2", "name": "AsgardOS-SM8550.aarch64-0.0.2.tar",
         "size": 1710090240, "prerelease": True, "notes": "• The gyro sets itself up\n• Release numbers", "download": {}}
TAR = "/storage/.update/AsgardOS-SM8550.aarch64-0.0.2.tar"


def keys(*parts):
    return " ".join(p for p in parts if p)


def down(n, then="a"):
    return keys(*["down"] * n, then)


UPDATES_PAGE = keys("start", *["down"] * ABOUT, "a", down(UPDATES))


def battery(root, level, status="Discharging"):
    root.write("sys/class/power_supply/battery/capacity", f"{level}\n")
    root.write("sys/class/power_supply/battery/status", f"{status}\n")


def copy(root, status, staged=""):
    """Home's QML, with asgard-update.py status answering `status` (Settings and Home) and the .tar listing `staged`."""
    out = f"{root.path}/.qml"
    shutil.rmtree(out, ignore_errors=True)
    shutil.copytree(f"{hh.SRC}/qml", out)
    answers = {"asgard-update.py": json.dumps(status), "ls /storage/.update": staged}
    text = open(f"{out}/Settings.qml").read().replace("backend.exec(", "fakeExec(")
    text = text.replace("    function close() {", """    readonly property var answers: %s
    function fakeExec(cmd, done) {
        console.log("exec: " + cmd)
        let out = ""
        for (const k in answers) if (new RegExp(k).test(cmd)) out = answers[k]
        if (done) Qt.callLater(done, out)
    }
    function close() {""" % json.dumps(answers))
    open(f"{out}/Settings.qml", "w").write(text)
    text = open(f"{out}/Main.qml").read()
    old = 'backend.exec(app.ota + "status", app.offerUpdate)'
    assert old in text
    open(f"{out}/Main.qml", "w").write(text.replace(old, "app.offerUpdate(%s)" % json.dumps(json.dumps(status))))
    return {"ASGARD_HOME_QML": out}


def press(root, sequence, status, staged=""):
    return root.run(sequence, env=copy(root, status, staged), ms=300)


def cfg(root, key):
    values = [line.split("=", 1)[1] for line in root.read(CFG).splitlines() if line.startswith(key + "=")]
    return values[-1] if values else None


ASKED = dict(FOUND, asked="0.0.2")   # Home's prompt already shown this boot: out of the way of Settings

# ---- Settings > About > Updates ------------------------------------------------------------------------------------
with Root() as r:
    r.library()
    battery(r, 80)
    assert press(r, keys("start", *["down"] * ABOUT, "a"), ASKED).shows("Asgard 0.0.2 is available")
    page = press(r, UPDATES_PAGE, ASKED)
    for text in ("Check for updates", "Asgard 0.0.2 (pre-release) is available", "Download 0.0.2", "1631 MB",
                 "What's new in 0.0.2", "The gyro sets itself up", "Release numbers", "Asgard 0.0.1", "Check at startup", "Pre-releases"):
        assert page.shows(text), text
    assert "asgard-update.py check" in press(r, keys(UPDATES_PAGE, "a"), ASKED).log
    started = press(r, keys(UPDATES_PAGE, down(1)), ASKED)
    assert "shell: python3 /usr/share/asgard/asgard-transfers.py add update" in started.log   # through the queue (XFER-1)
    # Downloading: its progress and Cancel, no Download
    busy = dict(ASKED, download={"state": "downloading", "version": "0.0.2", "done": 855045120, "total": 1710090240})
    shown = press(r, UPDATES_PAGE, busy)
    assert shown.shows("Downloading 0.0.2") and shown.shows("50%") and shown.shows("Cancel download")
    assert not shown.shows("Download 0.0.2")
    cancelled = press(r, keys(UPDATES_PAGE, down(2)), busy).log
    assert "asgard-update.py cancel" in cancelled and "asgard-transfers.py cancel update" in cancelled, cancelled[-800:]
    # A failed or interrupted download: Resume, with the reason
    failed = dict(ASKED, download={"state": "error", "error": "The download doesn't match its checksum"})
    shown = press(r, UPDATES_PAGE, failed)
    assert shown.shows("Resume 0.0.2") and shown.shows("doesn't match its checksum")
    # Nothing newer, and no internet
    assert press(r, UPDATES_PAGE, {"checked": 1, "current": "0.0.1"}).shows("Up to date")
    assert press(r, UPDATES_PAGE, {"current": "0.0.1", "error": "No internet"}).shows("No internet")
    # The two settings
    nothing = {"checked": 1, "current": "0.0.1"}
    press(r, keys(UPDATES_PAGE, down(2)), nothing)               # Check, Installed, Check at startup
    assert cfg(r, "asgard.update.check_at_boot") == "0"
    press(r, keys(UPDATES_PAGE, down(3)), nothing)
    assert cfg(r, "asgard.update.prerelease") == "0"

# ---- SET-3: installing restarts only on the charger or at 30% or more, after asking -------------------------------------
with Root() as r:
    r.library()
    ready = dict(ASKED, asked="ready 0.0.2", download={"state": "ready", "version": "0.0.2", "tar": TAR})
    about_install = keys("start", *["down"] * ABOUT, "a", down(UPDATES))
    battery(r, 20)
    low = press(r, about_install, ready, TAR)
    assert low.shows("plug in the charger or charge to 30%") and "systemctl reboot" not in low.log
    battery(r, 20, "Charging")
    assert press(r, about_install, ready, TAR).shows("installs AsgardOS-SM8550.aarch64-0.0.2.tar")
    battery(r, 30)
    asked = press(r, about_install, ready, TAR)
    assert asked.shows("installs AsgardOS-SM8550.aarch64-0.0.2.tar") and "systemctl reboot" not in asked.log
    assert "shell: systemctl reboot" in press(r, keys(about_install, "a"), ready, TAR).log

# ---- Home's prompt ---------------------------------------------------------------------------------------------------
with Root() as r:
    r.library()
    battery(r, 80)
    shown = press(r, "", FOUND)
    assert shown.shows("Asgard 0.0.2 is available") and shown.shows("You have 0.0.1")
    assert shown.shows("Later") and shown.shows("Skip this version") and shown.shows("Download")
    assert "shell: echo '0.0.2' > /run/asgard-update-asked" in shown.log            # once a boot
    assert "asgard-update.py download" not in shown.log
    assert "shell: python3 /usr/share/asgard/asgard-transfers.py add update" in press(r, "a", FOUND).log   # Download: the default, queued (XFER-1)
    later = press(r, "b", FOUND)
    assert not later.shows("is available") and "download" not in later.log.split("asked")[-1]
    skipped = press(r, "left a", FOUND)                                             # Skip this version
    assert cfg(r, "asgard.update.skip") == "0.0.2" and "asgard-update.py check" in skipped.log
    assert not press(r, "", ASKED).shows("is available")                           # already asked this boot
    assert not press(r, "", {"checked": 1, "current": "0.0.1"}).shows("is available")
    downloading = dict(FOUND, download={"state": "downloading"})
    assert not press(r, "", downloading).shows("is available")
    # Downloaded and checked: Restart, once, and not with a low battery
    ready = dict(FOUND, download={"state": "ready", "version": "0.0.2", "tar": TAR})
    shown = press(r, "", ready)
    assert shown.shows("Asgard 0.0.2 is ready") and "shell: echo 'ready 0.0.2'" in shown.log
    assert "shell: systemctl reboot" in press(r, "a", ready).log
    assert "systemctl reboot" not in press(r, "b", ready).log
    assert not press(r, "", dict(ready, asked="ready 0.0.2")).shows("is ready")
    battery(r, 15)
    assert not press(r, "", ready).shows("is ready")
print("ok")
