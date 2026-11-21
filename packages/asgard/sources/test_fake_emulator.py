# spec: GAME-1 GAME-2 GAME-4 GAME-5 GAME-6 GAME-7 GAME-10 MENU-6 OVR-3 PORT-2 XFER-3
# requires: file:build/AsgardOS-SM8550.aarch64/toolchain/usr/local/qt6/lib/libQt6Quick.so cmd:cmake
"""The fake emulator (docs/testing.md, TEST-8): Asgard Home offscreen starting a script that follows the launcher contract and
exits with any code, crashes or hangs. Home's half of each rule: GAME-1 the command line and what it does for .desktop apps;
GAME-2 Quit's signal and names from the kill data; GAME-4 playlog around the launcher (test_playlog.py: the file); GAME-6 and 7
Home's side of Back to Home and sleep (test_asgard_background.py: the freezing; audio, input and real timing: human checks);
GAME-10 the focus on the top screen; OVR-3 the chosen emulator and core reach the launcher; PORT-2 Exec= and X-Asgard-Kill=;
XFER-3 the game waiting through a standby (asgard-transfers.py: when it's sent)."""
import os
import socket
import stat
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../../tools/test"))
from home_harness import Root  # noqa: E402

FAKE = r"""#!/bin/sh
# runemu.sh's place. Its arguments and set_kill's file are the contract; $FAKE_DIR/behaviour is what this launch does.
exec >>"$FAKE_DIR/out" 2>&1   # not Home's pipes: a hung game must not hold the test's read of Home's output
{ printf 'fake'; printf '\037%s' "$@"; echo; } >>"$FAKE_DIR/trace"
[ -z "$FAKE_KILL" ] || echo "$FAKE_KILL" >"$ASGARD_KILL_DATA"
hang() { i=0; while [ $i -lt 300 ] && [ -d "$FAKE_DIR" ]; do sleep 0.1; i=$((i + 1)); done; exit 0; }
cmd() { echo "$1" >"$ASGARD_CMD_FIFO"; }
. "$FAKE_DIR/behaviour"
"""
# What Home runs around the launcher, recorded instead of done.
RECORDER = """#!/bin/sh
{ printf '%s' "${0##*/}"; printf '\\037%s' "$@"; echo; } >>"$FAKE_DIR/trace"
"""
BASH_ENV = """
python3() { "$FAKE_DIR/bin/python3" "$@"; }
swaymsg() { "$FAKE_DIR/bin/swaymsg" "$@"; }
set_kill() { "$FAKE_DIR/bin/set_kill" "$@"; }
"""
WAIT = " ".join(["up"] * 40)  # 2.4 s, ignored while the game has no menu and a no-op at the menu's top row: the fake starts in it
OPEN_GAME = "a a"             # the first system, its first game


class Rig:
    def __init__(self, root, behaviour="exit 0", kill="fake-emu", ra_port=None):
        self.root, self.dir = root, f"{root.path}/.fake"
        os.makedirs(f"{self.dir}/bin")
        self.write("runemu", FAKE, True)
        for name in ("python3", "swaymsg", "set_kill"):
            self.write(f"bin/{name}", RECORDER, True)
        self.write("bash_env", BASH_ENV)
        self.write("behaviour", behaviour + "\n")
        self.kill = kill
        self.ra_port = {"ASGARD_RA_PORT": str(ra_port)} if ra_port else {}

    def write(self, name, text, executable=False):
        path = f"{self.dir}/{name}"
        with open(path, "w") as f:
            f.write(text)
        if executable:
            os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR)

    def run(self, keys, ms=600):
        return self.root.run(keys, ms=ms, env={
            "ASGARD_RUNEMU": f"{self.dir}/runemu", "ASGARD_KILL_DATA": f"{self.dir}/kill-data",
            "ASGARD_CMD_FIFO": f"{self.dir}/cmd", "FAKE_DIR": self.dir, "FAKE_KILL": self.kill,
            "EXEC_LOG": f"{self.dir}/exec.log", "BASH_ENV": f"{self.dir}/bash_env",
            "PATH": f"{self.dir}/bin:" + os.environ["PATH"], **self.ra_port})

    def trace(self):
        """Every recorded call, in order: [program, arg, arg...]."""
        if not os.path.exists(f"{self.dir}/trace"):
            return []
        with open(f"{self.dir}/trace") as f:
            return [line.rstrip("\n").split("\x1f") for line in f]

    def launches(self):
        return [t[1:] for t in self.trace() if t[0] == "fake"]


