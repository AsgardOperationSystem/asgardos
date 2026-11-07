#!/usr/bin/env python3
# spec: UPD-6
# requires: cmd:sh cmd:dd cmd:cmp cmd:sha256sum
"""updateabl against fake slots (1 MiB files with known contents): it refuses other devices and a bad image, does
nothing when both slots match, backs up both slots before asking, writes nothing without the confirmation, and flashes
abl_b then abl_a, each read back. A fake dd corrupts one slot's write to check that the bad slot gets its backup back
and the other slot is left alone. It runs under each shell the host has of sh, dash and busybox sh; busybox runs its own
dd applet whatever PATH says, so under it the checks that need the fake dd (write order, corrupted writes) are skipped."""
import hashlib
import os
import shutil
import subprocess
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "../../.."))
SCRIPT = os.path.join(REPO, "packages/asgardos/sources/scripts/updateabl")
PART = 1 << 20
ELF = bytes((i * 7 + 3) % 251 for i in range(532480))
OLD_A = bytes((i * 13 + 1) % 241 for i in range(PART))
OLD_B = bytes((i * 17 + 5) % 239 for i in range(PART))
SHELLS = [s for s in (["sh"], ["dash"], ["busybox", "sh"]) if shutil.which(s[0])]

# Logs every dd and, for the slot named in $CORRUPT, overwrites the first byte after a write of the image.
FAKE_DD = """#!/bin/sh
echo "$*" >> "$DD_LOG"
PATH=$REAL_PATH dd "$@" || exit $?
for a in "$@"; do case $a in of=*) out=${a#of=} ;; if=*) in=${a#if=} ;; esac; done
if [ -n "$CORRUPT" ] && [ "$out" = "$CORRUPT" ] && [ "$in" = "$ABL_ELF" ]; then
  printf 'X' | PATH=$REAL_PATH dd of="$out" bs=1 count=1 conv=notrunc status=none
fi
"""


def run(shell, t, model="AYN Thor", device="SM8550", a=OLD_A, b=OLD_B, sha=None, args=(), answer="flash\n",
        corrupt=None):
    for name, data in (("abl_a", a), ("abl_b", b), ("abl.elf", ELF)):
        with open(f"{t}/{name}", "wb") as f:
            f.write(data)
    with open(f"{t}/abl.elf.sha256", "w") as f:
        f.write(f"{sha or hashlib.sha256(ELF).hexdigest()}  abl_signed-SM8550.elf\n")
    with open(f"{t}/os-release", "w") as f:
        f.write(f'HW_DEVICE="{device}"\n')
    with open(f"{t}/model", "wb") as f:
        f.write(model.encode() + b"\0")
    os.makedirs(f"{t}/bin", exist_ok=True)
    with open(f"{t}/bin/dd", "w") as f:
        f.write(FAKE_DD)
    os.chmod(f"{t}/bin/dd", 0o755)
    shutil.rmtree(f"{t}/backup", ignore_errors=True)
    open(f"{t}/dd.log", "w").close()
    env = dict(os.environ, PATH=f"{t}/bin:{os.environ['PATH']}", REAL_PATH=os.environ["PATH"], DD_LOG=f"{t}/dd.log",
               CORRUPT=f"{t}/{corrupt}" if corrupt else "", ABL_OS_RELEASE=f"{t}/os-release",
               ABL_MODEL_FILE=f"{t}/model", ABL_ELF=f"{t}/abl.elf", ABL_DEV_A=f"{t}/abl_a", ABL_DEV_B=f"{t}/abl_b",
               ABL_BACKUP_ROOT=f"{t}/backup")
    env.pop("SYSTEM_ROOT", None)
    proc = subprocess.run(shell + [SCRIPT, *args], input=answer, capture_output=True, text=True, env=env, timeout=60)
    return proc


def slot(t, name):
    with open(f"{t}/{name}", "rb") as f:
        return f.read()


def backups(t):
    root = f"{t}/backup"
    return [os.path.join(root, d) for d in sorted(os.listdir(root))] if os.path.isdir(root) else []


def writes(t, name):
    """dd runs that wrote to the slot (backup restores included)."""
    return [l for l in open(f"{t}/dd.log").read().splitlines() if f"of={t}/{name} " in l + " "]


def flashed(data, old):
    return data[:len(ELF)] == ELF and data[len(ELF):] == old[len(ELF):]


