# spec: DEV-11 DEV-16
# requires: file:build/AsgardOS-SM8550.aarch64/toolchain/usr/local/qt6/lib/libQt6Quick.so cmd:cmake
"""Run: python -I test_sim_root.py  (no Thor, no network): tools/sim/make-root.py, the simulated Thor's root, from a
game list or placeholders. It never cleans a folder it didn't make, a rebuild keeps the scraped art, its settings carry
nothing personal (DEV-16), and Asgard Home finds every game in the list on it, with Recently played and the battery."""
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "../../.."))
sys.path.insert(0, os.path.join(REPO, "tools/test"))
from home_harness import CFG, Root  # noqa: E402

MAKE = os.path.join(REPO, "tools/sim/make-root.py")


def make(out, library):
    return subprocess.run([sys.executable, "-I", MAKE, "--out", out], capture_output=True, text=True,
                          env={**os.environ, "ASGARD_SIM_LIBRARY": library})


with tempfile.TemporaryDirectory() as tmp:
    # Your own list (tab-separated, # comments) wins; without one, placeholders: four games in each of 9 consoles
    mine = f"{tmp}/mine.tsv"
    rows = [("snes", "Game A (USA).sfc"), ("gba", "Game B.gba"), ("nds", "Game C.nds"), ("nds", "Game D.nds"),
            ("3ds", "Game E.3ds"), ("n64", "Game F.z64"), ("ps2", "Game G.iso")]
    open(mine, "w").write("# mine\n" + "".join(f"{s}\t{n}\n" for s, n in rows))
    r = make(f"{tmp}/placeholders", f"{tmp}/none.tsv")
    assert r.returncode == 0 and "36 games in 9 consoles" in r.stdout, r

    # A folder it didn't make is left alone, whatever is in it
    other = f"{tmp}/other"
    os.makedirs(other)
    open(f"{other}/keep", "w").close()
    r = make(other, mine)
    assert r.returncode != 0 and "refusing" in r.stderr, r
    assert os.listdir(other) == ["keep"]

    root = f"{tmp}/root"
    r = make(root, mine)
    assert r.returncode == 0, r.stderr
    for system, name in rows:   # every game is an empty stub
        assert os.path.getsize(f"{root}/storage/roms/{system}/{name}") == 0, name
    cfg = open(f"{root}/{CFG}").read()
    for secret in ("password", "wifi.key", "wifi.ssid", "username", "token"):   # DEV-16
        assert secret not in cfg, secret

    # A rebuild clears what it made but keeps the scraped art
    art = f"{root}/storage/ES-DE/downloaded_media/snes/covers/x.png"
    os.makedirs(os.path.dirname(art))
    open(art, "w").close()
    open(f"{root}/storage/roms/snes/stray.sfc", "w").close()
    assert make(root, mine).returncode == 0
    assert os.path.exists(art) and not os.path.exists(f"{root}/storage/roms/snes/stray.sfc")

    # Home on it: every console and game, Recently played, the battery
    home = Root()
    home.path = root
    shown = home.run("")
    systems = len({system for system, _ in rows})
    assert f"library: {systems} systems, {len(rows)} games, 5 recently played" in shown.log, shown.log
    assert shown.shows("78%"), shown.texts

print("ok")