def with_rig(keys="", ms=600, library=None, **rig):
    with Root() as r:
        r.library(library)
        fake = Rig(r, **rig)
        res = fake.run(keys, ms)
        return fake.trace(), fake.launches(), res


def udp_toggles(keys, ms, behaviour, kill):
    """How many PAUSE_TOGGLEs Home sends RetroArch's command port during this run, on a port of this test's own: another
    test's Home, or a RetroArch on this machine, uses the real one."""
    sink = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sink.bind(("127.0.0.1", 0))
    sink.settimeout(0.1)
    got, stop = [], threading.Event()

    def listen():
        while not stop.is_set():
            try:
                got.append(sink.recv(64).decode())
            except socket.timeout:
                pass

    t = threading.Thread(target=listen)
    t.start()
    try:
        with_rig(keys, ms, behaviour=behaviour, kill=kill, ra_port=sink.getsockname()[1])
        time.sleep(0.2)
    finally:
        stop.set()
        t.join()
        sink.close()
    return got.count("PAUSE_TOGGLE")


# GAME-1: the exact command line, the default emulator and core from es_systems.cfg.
_, launches, _ = with_rig(OPEN_GAME)
assert len(launches) == 1, launches
rom, *rest = launches[0]
assert rom.endswith("/storage/roms/gba/Metroid.gba"), rom
assert rest == ["-Pgba", "--core=mgba", "--emulator=retroarch", "--controllers="], rest

# OVR-3: the system's choice, then the game's, reach the launcher.
for cfg, emu, core in (('gba.emulator=alt\ngba.core=alt-gba\n', "alt", "alt-gba"),
                       ('gba.emulator=alt\ngba.core=alt-gba\ngba["Metroid.gba"].emulator=retroarch\n'
                        'gba["Metroid.gba"].core=other-mgba\n', "retroarch", "other-mgba")):
    with Root() as r:
        r.library()
        r.write("storage/.config/system/configs/system.cfg", cfg)
        fake = Rig(r)
        fake.run(OPEN_GAME)
        got = fake.launches()
        assert got and f"--emulator={emu}" in got[0] and f"--core={core}" in got[0], got

# GAME-4, GAME-10: playlog brackets the launcher with what /run/thor-playing.txt names; focus is on the top screen first.
trace, _, _ = with_rig(OPEN_GAME)
where = trace.index
focus, start, stop = ["swaymsg", "focus output DSI-2"], ["python3", "/usr/share/asgard/playlog.py", "start", rom, "gba", "retroarch",
                                                       "mgba"], ["python3", "/usr/share/asgard/playlog.py", "stop"]
game = next(t for t in trace if t[0] == "fake")
assert where(focus) < where(game) and where(start) < where(game) < where(stop), trace

# However the game ends, Home comes back and can start another: exit codes, a crash, a kill.
AGAIN = OPEN_GAME + " " + " ".join(["up"] * 12) + " a"   # a game list stays open: A starts the game again
for ending in ("exit 0", "exit 143", "exit 250", "kill -SEGV $$", "kill -KILL $$"):
    _, launches, res = with_rig(AGAIN, behaviour=ending)
    assert res.rc == 0, (ending, res.log[-400:])
    assert len(launches) == 2, (ending, launches)

# A hung game keeps its place: pressing A doesn't start a second one, and Home stays up.
_, launches, res = with_rig(AGAIN, behaviour="hang")
assert res.rc == 0 and len(launches) == 1, launches

# GAME-2: Quit game reads the signal and names from the launcher's set_kill; no signal means ask politely.
MENU = 'cmd menu; hang'
QUIT = f"{OPEN_GAME} {WAIT} down down a down a"  # Exit (after Sound and Wi-Fi and Bluetooth), then its last tile: Quit game
for kill, want in (("-9 fake-emu", "killall -9 fake-emu;"), ("fake-emu", "killall -TERM fake-emu;"),
                   ("-15 one two", "killall -15 one two;")):
    _, _, res = with_rig(QUIT, behaviour=MENU, kill=kill)
    assert f"shell: {want}" in res.log, (want, res.log[-600:])

