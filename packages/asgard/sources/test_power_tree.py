#!/usr/bin/env python3
# spec: PWR-9 LOG-3
# Tree checks. PWR-9, only the part the tree shows: nothing arms a wake from sleep except asgard-charge-fix, whose reason is
# stopping at the charge limit (its header), and 999-lid-reopened, which sets a 2 s alarm only when the lid was opened
# again while the Thor was going down, so it cancels that sleep or wakes it (PWR-13); its post hook only clears it. What really wakes a sleep and redraw are a device and a human check.
# LOG-3, the wiring: systemd-coredump keeps dumps as files, on /storage. That a crash leaves one is a human check.
import os
import re

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
ALLOWED = {"packages/asgard/sleep.d/asgard-charge-fix",
           "packages/hardware/quirks/platforms/SM8550/sleep.d/pre/999-lid-reopened",
           "packages/hardware/quirks/platforms/SM8550/sleep.d/post/000-lid-reopened"}
ARMS_WAKE = re.compile(r"\brtcwake\b|\bwakealarm\b|^\s*WakeSystem\s*=\s*(true|yes|1)", re.M)
found = []
for top in ("packages", "device", "distribution"):
    for d, dirs, files in os.walk(os.path.join(ROOT, top)):
        rel_d = os.path.relpath(d, ROOT)
        dirs[:] = [x for x in dirs if os.path.join(rel_d, x) != "packages/linux/src" and x not in ("__pycache__", ".git")]
        for name in files:
            rel = os.path.join(rel_d, name)
            if name.startswith("test_") or rel in ALLOWED:
                continue
            try:
                if os.path.getsize(os.path.join(d, name)) > 1 << 20:
                    continue
                text = open(os.path.join(d, name), errors="ignore").read()
            except OSError:
                continue
            if ARMS_WAKE.search(text):
                found.append(rel)
assert not found, f"these arm a wake from sleep, with no stated reason in this test: {found}"

conf = open(os.path.join(ROOT, "packages/asgard/coredump.conf.d/20-asgard.conf")).read()
assert re.search(r"^Storage=external$", conf, re.M), "core dumps aren't kept as files"
assert re.search(r"^ProcessSizeMax=[1-9]", conf, re.M) and re.search(r"^ExternalSizeMax=[1-9]", conf, re.M), "core dumps are dropped"
cores = open(os.path.join(ROOT, "packages/asgard/system.d/asgard-cores.service")).read()
assert re.search(r"^ExecStart=.*mount --bind /storage/\.cache/cores /var/lib/systemd/coredump", cores, re.M), "core dumps aren't on /storage"
print("ok")
