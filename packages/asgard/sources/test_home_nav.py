# spec: HOME-1 HOME-2 HOME-3 HOME-4 HOME-5 HOME-6 OLED-1
# requires: file:build/AsgardOS-SM8550.aarch64/toolchain/usr/local/qt6/lib/libQt6Quick.so cmd:cmake
"""Run: python -I test_home_nav.py  (no Thor): Asgard Home's browsing, offscreen on a fake root, driven by pad presses.
HOME-1: the buttons, and the pad decoding table for A east, B south; holding L+R as one press is a human check.
HOME-2: tabs, the return tile, systems without games; Recently played is test_home_recently_played.py (a known gap).
HOME-5, HOME-2's return tile: a game can't run on a host, so a QML copy has backend.background return one."""
import os
import shutil
import stat
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "../../../tools/test"))
import home_harness as hh  # noqa: E402
from home_harness import CFG, Root  # noqa: E402

BG = '({ path: "/storage/roms/nds/Mario.nds", name: "Mario", sys: "nds" })'


def qml_copy(root, edits):
    """Home's QML with exact edits, {file: [(old, new)]}: an old that isn't there fails the test."""
    out = f"{root.path}/.qml"
    shutil.rmtree(out, ignore_errors=True)
    shutil.copytree(f"{hh.SRC}/qml", out)
    for name, pairs in edits.items():
        text = open(f"{out}/{name}").read()
        for old, new in pairs:
            assert old in text, old
            text = text.replace(old, new)
        open(f"{out}/{name}", "w").write(text)
    return {"ASGARD_HOME_QML": out}


bin_dir = tempfile.mkdtemp()
calls = f"{bin_dir}/calls"
for tool in ("swaymsg", "systemctl", "ledcontrol"):   # never the host's: X runs these
    path = f"{bin_dir}/{tool}"
    open(path, "w").write(f'#!/bin/sh\necho "{tool} $*" >> {calls}\n')
    os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC)
PATH = {"PATH": f"{bin_dir}:{os.environ['PATH']}"}


def called(wanted):
    """Home starts these detached: give them a moment."""
    for _ in range(40):
        if os.path.exists(calls) and wanted in open(calls).read():
            return True
        time.sleep(0.05)
    return False


def press(root, keys, env=None):
    return root.run(keys, env={**PATH, **(env or {})}, ms=300)


def cfg(root, key):
    values = [line.split("=", 1)[1] for line in root.read(CFG).splitlines() if line.startswith(key + "=")]
    return values[-1] if values else None


# ---- HOME-1: the buttons
with Root() as r:
    r.library()
    assert press(r, "a").props["openSys"] == "gba"                    # A opens
    back = press(r, "a b")
    assert back.props["openSys"] == "" and back.shows("GBA")          # B goes back
    assert press(r, "y").props["reordering"] == "true"                # Y reorders
    assert press(r, "start").shows("Appearance")                      # Start: Settings
    game = press(r, "a start")                                        # in a game list: that game's page
    assert game.shows("Emulator options") and game.shows("This game only; unset ones follow GBA console")
    assert press(r, "a select").shows("Scrape this game")             # Select: the game's actions
    assert press(r, "a select down down a").shows("Emulator options")  # Select > Game settings: its page
    assert [press(r, k).props["tab"] for k in ("rb", "rb rb", "rb rb rb", "lb")] == ["1", "2", "0", "2"]   # LB/RB
    swapped = press(r, "").props["swapped"]
    assert press(r, "lr").props["swapped"] != swapped                 # L+R swaps, and it's saved
    assert cfg(r, "asgard.swap_screens") == ("0" if swapped == "true" else "1")
    assert press(r, "").props["swapped"] != swapped

gamepad = open(os.path.join(HERE, "../../asgard-home/src/backend.cpp")).read()
for pair in ('{BTN_EAST, "a"}', '{BTN_SOUTH, "b"}', '{BTN_NORTH, "x"}', '{BTN_WEST, "y"}'):  # the Thor's Nintendo layout
    assert pair in gamepad, pair

# ---- OLED-1: X turns both screens off; any button then only wakes them
with Root() as r:
    r.library()
    press(r, "x")
    assert called("swaymsg output DSI-2 power off, output DSI-1 power off")
    os.remove(calls)
    woken = press(r, "x a")
    assert called("swaymsg output DSI-2 power on, output DSI-1 power on")
    assert woken.props["openSys"] == ""                               # A didn't open the tile
    assert press(r, "x rb").props["tab"] == "0"
    assert not press(r, "x start").shows("Appearance")
    assert press(r, "x a a").props["openSys"] == "gba"                # awake: A works again

# ---- HOME-2: the tabs, and only systems with games
with Root() as r:
    r.library()
    home = r.run("").window("Asgard Home")
    assert "GBA" in home and "NDS" in home and "SNES" not in home     # home: the snes system has no games
    consoles = r.run("rb").window("Asgard Home")
    assert "GBA" in consoles and "NDS" in consoles and "SNES" not in consoles
    assert r.run("rb rb").shows("Add your RetroAchievements username")  # trophies
    tile = {"Main.qml": [("const bg = backend.background        //", f"const bg = {BG}        //")]}
    returning = r.run("", env=qml_copy(r, tile))
    assert returning.shows("Return to game")
    assert not r.run("").shows("Return to game")

