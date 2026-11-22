#!/usr/bin/env python3
"""Builds the simulated Thor's /storage and /usr for Asgard Home on the host (ASGARD_ROOT), so its screens can be
rendered without a Thor. Nothing comes from a real device: the games are empty stubs, named in library.local.tsv
(git-ignored, as it says what is in a library; ASGARD_SIM_LIBRARY names another) or placeholders without one; the
settings carry no account, network or password; the system files are the build's own.
    python3 -I tools/sim/make-root.py [--art] [--out DIR]
DIR defaults to build/sim/root (DEV-11). The image must be built: the systems list, the theme's console art and Home's
media come from build/AsgardOS-SM8550.aarch64/install_pkg. --art scrapes covers, screenshots and details from libretro
(asgard-scrape.py, by name, no account) for games that have none; they're kept across rebuilds, under storage/ES-DE."""
import glob
import importlib.util
import json
import os
import shutil
import sys
import time

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PKG = f"{REPO}/build/AsgardOS-SM8550.aarch64/install_pkg"
CFG = "storage/.config/system/configs/system.cfg"
KEEP = "storage/ES-DE"   # scraped art: slow to fetch, kept across rebuilds
MARK = ".asgard-sim-root"
# Recently played, newest first: (hours ago, minutes played) for the first game of the first five consoles
PLAYED = [(2, 48), (26, 135), (50, 92), (75, 61), (120, 210)]
LOCAL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "library.local.tsv")
# Without your own list: placeholder games, a few per console, named so nobody mistakes them for real ones
PLACEHOLDERS = {"snes": ".sfc", "gba": ".gba", "n64": ".z64", "nds": ".nds", "3ds": ".3ds", "psx": ".chd",
                "ps2": ".iso", "gamecube": ".rvz", "switch": ".nsp"}


def built(pattern):
    """The one file or dir in the build's install_pkg matching pattern; stops with a hint if the image isn't built."""
    found = sorted(glob.glob(f"{PKG}/{pattern}"))
    if not found:
        sys.exit(f"make-root: {PKG}/{pattern} is missing: build the image first (./build.sh)")
    return found[-1]


def library(path=None):
    """[(system, file name)]: the list at path (default library.local.tsv, git-ignored: it names a real library) if
    there is one, else placeholders."""
    path = path or os.environ.get("ASGARD_SIM_LIBRARY", LOCAL)
    if not os.path.exists(path):
        return [(system, f"Sample {system.upper()} Game {n}{ext}") for system, ext in PLACEHOLDERS.items()
                for n in range(1, 5)]
    games = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip() and not line.startswith("#"):
                system, name = line.rstrip("\n").split("\t")
                games.append((system, name))
    return games


def played(games):
    """Recently played: the first game of each of the first five consoles."""
    firsts = {}
    for system, name in games:
        firsts.setdefault(system, name)
    return [(s, n, hours, minutes) for (s, n), (hours, minutes) in zip(firsts.items(), PLAYED)]


def write(root, name, text=""):
    path = f"{root}/{name}"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def build(root, games):
    os.makedirs(root, exist_ok=True)
    if os.listdir(root) and not os.path.exists(f"{root}/{MARK}"):   # only ever clean a root this script made
        sys.exit(f"make-root: {root} isn't empty and isn't a simulated root ({MARK} missing): refusing to clean it")
    for entry in os.listdir(root):   # a clean root each time, but for the scraped art
        if entry != "storage":
            shutil.rmtree(f"{root}/{entry}") if os.path.isdir(f"{root}/{entry}") and not os.path.islink(
                f"{root}/{entry}") else os.remove(f"{root}/{entry}")
    if os.path.isdir(f"{root}/storage"):
        for entry in os.listdir(f"{root}/storage"):
            if f"storage/{entry}" != KEEP:
                path = f"{root}/storage/{entry}"
                shutil.rmtree(path) if os.path.isdir(path) and not os.path.islink(path) else os.remove(path)

    write(root, MARK, "Built by tools/sim/make-root.py; rebuilding it deletes everything here but storage/ES-DE.\n")
    # The image's files Home reads: the systems list, the theme's console art, Home's own media (Tools)
    os.makedirs(f"{root}/usr/config/emulationstation")
    shutil.copy(built("emulators-*/usr/config/emulationstation/es_systems.cfg"), f"{root}/usr/config/emulationstation/")
    os.makedirs(f"{root}/usr/share/asgard-home")
    os.symlink(built("es-theme-art-book-next-*/usr/share/themes"), f"{root}/usr/share/themes")
    os.symlink(built("asgard-home-*/usr/share/asgard-home/media"), f"{root}/usr/share/asgard-home/media")

    for system, name in games:   # empty stubs: Home lists a game by its file name
        write(root, f"storage/roms/{system}/{name}")
    write(root, CFG, "system.hostname=Thor\n")
    now = time.time()
    write(root, "storage/.config/thor/playtime.jsonl", "".join(
        json.dumps({"rom": f"/storage/roms/{s}/{n}", "sys": s, "start": now - hours * 3600, "secs": minutes * 60}) + "\n"
        for s, n, hours, minutes in played(games)))
    # A battery on its own power: 78 %, discharging, no charger
    write(root, "sys/class/power_supply/battery/capacity", "78\n")
    write(root, "sys/class/power_supply/battery/status", "Discharging\n")
    write(root, "sys/class/power_supply/qcom-battmgr-usb/online", "0\n")


def art(root, games):
    """Covers, screenshots and details from libretro, by name, for games that have no cover yet."""
    spec = importlib.util.spec_from_file_location("asgard_scrape", f"{REPO}/packages/asgard/sources/asgard-scrape.py")
    scrape = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(scrape)
    scrape.ROOT, scrape.CFG = f"{root}/{KEEP}", f"{root}/{CFG}"
    scrape.INDEX = built("asgard-*/usr/share/asgard/scrape-index")
    for system, name in games:
        stem = os.path.splitext(name)[0]
        media = f"{scrape.ROOT}/downloaded_media/{system}"
        if glob.glob(f"{media}/covers/{glob.escape(stem)}.*"):
            continue
        try:
            r = scrape.libretro(system, f"{root}/storage/roms/{system}/{name}", stem, media)
        except scrape.Offline:
            sys.exit("make-root: no internet connection: --art needs raw.githubusercontent.com")
        print(f"{system}/{name}: " + (f"{r['matched']} ({', '.join(r['media']) or 'details only'})" if r else "no match"))


def main(argv):
    out = f"{REPO}/build/sim/root"
    if "--out" in argv:
        out = os.path.abspath(argv[argv.index("--out") + 1])
    games = library()
    build(out, games)
    if "--art" in argv:
        art(out, games)
    print(f"{out}: {len(games)} games in {len({s for s, _ in games})} consoles")


if __name__ == "__main__":
    main(sys.argv[1:])
