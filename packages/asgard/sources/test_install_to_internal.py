#!/usr/bin/env python3
# spec: UPD-7
# requires: cmd:bash cmd:awk cmd:sort
"""installtointernal on a fake disk: parted, sgdisk, mount, umount, mkfs and blockdev are stubs over a JSON partition
table and a mount list, and /flash, /storage and /tmp are rewritten into a temp dir. A reinstall over an earlier
Linux install unmounts the old partitions (as ROCKNIX auto-mounts STORAGE at /storage/roms and games-external) and
removes them. Anything that would leave a half-removed table stops it before the first partition goes: a mount
that won't unmount, the running system on one of them, a failed parted rm. With "preserve userdata", the new boot
partition starts after userdata's last byte, also when userdata ends exactly on a MiB boundary. Real partitioning is
a device step."""
import json
import os
import re
import subprocess
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "../../.."))
SCRIPT = os.path.join(REPO, "packages/asgardos/sources/scripts/installtointernal")
ROOTED = re.compile(r'(?<![\w.$/}-])/(flash|storage|tmp)(?=[/\s"\':]|$)', re.M)
MIB = 1 << 20

PARTED = r'''#!/usr/bin/env python3
import json, os, sys
state = os.environ["FAKE_GPT"]
gpt = json.load(open(state))
open(os.environ["FAKE_LOG"], "a").write("parted " + " ".join(sys.argv[1:]) + "\n")
args = [a for a in sys.argv[1:] if a not in ("-m", "-s")]
if args[:2] == ["-a", "optimal"]:
    args = args[2:]
dev, cmd, rest = args[0], args[1], args[2:]
mib = lambda v: int(v[:-3]) << 20 if v.endswith("MiB") else None
if cmd == "unit":
    rest = rest[1:]; cmd = rest[0]
if cmd == "print":
    print("BYT;")
    for p in sorted(gpt["parts"], key=lambda p: p["n"]):
        print(f'{p["n"]}:{p["start"]}B:{p["end"]}B:{p["end"] - p["start"] + 1}B::{p["name"]}:;')
elif cmd == "rm":
    n = int(rest[0])
    mounted = any(l.startswith(f"{dev}{n} ") for l in open(os.environ["FAKE_MOUNTS"]))
    if n in gpt.get("rm_fails", []) or mounted:
        sys.exit("Error: Partition(s) on /dev/sda are being used.")
    gpt["parts"] = [p for p in gpt["parts"] if p["n"] != n]
elif cmd == "mkpart":
    start = mib(rest[2])
    end = gpt["size"] - 1 if rest[3] == "100%" else mib(rest[3]) - 1
    for p in gpt["parts"]:
        if start <= p["end"] and end >= p["start"]:
            sys.exit("Error: You requested a partition from ... The closest location we can manage is ...")
    n = min(set(range(1, 129)) - {p["n"] for p in gpt["parts"]})
    gpt["parts"].append({"n": n, "start": start, "end": end, "name": ""})
elif cmd == "name":
    for p in gpt["parts"]:
        if p["n"] == int(rest[0]):
            p["name"] = rest[1]
json.dump(gpt, open(state, "w"))
'''

MOUNT = r'''#!/bin/sh
echo "mount $*" >> "$FAKE_LOG"
if [ $# = 0 ]; then cat "$FAKE_MOUNTS"; else echo "$1 on $2 type auto (rw)" >> "$FAKE_MOUNTS"; fi
'''

UMOUNT = r'''#!/bin/sh
echo "umount $*" >> "$FAKE_LOG"
for a in "$@"; do
  if grep -qxF "$a" "$FAKE_BUSY" 2>/dev/null; then echo "umount: $a: target is busy." >&2; exit 32; fi
  grep -q -e "^$a " -e " on $a type " "$FAKE_MOUNTS" || { echo "umount: $a: not mounted." >&2; exit 32; }
  grep -v -e "^$a " -e " on $a type " "$FAKE_MOUNTS" > "$FAKE_MOUNTS.new"; mv "$FAKE_MOUNTS.new" "$FAKE_MOUNTS"
done
'''

LOGGED = '''#!/bin/sh
echo "$(basename "$0") $*" >> "$FAKE_LOG"
case "$(basename "$0") $1" in "sgdisk -p") echo "Partition table holds up to 128 entries" ;; esac
case "$(basename "$0")" in blockdev) echo 0 ;; esac
'''

USERDATA_START = 1 << 30
# Ends exactly on a MiB boundary (sector 10346495 on the Thor = 40416 MiB): parted's end is the last byte, inclusive.
USERDATA_END = 40416 * MIB - 1
DISK = 238 << 30


def old_install():
    """Android's 16 partitions (parted gives a new one the first free number), userdata, and an earlier install."""
    return [{"n": n, "start": n * MIB, "end": (n + 1) * MIB - 1, "name": f"android{n}"} for n in range(1, 17)] + [
        {"n": 17, "start": USERDATA_START, "end": USERDATA_END, "name": "userdata"},
        {"n": 18, "start": 40416 * MIB, "end": 42464 * MIB - 1, "name": "ASGARDOS"},
        {"n": 19, "start": 42464 * MIB, "end": DISK - 1, "name": "STORAGE"},
    ]


