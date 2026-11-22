#!/usr/bin/env python3
"""Renders Asgard Home's screens on the simulated Thor (build/sim/root, from make-root.py): one PNG per window and
scene in build/sim/shots, <scene>-<window>.png. Home runs offscreen with ASGARD_SIM, so it runs no command and
answers from the root's sim/exec.json; the harness's stubs stand in for the few it calls directly, and
fake_panel.py for the Thor Panel's thor_panel.py.
    python3 -I tools/sim/shots.py [scene ...]      (default: every scene; --list names them)
ASGARD_SIM_ROOT and ASGARD_SIM_SHOTS name another root and output folder.
Each scene must show its expected text, or the run fails: test_sim_scenes.py runs them all."""
import glob
import os
import sys
import xml.etree.ElementTree as ET

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(REPO, "tools/test"))
import home_harness as hh  # noqa: E402

ROOT = os.environ.get("ASGARD_SIM_ROOT", f"{REPO}/build/sim/root")
OUT = os.environ.get("ASGARD_SIM_SHOTS", f"{REPO}/build/sim/shots")
LAVAPIPE = "/usr/share/vulkan/icd.d/lvp_icd.json"
# Qt Quick on Vulkan through lavapipe (Mesa's CPU driver): the toolchain's Qt has no OpenGL, and its software renderer
# draws no MultiEffect, which every rounded tile, the glow and the blurred backdrop are. vkkhrdisplay is the toolchain's
# one platform with Vulkan; windows are never shown (ASGARD_SHOT), so it needs no display, and input stays off.
GPU = {"QT_QPA_PLATFORM": "vkkhrdisplay", "QSG_RHI_BACKEND": "vulkan", "VK_ICD_FILENAMES": LAVAPIPE,
       "QT_QPA_DISABLE_INPUT": "1"}
HARDWARE = "start down down down down a"
NETWORK = HARDWARE + " down down down a"
# name: (button presses, Home's mode arguments, a text the scene must show)
SCENES = {
    "home": ("", (), " games"),
    "games": ("a", (), "Play"),
    "game-details": ("a select down down down a", (), "Details"),
    "trophies": ("rb rb", (), "TROPHIES"),
    "settings": ("start", (), "Device name"),
    "library": ("start down down a", (), "Consoles"),
    "hardware": (HARDWARE, (), "Calibration"),
    "display": (HARDWARE + " down a", (), "Brightness"),
    "audio": (HARDWARE + " a", (), "Speaker EQ"),
    "network": (NETWORK, (), "Connected to Asgard Wi-Fi"),
    "bluetooth": (NETWORK + " down a", (), "BT Headphones"),
    "storage": (HARDWARE + " down down down down a", (), "GB free"),
    "battery": (HARDWARE + " down down down down down a", (), "Since unplugged"),
    "about": ("start down down down down down a", (), "Version"),
    "files": ("", ("--files",), "285 GB free"),
    "panel": ("", ("--panel",), "41°C"),
    # A game in play: the top screen is the game (tools/sim/runemu.sh, <scene>-Game.png), the bottom Home's in-game
    # menu. The game is the first with a play line in the root's sim/play.tsv, else the first game of all.
    "ingame": (None, (), "Resume"),
}
COLS = 6   # tiles a row in Home's grid on the top screen


def grid_keys(index):
    return " ".join(["down"] * (index // COLS) + ["right"] * (index % COLS))


def keys_to_game():
    """The presses from Home's first tile to playing the in-game scene's game, in Home's order: consoles as
    es_systems.cfg lists them (those with games), each one's games by name (the gamelist's, else the file's)."""
    exts, order = {}, []
    for sysx in ET.parse(f"{ROOT}/usr/config/emulationstation/es_systems.cfg").getroot().findall("system"):
        name = sysx.findtext("name")
        order.append(name)
        exts[name] = {e.lower() for e in (sysx.findtext("extension") or "").split()}
    games = {}
    for system in order:
        names = {}
        gamelist = f"{ROOT}/storage/ES-DE/gamelists/{system}/gamelist.xml"
        if os.path.exists(gamelist):
            names = {g.findtext("path")[2:]: g.findtext("name") for g in ET.parse(gamelist).getroot().findall("game")
                     if g.findtext("name")}
        files = [os.path.basename(f) for f in glob.glob(f"{ROOT}/storage/roms/{system}/*")
                 if os.path.splitext(f)[1].lower() in exts[system]]
        if files:
            games[system] = sorted(files, key=lambda f: (names.get(f) or os.path.splitext(f)[0]).lower())
    systems = [s for s in order if s in games]
    play = [line.split("\t")[:2] for line in open(f"{ROOT}/sim/play.tsv", encoding="utf-8") if line.strip()] \
        if os.path.exists(f"{ROOT}/sim/play.tsv") else []
    system, file = next(((s, f) for s, f in play if f in games.get(s, [])), (systems[0], games[systems[0]][0]))
    return f"{grid_keys(systems.index(system))} a {grid_keys(games[system].index(file))} a".replace("  ", " ")


def shoot(name, ms=1500, extra=None):
    """Renders one scene; returns (missing expected text or None, Home's result)."""
    keys, args, expect = SCENES[name]
    game = {}
    if keys is None:   # the in-game scene: Home starts runemu.sh, which asks it for the menu
        keys, ms = keys_to_game(), max(ms, 6000)
        game = {"ASGARD_RUNEMU": f"{REPO}/tools/sim/runemu.sh", "ASGARD_KILL_DATA": f"{ROOT}/sim/kill-data",
                "ASGARD_CMD_FIFO": f"{ROOT}/sim/cmd"}
    if not os.path.exists(f"{ROOT}/.asgard-sim-root"):
        sys.exit(f"shots: no simulated root at {ROOT}: run tools/sim/make-root.py first")
    os.makedirs(OUT, exist_ok=True)
    root = hh.Root()
    root.path = ROOT
    env = {"ASGARD_SIM": "1", "ASGARD_SHOT": f"{OUT}/{name}-", "ASGARD_PANEL": f"{REPO}/tools/sim/fake_panel.py",
           "QT_QPA_FONTDIR": f"{ROOT}/sim/fonts", **game}
    if os.path.exists(LAVAPIPE):
        env.update(GPU)
    else:
        print(f"shots: no lavapipe ({LAVAPIPE}, Mesa's Vulkan CPU driver): software rendering, the tiles come out empty",
              file=sys.stderr)
    shown = root.run(keys, args=args, ms=ms, env={**env, **(extra or {})})
    return (None if shown.shows(expect) else expect), shown


def main(argv):
    if "--list" in argv:
        print("\n".join(SCENES))
        return 0
    names = [a for a in argv if not a.startswith("-")] or list(SCENES)
    unknown = [n for n in names if n not in SCENES]
    if unknown:
        sys.exit(f"shots: no scene {', '.join(unknown)} (--list)")
    failed = 0
    for name in names:
        missing, shown = shoot(name)
        if missing or shown.rc:
            failed += 1
            print(f"FAIL {name}: exit {shown.rc}, {missing!r} not shown; it shows: {' | '.join(shown.texts)[:600]}")
        else:
            print(f"ok   {name}")
    print(f"{OUT}: {len(names) - failed} of {len(names)} scenes")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
