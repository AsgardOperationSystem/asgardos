#!/usr/bin/env python3
# spec: UPD-5
# requires: cmd:git
# Tree check: nothing but the manual `updateabl` can reach abl_a/abl_b or the OpenABL image, so no update can flash them.
# It scans the whole tree, not just today's update path, because the path can grow: a script it calls, or a ROCKNIX
# cherry-pick that puts `updateabl` back in update.sh. UPD-5's boot entry layout half isn't checked here.
import os
import re
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
UPDATEABL = "packages/asgardos/sources/scripts/updateabl"

# Names that lead to the slots: the command, the partitions (abl_a, abl_b, abl_$slot, abl_${slot}), a partition label
# lookup, and the image to flash. Not abl_dev or abl_model, which are GRUB variables in distribution/config/functions.
PATTERN = (
    r"(^|[^A-Za-z0-9_])("
    r"updateabl"
    r"|abl_([ab]([^A-Za-z0-9_]|$)|\$)"
    r"|abl_signed"
    r")"
    r"|bootloader/openabl"
    r"|[Pp][Aa][Rr][Tt][Ll][Aa][Bb][Ee][Ll][=/][\"']?abl"
)

# What may name them: the command itself, and the package that ships the image without flashing it.
ALLOWED = (UPDATEABL, "packages/tools/openabl/")


def scan():
    """(path, line number, text) of each match, in tracked and new files. Build output and thor/ are git-ignored."""
    proc = subprocess.run(
        ["git", "-C", ROOT, "grep", "--untracked", "-z", "-nIE", PATTERN, "--",
         ":!*.md", ":!docs", ":!packages/asgard/sources/test_*", ":!test-device.sh", ":!tools/test"],
        capture_output=True, text=True, errors="replace")
    if proc.returncode not in (0, 1):  # 1 is no match; anything else means the scan didn't run
        sys.exit(f"FAIL: git grep failed: {proc.stderr.strip()}")
    hits = []
    for line in proc.stdout.splitlines():
        path, number, text = line.split("\0", 2)
        hits.append((path, int(number), text))
    return hits


def is_comment(text):
    return text.lstrip().startswith("#")


def main():
    hits = scan()
    # A scan that finds nothing proves nothing: it has to see the one command it knows is there.
    if not any(path == UPDATEABL and "PARTLABEL=abl_a" in text for path, _, text in hits):
        sys.exit(f"FAIL: the scan didn't find abl_a in {UPDATEABL}: it's broken, or the file moved")
    bad = [hit for hit in hits
           if not is_comment(hit[2]) and not any(hit[0] == a or (a.endswith("/") and hit[0].startswith(a))
                                                 for a in ALLOWED)]
    for path, number, text in bad:
        print(f"{path}:{number}: {text.strip()}")
    if bad:
        sys.exit("FAIL: only updateabl may reach abl_a/abl_b (SPEC UPD-5: an update never writes them)")
    print("OK")


if __name__ == "__main__":
    main()