# ---- HOME-3: es_systems.cfg, the ROM directories and ES-DE's media; art on the tiles, details and play time on the card
with Root() as r:
    r.library({"gba": ["Metroid.gba", "notes.txt"]})                  # .txt isn't in es_systems.cfg's extensions
    media = "storage/ES-DE/downloaded_media/gba"
    r.write(f"{media}/covers/Metroid.png", "x")
    r.write(f"{media}/screenshots/Metroid.png", "x")
    r.write("storage/ES-DE/gamelists/gba/gamelist.xml", "<gameList><game><path>./Metroid.gba</path><name>Metroid Fusion</name>"
            "<desc>Samus on station.</desc><developer>Nintendo</developer></game></gameList>")
    r.write("storage/.config/thor/playtime.jsonl",
            '{"rom": "/storage/roms/gba/Metroid.gba", "sys": "gba", "start": 1700000000, "secs": 5400}\n')
    listed = r.run("a")
    assert listed.shows("Metroid Fusion") and not listed.shows("notes")
    assert listed.props["art"].endswith(f"{media}/screenshots/Metroid.png")  # the card and the backdrop
    # What the tile's own cover Image loads, read back through a label inside it.
    art = {"Tile.qml": [("source: !tile.near ? \"\" : visible ? (tile.game.cover",
                         "Text { text: 'cover=' + parent.source }\n            source: !tile.near ? \"\" : visible ? (tile.game.cover")]}
    assert any(t.startswith("cover=") and t.endswith(f"{media}/covers/Metroid.png") for t in r.run("a", env=qml_copy(r, art)).texts)
    card = r.run("a select down down down a")                         # Select > Details
    assert card.shows("Samus on station.") and card.shows("Played 1 h 30 min")

# ---- HOME-4: tile order, saved; B cancels
with Root() as r:
    r.library()
    assert r.run("").window("Asgard Home").index("GBA") < r.run("").window("Asgard Home").index("NDS")
    cancelled = r.run("y right b")
    assert cancelled.props["reordering"] == "false" and cfg(r, "asgard.order") is None
    assert cancelled.window("Asgard Home").index("GBA") < cancelled.window("Asgard Home").index("NDS")
    r.run("y right a")
    assert cfg(r, "asgard.order") == "nds,gba"
    after = r.run("").window("Asgard Home")                            # a new start: the saved order
    assert after.index("NDS") < after.index("GBA")
    assert r.run("right a").props["openSys"] == "gba"                 # per console too (GBA is the second tile now)
    r.run("right a y right a")
    assert cfg(r, "asgard.order.gba") == "Zelda.gba|Metroid.gba"
    games = r.run("right a").window("Asgard Home")
    assert games.index("Zelda") < games.index("Metroid")
    assert cfg(r, "asgard.order") == "nds,gba"                        # one console's order leaves the rest alone

# ---- HOME-5: another game while one waits in the background asks first and warns
with Root() as r:
    r.library()
    assert "launch /storage/roms/gba/Metroid.gba" in r.run("a a").log  # nothing waits: it just starts
    waiting = {"Main.qml": [("const bg = backend.background, g = current.game", f"const bg = {BG}, g = current.game"),
                            ("pendingLaunch = g; backend.quitGame()", "pendingLaunch = g; console.log('QUIT')")]}
    env = qml_copy(r, waiting)
    asked = r.run("a a", env=env)
    assert asked.shows("unsaved progress is lost") and asked.shows("Close Mario?")
    assert "launch " not in asked.log and "QUIT" not in asked.log
    cancelled = r.run("a a b", env=env)
    assert not cancelled.shows("unsaved progress is lost") and "QUIT" not in cancelled.log and "launch " not in cancelled.log
    assert "QUIT" in r.run("a a a", env=env).log                      # "Close it" closes the waiting game first

# ---- HOME-6: the on-screen power button opens Sleep, Restart and Power off
with Root() as r:
    r.library()
    assert not r.run("").shows("Power off")
    tap = {"Main.qml": [("TapHandler { onTapped: { backend.sound(\"open\"); powerMenuPanel.anchorRight",
                         "TapHandler { id: powerTap; onTapped: { backend.sound(\"open\"); powerMenuPanel.anchorRight"),
                        ("Component.onCompleted: if (debugInput) console.log(\"input: debug logging on (bottom window)\")",
                         "Component.onCompleted: powerTap.tapped(undefined, Qt.LeftButton)")]}
    env = qml_copy(r, tap)
    menu = r.run("", env=env)
    assert all(menu.shows(item) for item in ("Sleep", "Restart", "Power off")), menu.log
    assert "shell: systemctl suspend" in r.run("a", env=env).log

shutil.rmtree(bin_dir)
print("ok")
