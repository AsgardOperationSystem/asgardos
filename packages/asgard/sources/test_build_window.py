#!/usr/bin/env python3
# spec: DEV-14
# requires: cmd:git file:build/log
# After a build: no tracked file was last changed while the newest build in build/log ran. It sees only a file's last change,
# so an edit during a build that was edited again later goes unseen: the rule itself is a human check too.
import glob
import os
import re
import subprocess
import sys
from datetime import datetime

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
LOGS = os.environ.get("ASGARD_BUILD_LOGS", os.path.join(ROOT, "build", "log"))
REGENERATED = {"docs/supported-emulators.md"}  # SPEC 16, DEV-11: the build itself writes it; test_gap_emulators_doc.sh


def main():
    logs = sorted(glob.glob(os.path.join(LOGS, "build-*.log")))
    if not logs:
        sys.exit("FAIL: no build-*.log: this test needs a build's log")
    newest = logs[-1]
    stamp = re.search(r"build-(\d{8}-\d{6})\.log$", newest)
    started = datetime.strptime(stamp.group(1), "%Y%m%d-%H%M%S").timestamp()
    finished = os.path.getmtime(newest)
    files = subprocess.run(["git", "-C", ROOT, "ls-files"], capture_output=True, text=True, check=True).stdout.splitlines()
    if not files:
        sys.exit("FAIL: git listed no files: the scan is broken")
    bad = []
    for path in files:
        full = os.path.join(ROOT, path)
        if path in REGENERATED or not os.path.isfile(full):
            continue
        if started <= os.path.getmtime(full) <= finished:
            bad.append(path)
    if bad:
        sys.exit(f"FAIL: changed during the build {os.path.basename(newest)} (SPEC DEV-14): {bad[:20]}")
    print("OK")


if __name__ == "__main__":
    main()
