#!/usr/bin/env python3
"""Renders Asgard Home's screens on the simulated Thor (build/sim/root, from make-root.py): one PNG per window and
scene in build/sim/shots, <scene>-<window>.png. Home runs offscreen with ASGARD_SIM, so it runs no command and
answers from the root's sim/exec.json; the harness's stubs stand in for the few it calls directly, and
fake_panel.py for the Thor Panel's thor_panel.py.
    python3 -I tools/sim/shots.py [scene ...]      (default: every scene; --list names them)
ASGARD_SIM_ROOT and ASGARD_SIM_SHOTS name another root and output folder.
Each scene must show its expected text, or the run fails: test_sim_scenes.py runs them all."""
import os
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(REPO, "tools/test"))
import home_harness as hh  # noqa: E402

ROOT = os.environ.get("ASGARD_SIM_ROOT", f"{REPO}/build/sim/root")
OUT = os.environ.get("ASGARD_SIM_SHOTS", f"{REPO}/build/sim/shots")
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
}


def shoot(name, ms=1500):
    """Renders one scene; returns (missing expected text or None, Home's result)."""
    keys, args, expect = SCENES[name]
    if not os.path.exists(f"{ROOT}/.asgard-sim-root"):
        sys.exit(f"shots: no simulated root at {ROOT}: run tools/sim/make-root.py first")
    os.makedirs(OUT, exist_ok=True)
    root = hh.Root()
    root.path = ROOT
    shown = root.run(keys, args=args, ms=ms, env={"ASGARD_SIM": "1", "ASGARD_SHOT": f"{OUT}/{name}-",
                                                    "ASGARD_PANEL": f"{REPO}/tools/sim/fake_panel.py"})
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
