#!/usr/bin/env python3
"""Builds the simulated Thor's /storage and /usr for Asgard Home on the host (ASGARD_ROOT), so its screens can be
rendered without a Thor. Nothing comes from a real device: the games are empty stubs, named in library.local.tsv
(git-ignored, as it says what is in a library; ASGARD_SIM_LIBRARY names another) or placeholders without one, but
for a real ROM the list may name to copy and play (see real_roms); the
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
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

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
                system, name = line.rstrip("\n").split("\t")[:2]
                games.append((system, name))
    return games


def real_roms(path=None):
    """{(system, file name): (ROM to copy, play script)} from the list's optional third and fourth columns: a real ROM
    copied in place of the stub (it stays in this machine's build/), and "<frames> button@first-last ..." for
    tools/sim/runemu.sh, which plays it that far for the top screen of an in-game screenshot."""
    path = path or os.environ.get("ASGARD_SIM_LIBRARY", LOCAL)
    out = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                cols = line.rstrip("\n").split("\t")
                if not line.startswith("#") and len(cols) >= 3 and cols[2]:
                    out[(cols[0], cols[1])] = (cols[2], cols[3] if len(cols) > 3 else "600")
    return out


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

    real = real_roms()
    for system, name in games:   # empty stubs: Home lists a game by its file name; real ROMs where the list names one
        if (system, name) in real:
            os.makedirs(f"{root}/storage/roms/{system}", exist_ok=True)
            shutil.copy(os.path.expanduser(real[(system, name)][0]), f"{root}/storage/roms/{system}/{name}")
        else:
            write(root, f"storage/roms/{system}/{name}")
    write(root, "sim/play.tsv", "".join(f"{s}\t{n}\t{play}\n" for (s, n), (_, play) in real.items()))
    write(root, CFG, "system.hostname=Thor\nwifi.enabled=1\nbluetooth.enabled=1\n")
    write(root, "sim/exec.json", answers())
    write(root, "sim/space", "285 GB free of 476 GB\n")   # Files' free space (the answers' df for /storage)
    # The image's fonts, flat (QT_QPA_FONTDIR isn't searched recursively): symbols Home's own font lacks, as on the Thor
    os.makedirs(f"{root}/sim/fonts")
    for font in sorted(glob.glob(f"{REPO}/build/AsgardOS-SM8550.aarch64/image/system/usr/share/fonts/**/*.[ot]tf",
                                 recursive=True)):
        if not os.path.exists(f"{root}/sim/fonts/{os.path.basename(font)}"):
            os.symlink(font, f"{root}/sim/fonts/{os.path.basename(font)}")
    release = f"{REPO}/build/AsgardOS-SM8550.aarch64/image/system/etc/os-release"   # Settings > About: the build's
    write(root, "etc/os-release", open(release).read() if os.path.exists(release) else 'OS_NAME="AsgardOS"\n')
    now = time.time()
    write(root, "storage/.config/thor/playtime.jsonl", "".join(
        json.dumps({"rom": f"/storage/roms/{s}/{n}", "sys": s, "start": now - hours * 3600, "secs": minutes * 60}) + "\n"
        for s, n, hours, minutes in played(games)))
    # A battery on its own power: 78 %, discharging, no charger
    write(root, "sys/class/power_supply/battery/capacity", "78\n")
    write(root, "sys/class/power_supply/battery/status", "Discharging\n")
    write(root, "sys/class/power_supply/qcom-battmgr-usb/online", "0\n")


def answers():
    """sim/exec.json: what each command Home asks (Settings, the in-game menu) answers on the simulated Thor, in the
    format its parser reads. First match wins; anything else answers "". Home runs none of them (ASGARD_SIM)."""
    now = int(time.time())
    kernel = os.path.basename(built("linux-[0-9]*")).split("-", 1)[1]
    versions = subprocess.run([f"{REPO}/scripts/emulator-versions"], capture_output=True, text=True).stdout
    battery = {"now": {"pct": 78, "charging": False, "ma": 610, "hours_left": 6.4},
               "session": {"start": now - 4 * 3600, "from_pct": 100, "to_pct": 78, "hours": 4.0, "activities": [
                   {"name": "Sample game", "hours": 1.6, "pct": 12, "ma": 690},
                   {"name": "Home", "hours": 0.7, "pct": 4, "ma": 480},
                   {"name": "Sleep", "hours": 1.7, "pct": 1, "ma": 24}]}}
    eq = {"speaker": "thor", "headphones": "thor", "saved": [], "tone": {"speaker": [0, 0, 0], "headphones": [0, 0, 0]}}
    df = lambda path, dev, kind, total, used, mount: \
        f"{path} {dev} {kind} {total} {used} {total - used} {used * 100 // total}% {mount}"
    storage = "\n".join([df("/storage", "/dev/sda15", "ext4", 467_000_000, 182_000_000, "/storage"),
                         df("/storage/games-external", "/dev/mmcblk0p1", "exfat", 487_000_000, 301_000_000, "/storage/games-external"),
                         df("/flash", "/dev/sda14", "vfat", 2_096_000, 610_000, "/flash"),
                         df("/storage/roms", "/dev/sda15", "ext4", 467_000_000, 182_000_000, "/storage")])
    rows = [(r"nmcli -t -f DEVICE,STATE,CONNECTION dev", "wlan0:connected:Asgard Wi-Fi"),
            (r"^ip -4 -o addr show wlan0", "192.168.1.42"),
            (r"^usbgadget", "disabled"),
            (r"^uname -r", kernel),
            (r"emulator-versions", versions),
            (r"asgard-eq\.py status", json.dumps(eq)),
            (r"battery-report\.py", json.dumps(battery)),
            (r"df -PkT", storage),
            (r"^asgardos-bluetooth list", '<device id="00:00:5E:00:53:01" name="BT Headphones" connected="yes" '
                                         'type="audio-headset" battery="80" codec="LDAC" codecs="SBC AAC LDAC"/>'),
            (r"^asgardos-bluetooth scan_list", '<device id="00:00:5E:00:53:02" name="8BitDo Ultimate 2C" connected="no" '
                                              'type="input-gaming"/>'),
            (r"^wifictl list", "Asgard Wi-Fi\nValhalla 5G\nBifrost"),
            (r"asgard-update\.py", "{}"),
            (r"asgard-transfers\.py", "{}"),
            (r"asgard-library\.py", json.dumps({"paired": 0})),
            (r"(tailscale|zerotier).* -j |status --json", "{}"),
            (r"/usr/share/zoneinfo/", "Africa/Cairo\nAmerica/New_York\nAsia/Tokyo\nEurope/Berlin\nEurope/London")]
    return json.dumps([{"match": m, "out": o} for m, o in rows], indent=1)


def art(root, games):
    """Covers, screenshots and details from libretro, by name, for games without a cover (an image) or a name yet."""
    spec = importlib.util.spec_from_file_location("asgard_scrape", f"{REPO}/packages/asgard/sources/asgard-scrape.py")
    scrape = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(scrape)
    scrape.ROOT, scrape.CFG = f"{root}/{KEEP}", f"{root}/{CFG}"
    scrape.INDEX = built("asgard-*/usr/share/asgard/scrape-index")
    named = set()   # (system, "./file") with a <name> already: scraped before
    for gamelist in glob.glob(f"{scrape.ROOT}/gamelists/*/gamelist.xml"):
        system = os.path.basename(os.path.dirname(gamelist))
        for game in ET.parse(gamelist).getroot().findall("game"):
            if (game.findtext("name") or "").strip():
                named.add((system, game.findtext("path")))
    for system, name in games:
        stem = os.path.splitext(name)[0]
        media = f"{scrape.ROOT}/downloaded_media/{system}"
        covers = glob.glob(f"{media}/covers/{glob.escape(stem)}.*")
        real = covers and open(covers[0], "rb").read(4) in (b"\x89PNG", b"\xff\xd8\xff\xe0", b"\xff\xd8\xff\xe1")
        if real and (system, "./" + name) in named:   # an image, not a saved libretro link, and a name: done
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