def run(t, parts, mounts=(), busy=(), rm_fails=(), answers="y\nY\nn\n"):
    for d in ("flash", "storage", "tmp", "bin"):
        os.makedirs(f"{t}/{d}", exist_ok=True)
    open(f"{t}/flash/KERNEL", "w").write("kernel")
    json.dump({"size": DISK, "parts": parts, "rm_fails": list(rm_fails)}, open(f"{t}/gpt.json", "w"))
    open(f"{t}/mounts", "w").write("".join(f"{dev} on {mp} type ext4 (rw)\n" for dev, mp in mounts))
    open(f"{t}/busy", "w").write("".join(f"{b}\n" for b in busy))
    open(f"{t}/log", "w").close()
    for name, text in (("parted", PARTED), ("mount", MOUNT), ("umount", UMOUNT), ("sgdisk", LOGGED),
                       ("mkfs.vfat", LOGGED), ("mkfs.ext4", LOGGED), ("blockdev", LOGGED), ("dd", LOGGED), ("rmdir", LOGGED)):
        with open(f"{t}/bin/{name}", "w") as f:
            f.write(text)
        os.chmod(f"{t}/bin/{name}", 0o755)
    script = ROOTED.sub(lambda m: f"{t}/{m.group(1)}", open(SCRIPT).read())
    with open(f"{t}/installtointernal", "w") as f:
        f.write(script)
    env = dict(os.environ, PATH=f"{t}/bin:{os.environ['PATH']}", HW_DEVICE="SM8550", FAKE_GPT=f"{t}/gpt.json",
               FAKE_LOG=f"{t}/log", FAKE_MOUNTS=f"{t}/mounts", FAKE_BUSY=f"{t}/busy")
    proc = subprocess.run(["bash", f"{t}/installtointernal"], input=answers, capture_output=True, text=True, env=env,
                          timeout=60)
    gpt = json.load(open(f"{t}/gpt.json"))["parts"]
    return proc, {p["n"]: p for p in gpt}, open(f"{t}/log").read()


def check_refused(proc, parts, log, why):
    assert proc.returncode != 0, f"{why}: went on\n{proc.stdout}"
    assert sorted(parts)[16:] == [17, 18, 19], f"{why}: partitions removed: {sorted(parts)}\n{proc.stdout}{proc.stderr}"
    assert "mkpart" not in log and "mkfs" not in log, f"{why}: made partitions\n{log}"


with tempfile.TemporaryDirectory() as t:
    # A reinstall over a ROCKNIX-style install that auto-mounted STORAGE for the games: it unmounts and removes.
    proc, parts, log = run(t, old_install(), mounts=[("/dev/sda19", "/storage/games-external"),
                                                     ("/dev/sda19", "/storage/roms")])
    assert proc.returncode == 0, f"reinstall failed\n{proc.stdout}{proc.stderr}\n{log}"
    assert "umount /storage/roms" in log and "umount /storage/games-external" in log, log
    assert [parts[n]["name"] for n in (17, 18, 19)] == ["userdata", "ASGARDOS", "STORAGE"], parts
    # Preserve userdata: userdata kept, the boot partition right after its last byte, no overlap.
    assert parts[17]["end"] == USERDATA_END, "userdata changed"
    assert parts[18]["start"] == USERDATA_END + 1, f"ASGARDOS starts at {parts[18]['start']}, not after userdata"

    # The same with no mounts.
    proc, parts, log = run(t, old_install())
    assert proc.returncode == 0 and sorted(parts)[16:] == [17, 18, 19], f"plain reinstall\n{proc.stdout}{proc.stderr}"

    # A mount that won't go: nothing removed.
    proc, parts, log = run(t, old_install(), mounts=[("/dev/sda19", "/storage/roms")], busy=["/storage/roms"])
    check_refused(proc, parts, log, "busy mount")

    # Run from the internal install itself: /storage and /flash are the partitions it would remove.
    proc, parts, log = run(t, old_install(), mounts=[("/dev/sda18", f"{t}/flash"), ("/dev/sda19", f"{t}/storage")])
    check_refused(proc, parts, log, "running from internal")
    assert "umount" not in log, f"running from internal: unmounted the running system\n{log}"

    # parted can't remove one: stop, and say so.
    proc, parts, log = run(t, old_install(), rm_fails=[18])
    assert proc.returncode != 0, f"failed rm: went on\n{proc.stdout}"
    assert "mkpart" not in log, f"failed rm: made partitions\n{log}"
    assert "18" in proc.stdout + proc.stderr, f"failed rm: no message naming it\n{proc.stdout}{proc.stderr}"

    # Declined: nothing touched.
    proc, parts, log = run(t, old_install(), answers="n\n")
    assert proc.returncode == 0 and sorted(parts)[16:] == [17, 18, 19], "declined"
    assert not re.search(r"^parted .* rm ", log, re.M), f"declined: removed\n{log}"

print("OK")
