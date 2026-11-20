#!/usr/bin/env python3
# spec: EMU-1 EMU-3 EMU-4 EMU-5 EMU-6 GAME-8 GAME-9 GPU-2 PORT-1
# Tree checks over SPEC.md's emulator tables and the metapackage. EMU-1: the spec's and docs/emulators.md's defaults match add_emu_core (the
# systems kept from ROCKNIX: test_emulator_fork_systems.py). EMU-3: every package has its package.mk; names: test_emulator_names.py.
# EMU-4: what the spec lists is in PKG_EMUS and LIBRETRO_CORES, and PKG_EMUS's are in the spec. GAME-8: the file holds each checklist topic (the process: human).
# GAME-9: InputPlumber's Thor profile (that the raw pad is hidden: device check). GPU-2: the recipe and its version; the built tree: image.
import os
import re
import subprocess

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../.."))


def read(path):
    with open(f"{REPO}/{path}") as f:
        return f.read()


SPEC, README = read("SPEC.md"), read("docs/emulators.md")
META = read("packages/virtual/emulators/package.mk")
STANDALONE, LIBRETRO = "packages/emulators/standalone", "packages/emulators/libretro"


def metapackage():
    """PKG_EMUS, EMUS_32BIT and LIBRETRO_CORES as the build computes them for the Thor (distribution/options' ENABLE_32BIT)."""
    head = META[:META.index('case "${TARGET_TYPE}"')]
    default = re.search(r'ENABLE_32BIT="\$\{ENABLE_32BIT-(\w+)\}"', read("distribution/options")).group(1)
    out = subprocess.run(["bash", "-c", f'ARCH=aarch64; ENABLE_32BIT={default}\n{head}\necho "$PKG_EMUS"; echo "$EMUS_32BIT"; echo "$LIBRETRO_CORES"'],
                         check=True, capture_output=True, text=True).stdout.splitlines()
    return out[0].split(), out[1].split(), out[2].split()


def table(heading):
    """{first cell: second cell} of the table under this SPEC.md heading."""
    body = SPEC[SPEC.index(heading):]
    rows = {}
    for line in body.splitlines()[1:]:
        if line.startswith("#") or (rows and not line.startswith("|")):
            break
        m = re.match(r"\| (.+?) \| (.+) \|$", line)
        if m and m.group(1) not in ("System", "---"):
            rows[m.group(1)] = m.group(2)
    assert rows, heading
    return rows


emus, emus32, cores = metapackage()
core_calls = re.findall(r"^\s*add_emu_core\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)", META, re.M)
assert core_calls
defaults = {s: (e, c) for s, e, c, d in core_calls if d == "true"}

# EMU-4: the spec's lists are the metapackage's, both ways.
standalone_rows, platform_rows = table("### Standalone emulators"), table("### Platforms, apps and players")
listed = set()
for cell in standalone_rows.values():
    listed |= set(re.findall(r"[a-z][a-z0-9-]+(?=\*\*|,| \(|$)", re.sub(r"\(.*?\)", "", cell)))
listed.discard("default")
platform = set()
for cell in platform_rows.values():
    platform |= set(re.findall(r"\*\*([a-z0-9-]+)\*\*", cell))
in_image = set(emus) | {e for e in emus32 if not e.endswith("-lr")}
missing = (listed | {p for p in platform if p not in ("asgard-music", "mplayer")}) - in_image
assert not missing, f"in SPEC.md's tables but not in PKG_EMUS/EMUS_32BIT: {sorted(missing)}"
unlisted = {e for e in in_image if not re.search(rf"\b{re.escape(e)}\b", SPEC)} - {"box86"}   # box86: 32-bit x86 support, not a system's emulator
assert not unlisted, f"in PKG_EMUS but not in SPEC.md: {sorted(unlisted)}"
paragraph = SPEC[SPEC.index("The image's cores are:"):SPEC.index("- **EMU-1**")].split(":", 1)[1]
spec_cores = {c.strip().rstrip(".") for c in paragraph.replace("\n", " ").split(",")}
meta_cores = {c.removesuffix("-lr").removesuffix("_lr") for c in cores + [e for e in emus32 if e.endswith("-lr")]}
assert spec_cores <= meta_cores, f"SPEC.md's cores not in the metapackage: {sorted(spec_cores - meta_cores)}"   # the reverse: test_emulator_core_list.py