# MENU-6: the menu's Wi-Fi and Bluetooth pages are drawn as the menu: its header and "B  back", no Settings categories.
NETWORK = f"{OPEN_GAME} {WAIT} down right a"     # Wi-Fi and Bluetooth (after Resume, Performance and Sound)
for keys, title in ((NETWORK + " a", "Wi-Fi"), (NETWORK + " left down a", "Bluetooth")):
    _, _, res = with_rig(keys, behaviour=MENU)
    shown = res.window("Asgard Home (Bottom)")
    assert title in shown and "B  back" in shown, (title, shown)
    assert not {"Settings", "General", "Hardware", "‹  Hardware"} & set(shown), (title, shown)

# GAME-6: Back to Home freezes through asgard-background.py, shows the return tile, and A on it continues the game.
TO_HOME = f"{OPEN_GAME} {WAIT} down down a a"    # Exit, then Back to Home
trace, launches, res = with_rig(TO_HOME + " b", behaviour=MENU)
assert ["python3", "/usr/share/asgard/asgard-background.py", "hide", "fake-emu"] in trace, trace
assert res.shows("Return to game"), res.texts
assert len(launches) == 1
trace, _, _ = with_rig(TO_HOME + " b left a", behaviour=MENU)
background = [t[2:] for t in trace if t[0] == "python3" and "asgard-background.py" in t[1]]
assert background == [["hide", "fake-emu"], ["show", "fake-emu"]], background

# GAME-7: the sleep hook's commands pause the game with its own pause and unpause it after, once each.
SLEEP = 'sleep 0.3; cmd sleep; sleep 0.3; cmd wake; hang'
assert udp_toggles(OPEN_GAME, 1200, SLEEP, "retroarch") == 2
# No pause known for this emulator: nothing to send.
assert udp_toggles(OPEN_GAME, 1200, SLEEP, "fake-emu") == 0
# Home only unpauses what it paused: a wake with no sleep before it does nothing.
assert udp_toggles(OPEN_GAME, 1200, 'sleep 0.3; cmd wake; hang', "retroarch") == 0
# The in-game menu already paused it: one toggle for the menu, none for the sleep or the wake.
assert udp_toggles(OPEN_GAME, 1500, 'cmd menu; sleep 0.3; cmd sleep; sleep 0.3; cmd wake; hang', "retroarch") == 1
# Frozen in the background: the menu's pause and unpause only, nothing for the sleep. RetroArch's Exit is its ninth tile.
assert udp_toggles(f"{OPEN_GAME} {WAIT} down down down down a a", 800,
                   'cmd menu; until grep -q asgard-background "$FAKE_DIR/trace"; do sleep 0.1; done; cmd sleep; sleep 0.2; cmd wake; hang',
                   "retroarch") == 2

# XFER-3: a standby pauses the game as a sleep does, and ending it early continues it; the standby turning into a sleep
# once the work's done leaves it paused through that sleep (no toggle for "sleep") and its wake continues it.
assert udp_toggles(OPEN_GAME, 1200, 'sleep 0.3; cmd standby; sleep 0.3; cmd standby-end; hang', "retroarch") == 2
assert udp_toggles(OPEN_GAME, 1500, 'sleep 0.3; cmd standby; sleep 0.2; cmd sleep; sleep 0.2; cmd wake; hang', "retroarch") == 2
assert udp_toggles(OPEN_GAME, 1200, 'sleep 0.3; cmd standby-end; hang', "retroarch") == 0   # nothing of ours to continue

# XFER-3: with no pause Home can drive, a standby freezes the game, and ending it continues it.
STANDBY = r"""cp /bin/sh "$FAKE_DIR/bin/frozen-emu"
"$FAKE_DIR/bin/frozen-emu" -c 'sleep 30 & echo $! >"$FAKE_DIR/child"; wait' & echo $! >"$FAKE_DIR/parent"
states() { for p in $(cat "$FAKE_DIR/parent" "$FAKE_DIR/child"); do awk '{printf "%s ", $3}' /proc/$p/stat; done; echo; }
sleep 0.3; cmd standby; sleep 0.6; states >"$FAKE_DIR/open"; cmd standby-end; sleep 0.6; states >"$FAKE_DIR/closed"; hang"""
with Root() as r:
    r.library()
    fake = Rig(r, behaviour=STANDBY, kill="frozen-emu")
    res = fake.run(OPEN_GAME, ms=2000)
    for n in ("parent", "child"):
        try:
            p = int(open(f"{fake.dir}/{n}").read())
            os.kill(p, 18)
            os.kill(p, 9)
        except (ProcessLookupError, OSError, ValueError):
            pass
    opened, closed = (open(f"{fake.dir}/{n}").read().split() for n in ("open", "closed"))
    assert opened == ["T", "T"], (opened, res.log[-800:])
    assert "T" not in closed and len(closed) == 2, (closed, res.log[-800:])