def check(shell):
    name = " ".join(shell)
    hooked = shell[0] != "busybox"  # the fake dd runs
    with tempfile.TemporaryDirectory() as t:
        def untouched(proc, why):
            assert slot(t, "abl_a") == OLD_A and slot(t, "abl_b") == OLD_B, f"{name}: {why}: a slot changed"
            assert not writes(t, "abl_a") and not writes(t, "abl_b"), f"{name}: {why}: dd wrote to a slot"

        # Other devices: an SM8550 handheld that isn't a Thor, and another SoC.
        for kwargs in ({"model": "AYN Odin 2"}, {"device": "SM8250"}):
            p = run(shell, t, **kwargs)
            assert p.returncode != 0, f"{name}: {kwargs}: accepted\n{p.stdout}"
            untouched(p, kwargs)
            assert not backups(t), f"{name}: {kwargs}: backed up before refusing"

        # An image that doesn't match its checksum.
        p = run(shell, t, sha="0" * 64)
        assert p.returncode != 0 and "checksum" in p.stdout, f"{name}: bad image accepted\n{p.stdout}"
        untouched(p, "bad image")

        # Both slots already hold the image: nothing written, nothing backed up.
        a = ELF + OLD_A[len(ELF):]
        b = ELF + OLD_B[len(ELF):]
        p = run(shell, t, a=a, b=b)
        assert p.returncode == 0 and "nothing to flash" in p.stdout, f"{name}: up to date\n{p.stdout}{p.stderr}"
        assert not writes(t, "abl_a") and not writes(t, "abl_b") and not backups(t), f"{name}: up to date: wrote"

        # No confirmation: backed up, nothing written.
        for answer in ("\n", "yes\n", ""):
            p = run(shell, t, answer=answer)
            assert p.returncode != 0, f"{name}: answer {answer!r} flashed\n{p.stdout}"
            untouched(p, f"answer {answer!r}")
            assert len(backups(t)) == 1, f"{name}: answer {answer!r}: no backup before asking"

        # The confirmed flash, and --yes.
        for args, answer in (((), "flash\n"), (("--yes",), "")):
            p = run(shell, t, args=args, answer=answer)
            assert p.returncode == 0, f"{name}: {args}: failed\n{p.stdout}{p.stderr}"
            assert flashed(slot(t, "abl_a"), OLD_A) and flashed(slot(t, "abl_b"), OLD_B), f"{name}: {args}: slots"
            [backup] = backups(t)
            assert open(f"{backup}/abl_a.img", "rb").read() == OLD_A, f"{name}: abl_a backup"
            assert open(f"{backup}/abl_b.img", "rb").read() == OLD_B, f"{name}: abl_b backup"
            sums = open(f"{backup}/sha256.txt").read()
            assert hashlib.sha256(OLD_A).hexdigest() in sums and hashlib.sha256(OLD_B).hexdigest() in sums, sums
            log = open(f"{t}/dd.log").read()
            assert not hooked or log.index(f"of={t}/abl_b") < log.index(f"of={t}/abl_a"), f"{name}: abl_a written before abl_b"

        # One slot already matches: only the other one is written.
        p = run(shell, t, b=b, args=("--yes",))
        assert p.returncode == 0, f"{name}: half done\n{p.stdout}{p.stderr}"
        assert not hooked or (not writes(t, "abl_b") and len(writes(t, "abl_a")) == 1), f"{name}: half done: wrote abl_b again"
        assert slot(t, "abl_b") == b, f"{name}: half done: abl_b changed"
        assert flashed(slot(t, "abl_a"), OLD_A), f"{name}: half done: abl_a"

        if not hooked:
            return
        # abl_b doesn't read back: restored, and abl_a never written.
        p = run(shell, t, args=("--yes",), corrupt="abl_b")
        assert p.returncode != 0, f"{name}: bad abl_b passed\n{p.stdout}"
        assert slot(t, "abl_b") == OLD_B, f"{name}: abl_b not restored"
        assert slot(t, "abl_a") == OLD_A and not writes(t, "abl_a"), f"{name}: abl_a written after abl_b failed"

        # abl_a doesn't read back: restored, abl_b keeps the update.
        p = run(shell, t, args=("--yes",), corrupt="abl_a")
        assert p.returncode != 0, f"{name}: bad abl_a passed\n{p.stdout}"
        assert slot(t, "abl_a") == OLD_A, f"{name}: abl_a not restored"
        assert flashed(slot(t, "abl_b"), OLD_B), f"{name}: abl_b lost the update"


assert SHELLS, "no sh"
for shell in SHELLS:
    check(shell)
print(f"OK ({', '.join(' '.join(s) for s in SHELLS)})")