# EMU-1: a default in SPEC.md's table and docs/emulators.md's table is the one add_emu_core registers, so changing one has to
# touch both. Package and core names differ a little: dolphin-sa-gc is dolphin-sa's, OpenBOR is openbor's.
SYSTEMS = {"Nintendo 3DS": ["3ds"], "Nintendo Switch": ["switch"], "GameCube, Wii, Triforce": ["gamecube", "wii", "triforce"],
           "Wii U": ["wiiu"], "Nintendo DS": ["nds"], "PlayStation 2": ["ps2"], "PlayStation 3": ["ps3"], "PSP": ["psp"],
           "PS Vita": ["psvita"], "Dreamcast, Naomi, Atomiswave": ["dreamcast", "naomi", "atomiswave"], "Saturn": ["saturn"],
           "Xbox": ["xbox"], "Sega Model 3": ["segamodel3"], "Laserdisc": ["daphne"], "DOOM": ["doom"], "ScummVM": ["scummvm"],
           "OpenBOR": ["openbor"], "iOS": ["ios"], "Steam": ["steam"], "Heroic": ["heroic"], "Windows": ["windows"], "Ports": ["ports"],
           "Game streaming": ["moonlight"], "Music": ["music"], "Video": ["mplayer"]}
RETROARCH = {"Game Boy, Color, Advance": ["gb", "gbc", "gba"], "Nintendo 64": ["n64"], "PlayStation": ["psx"], "Atari Jaguar": ["atarijaguar"],
             "Atari ST": ["atarist"], "Amiga": ["amiga"], "Commodore": ["c64"]}
for row, cell in {**standalone_rows, **platform_rows}.items():
    if row in RETROARCH:
        assert "(default: RetroArch)" in cell, row
        for system in RETROARCH[row]:
            assert defaults[system][0] == "retroarch", (system, defaults[system])
        continue
    assert row in SYSTEMS, f"SPEC.md row with no system map here: {row}"
    bold = re.search(r"\*\*([a-z0-9-]+)\*\*", cell).group(1)
    for system in SYSTEMS[row]:
        emu, core = defaults[system]
        names = {emu.lower(), core.lower(), core.lower().rsplit("-", 1)[0]}
        assert bold in names or bold.removesuffix("-sa") in names, (row, system, bold, emu, core)
# docs/emulators.md's table says it in words, so the words each default has to show.
README_DEFAULTS = {"Game Boy / Color": [("gb", "gambatte"), ("gbc", "gambatte")], "Game Boy Advance": [("gba", "mgba")],
                   "NES / SNES": [("nes", "nestopia"), ("snes", "snes9x")], "Nintendo 64": [("n64", "mupen64plus_next")],
                   "Nintendo DS": [("nds", "melonds-sa")], "Nintendo 3DS": [("3ds", "azahar-sa")],
                   "GameCube / Wii": [("gamecube", "dolphin-sa-gc"), ("wii", "dolphin-sa-wii")], "Switch": [("switch", "eden-sa")],
                   "PlayStation 2": [("ps2", "armsx2-sa")], "PSP": [("psp", "ppsspp-sa")], "Dreamcast": [("dreamcast", "flycast-sa")],
                   "**Steam**": [("steam", "steam")]}
for row, pairs in README_DEFAULTS.items():
    assert re.search(rf"^\| {re.escape(row)} \|", README, re.M), f"docs/emulators.md lost its row: {row}"
    for system, core in pairs:
        assert defaults[system][1] == core, f"{system}'s default is {defaults[system]}: update docs/emulators.md's row {row} and this table"