# GAME-5: an emulator with no pause Home can drive is frozen while the menu is open, its children too (Steam's games are),
# and continues when the menu closes (Resume, its first tile). The launcher itself isn't part of the game: it isn't frozen.
FROZEN = r"""cp /bin/sh "$FAKE_DIR/bin/frozen-emu"
"$FAKE_DIR/bin/frozen-emu" -c 'sleep 30 & echo $! >"$FAKE_DIR/child"; wait' & echo $! >"$FAKE_DIR/parent"
states() { for p in $(cat "$FAKE_DIR/parent" "$FAKE_DIR/child"); do awk '{printf "%s ", $3}' /proc/$p/stat; done; echo; }
sleep 0.3; cmd menu; sleep 1; states >"$FAKE_DIR/open"; sleep 2.2; states >"$FAKE_DIR/closed"; hang"""
with Root() as r:
    r.library()
    fake = Rig(r, behaviour=FROZEN, kill="frozen-emu")
    res = fake.run(f"{OPEN_GAME} {WAIT} a", ms=1800)
    pids = [int(open(f"{fake.dir}/{n}").read()) for n in ("parent", "child")]
    for p in pids:
        try:
            os.kill(p, 18)   # SIGCONT, then gone, whatever the test found
            os.kill(p, 9)
        except ProcessLookupError:
            pass
    opened, closed = (open(f"{fake.dir}/{n}").read().split() for n in ("open", "closed"))
    assert opened == ["T", "T"], (opened, res.log[-800:])
    assert "T" not in closed and len(closed) == 2, (closed, res.log[-800:])
    assert not r.exists("run/asgard-frozen"), "the marker outlived the menu"

# GAME-1, PORT-2: a .desktop app skips the launcher, runs its own Exec= with its output in exec.log, gets play time, and is
# named for Quit by X-Asgard-Kill=, else by the command's own name.
PC = ("<systemList><system><name>pc</name><fullname>PC</fullname><path>/storage/roms/pc</path><extension>.desktop</extension>"
      "<emulators><emulator name=\"pc\"><cores><core default=\"true\">pc</core></cores></emulator></emulators></system></systemList>")
for extra, kill in (("", "my-port"), ("X-Asgard-Kill=real-process\n", "real-process")):
    with Root() as r:
        fake = Rig(r)
        r.write("usr/config/emulationstation/es_systems.cfg", PC)
        port = f"{r.path}/my-port"
        with open(port, "w") as f:
            f.write('#!/bin/sh\necho "port ran with $1"\n')
        os.chmod(port, 0o755)
        r.write("storage/roms/pc/Game.desktop", f"[Desktop Entry]\nName=Game\nExec={port} --flag\n{extra}")
        fake.run(OPEN_GAME)
        trace = fake.trace()
        assert not fake.launches(), trace
        assert ["set_kill", "set", kill] in trace, trace
        assert ["set_kill", "stop"] in trace, trace
        assert [t[0:3] for t in trace if t[0] == "python3" and "playlog.py" in t[1]][0][2] == "start", trace
        assert "port ran with --flag" in r.read(".fake/exec.log")

# A Steam link isn't a PC app: it goes through the launcher.
with Root() as r:
    fake = Rig(r)
    r.write("usr/config/emulationstation/es_systems.cfg", PC)
    r.write("storage/roms/pc/Link.desktop", "[Desktop Entry]\nName=Link\nExec=steam steam://rungameid/1\n")
    fake.run(OPEN_GAME)
    assert len(fake.launches()) == 1, fake.trace()

# GAME-1: what a .desktop app gets from code that only exists on the Thor (host-absent paths, so read, not run): the same profile
# around it as runemu.sh's, and a crash log for an unclean end.
source = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../asgard-home/src/backend.cpp")).read()
branch = source[source.index('if (rom.endsWith(".desktop"))'):source.index("// playlog.py around ROCKNIX's runemu.sh")]
code = "\n".join(line for line in branch.splitlines() if not line.lstrip().startswith("//"))
for piece in ('asgard-perf-profile.sh apply', 'asgard-perf-profile.sh restore', 'asgard-crashlog.sh'):
    assert piece in code, piece
print("ok")
