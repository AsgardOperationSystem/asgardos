#!/usr/bin/env python3
# spec: SET-6
# Tree check of scripts/emulator-versions, the list Settings > About > Emulators shows: versions come from package.mk,
# a tag in a trailing comment wins over the commit, a bare commit shows 7 chars, and only installed packages are listed.
import os
import re
import subprocess
import tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../.."))
SCRIPT = f"{ROOT}/scripts/emulator-versions"


def run(*args):
    out = subprocess.run([SCRIPT, *args], capture_output=True, text=True, check=True).stdout
    return dict(line.split("\t") for line in out.splitlines())


def pkg_version(pkg):
    mk = open(f"{ROOT}/packages/emulators/standalone/{pkg}/package.mk").read()
    return re.search(r'^PKG_VERSION="([^"]*)"', mk, re.M).group(1)


every = run()
assert every, "no emulators listed"
assert all(v for v in every.values()), every
# a sha with "# tag v0.2.1": the tag; with "#v148": v148
assert every["Eden"] == "v0.2.1" and every["ares"] == "v148", every
# a plain version stays as it is; a bare sha is shortened
assert every["ScummVM"] == pkg_version("scummvm-sa"), every
assert every["Vita3K"] == "commit " + pkg_version("vita3k-sa")[:7], every
# mupen64plus-sa is a meta package: its core's version, not the meta's 1.0
assert every["Mupen64Plus"] != "1.0", every
assert "RetroArch" in every and "Steam" not in every and "heroic" not in every, every
# no raw 40-char sha leaks through
assert not [v for v in every.values() if re.fullmatch(r"[0-9a-f]{40}", v)], every

# With the image's stamps: only what was installed
with tempfile.TemporaryDirectory() as stamps:
    for pkg in ("azahar-sa", "mupen64plus-sa", "retroarch", "linux"):
        os.mkdir(f"{stamps}/{pkg}")
    assert sorted(run(stamps)) == ["Azahar", "Mupen64Plus", "RetroArch"], run(stamps)