# EMU-3, EMU-6: each standalone package and core has its recipe with a version. That the plan covers each: test_emulator_versions_plan.py.
plan = read("docs/plans/emulator-versions.md")
for name in re.findall(r"^\| [^|]+ \| `([\w-]+)` \|", plan, re.M):
    assert os.path.isdir(f"{REPO}/{STANDALONE}/{name}"), f"the versions plan tracks a package that's gone: {name}"
packages = sorted(os.listdir(f"{REPO}/{STANDALONE}"))
assert packages
for name in packages:
    recipe = f"{STANDALONE}/{name}/package.mk"
    assert os.path.exists(f"{REPO}/{recipe}"), recipe
    assert re.search(r'^PKG_VERSION="[^"]+"', read(recipe), re.M), f"{recipe}: no PKG_VERSION"
for core in cores:
    if core not in ("neocd_lr",):    # test_emulator_names.py holds this one
        recipe = f"{LIBRETRO}/{core}/package.mk"
        assert os.path.exists(f"{REPO}/{recipe}"), recipe
        assert re.search(r'^PKG_VERSION="[^"]+"', read(recipe), re.M), f"{recipe}: no PKG_VERSION"

# EMU-5: Settings' options come from es_features.cfg, and the image gets the catalogue (asgard's recipe) with no EmulationStation.
recipe = read("packages/asgard/package.mk")
assert re.search(r"^\s*cp \$\(get_pkg_directory emulationstation\)/config/common/es_features\.cfg \$\{INSTALL\}/usr/share/asgard/", recipe, re.M)
image = read("packages/virtual/image/package.mk")
assert not re.search(r'PKG_UI="[^"]*\bemulationstation\b', image), "EmulationStation went back into the image"

# GAME-8: the checklist has each topic the rule names.
guide = read("docs/adding-an-emulator.md")
for topic in ("Launching", "Exit codes", "Sleep: no catch-up", "In-game menu", "Back to Home", "Screens and windows", "Controller"):
    assert re.search(rf"^## \d+\. {topic}", guide, re.M), f"docs/adding-an-emulator.md lost: {topic}"
assert "docs/adding-an-emulator.md" in SPEC[SPEC.index("**GAME-8**"):][:200]

# GAME-9: InputPlumber takes the Thor's two pad sources and presents a virtual DualSense, on its own.
thor = read("device/filesystem/usr/share/inputplumber/devices/02-ayn-thor-controller.yaml")
assert re.search(r"^\s*value: AYN Thor\s*$", thor, re.M)
assert re.search(r"^\s*auto_manage: true", thor, re.M)
assert re.search(r"^target_devices:\n\s*- ds5", thor, re.M)
assert "Environment=HIDE_DEVICES_FROM_ROOT=1" in read("packages/tools/inputplumber/sources/usr/lib/systemd/system/inputplumber.service")
sources = re.findall(r"^\s*phys_path: (\S+)", thor, re.M)
assert set(sources) >= {"rsinput-gamepad/input0", "gpio-keys-ayn/input0"}, sources

# GPU-2: the extra Turnip's recipe, in the image, and the tool for users' builds.
turnip = read("packages/graphics/turnip-extra/package.mk")
assert 'PKG_VERSION="25.3.6"' in turnip and "/usr/lib/gpu-drivers/" in turnip
assert re.search(r'^PKG_DEPENDS_TARGET="[^"]*\bturnip-extra\b', recipe, re.M), "not in the image: asgard no longer depends on it"
tool = read("tools/turnip/turnip.sh")
assert re.search(r"^[^#\n]*/storage/\.config/gpu-drivers", tool, re.M)

# PORT-1: PortMaster is the only launcher registered for Ports, and it's in the image.
ports = [(e, c, d) for s, e, c, d in core_calls if s == "ports"]
assert ports == [("portmaster", "portmaster", "true")], ports
assert "portmaster" in emus
assert os.path.exists(f"{REPO}/packages/apps/portmaster/scripts/start_portmaster.sh")
print("ok")
