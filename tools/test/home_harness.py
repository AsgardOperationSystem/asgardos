"""Runs Asgard Home on the host for test_* files (docs/testing.md, level 1): offscreen, on a fake root, against the Qt
the build left in its toolchain. Press pad buttons, then read what its windows show and what it wrote. A test using it
says `# requires: file:build/AsgardOS-SM8550.aarch64/toolchain/usr/local/qt6/lib/libQt6Quick.so cmd:cmake`."""
import fcntl
import os
import subprocess
import tempfile

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
QT = f"{REPO}/build/AsgardOS-SM8550.aarch64/toolchain/usr/local/qt6"
SRC = f"{REPO}/packages/asgard-home/src"
OUT = f"{REPO}/build/test/asgard-home"  # DEV-11: output stays under build/
CFG = "storage/.config/system/configs/system.cfg"
HOST_COMMANDS = ("systemctl", "reboot", "poweroff", "shutdown", "halt", "swaymsg", "ledcontrol", "rfkill", "nmcli", "iwctl",
                 "bluetoothctl", "pw-play", "pactl", "wpctl", "suspendmode", "killall", "pkill", "kill-game",
                 "busctl", "pidof")


def binary():
    """Builds Home if its source changed. Tests may run at the same time, so one builds while the others wait."""
    os.makedirs(OUT, exist_ok=True)
    with open(f"{OUT}.lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if not os.path.exists(f"{OUT}/Makefile"):
            subprocess.run(["cmake", "-S", SRC, "-B", OUT, f"-DCMAKE_PREFIX_PATH={QT}", "-DCMAKE_BUILD_TYPE=Debug",
                            f"-DQT_HOST_PATH={QT}"], check=True, capture_output=True)
        subprocess.run(["cmake", "--build", OUT, "-j4"], check=True, capture_output=True)
    return f"{OUT}/asgard-home"


class Result:
    def __init__(self, rc, log, dump):
        self.rc, self.log = rc, log
        self.lines = [line.split("\t", 2) for line in dump.splitlines() if line.count("\t") >= 2]
        self.texts = [text for _, kind, text in self.lines if kind == "text"]
        self.props = dict(text.split("=", 1) for _, kind, text in self.lines if kind == "prop" and "=" in text)

    def window(self, title):
        """The texts showing in the window with this title."""
        return [text for win, kind, text in self.lines if kind == "text" and win == title]

    def shows(self, text):
        return any(text in shown for shown in self.texts)


class Root:
    """A fake filesystem root for ASGARD_ROOT, deleted when the `with` ends."""

    def __enter__(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = self._tmp.name
        self.write(CFG, "system.hostname=TEST\n")
        return self

    def library(self, games=None):
        """Two systems with games and one without, for Home's scan: {system: [rom names]}, with mgba and melonds as
        each system's default. Home reads the image's es_systems.cfg, so this is /usr/config's, not /storage's."""
        games = games if games is not None else {"gba": ["Metroid.gba", "Zelda.gba"], "nds": ["Mario.nds"]}
        systems = ""
        for name, emulator, core in (("gba", "retroarch", "mgba"), ("nds", "melonds", "melonds-sa"),
                                     ("snes", "retroarch", "snes9x")):
            systems += (f"<system><name>{name}</name><fullname>{name.upper()} console</fullname>"
                        f"<path>/storage/roms/{name}</path><extension>.{name} .zip</extension>"
                        f"<emulators><emulator name=\"{emulator}\"><cores><core default=\"true\">{core}</core>"
                        f"<core>other-{core}</core></cores></emulator><emulator name=\"alt\"><cores><core>alt-{name}"
                        f"</core></cores></emulator></emulators></system>")
            os.makedirs(f"{self.path}/storage/roms/{name}", exist_ok=True)
        self.write("usr/config/emulationstation/es_systems.cfg", f"<systemList>{systems}</systemList>")
        for name, roms in games.items():
            for rom in roms:
                self.write(f"storage/roms/{name}/{rom}", "rom")

    def __exit__(self, *_):
        self._tmp.cleanup()

    def write(self, name, text=""):
        path = f"{self.path}/{name}"
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(text)

    def read(self, name):
        with open(f"{self.path}/{name}") as f:
            return f.read()

    def exists(self, name):
        return os.path.exists(f"{self.path}/{name}")

    def run(self, keys="", args=(), env=None, ms=800, timeout=60):
        """Starts Home, presses `keys` ("right a b", names as in Gamepad), waits ms, returns what it shows."""
        dump = f"{self.path}/.dump"
        full = {"PATH": os.environ["PATH"], "HOME": self.path, "LANG": "C.UTF-8", "LD_LIBRARY_PATH": f"{QT}/lib",
                "QT_PLUGIN_PATH": f"{QT}/plugins", "QML_IMPORT_PATH": f"{QT}/qml", "QML2_IMPORT_PATH": f"{QT}/qml",
                "QT_QPA_PLATFORM": "offscreen", "QT_FORCE_STDERR_LOGGING": "1", "ASGARD_ROOT": self.path,
                "ASGARD_HOME_QML": f"{SRC}/qml", "ASGARD_SHOT": f"{self.path}/.shot-", "ASGARD_SHOT_MS": str(ms),
                "ASGARD_KEYS": keys, "ASGARD_DUMP": dump,
                "ASGARD_PANEL": f"{REPO}/packages/asgard/sources/thor_panel.py", **(env or {})}
        # Home runs some commands directly (X stops a systemd service). Nothing it starts may reach this machine.
        stubs = f"{self.path}/.stubs"
        os.makedirs(stubs, exist_ok=True)
        for name in HOST_COMMANDS:
            with open(f"{stubs}/{name}", "w") as f:
                f.write("#!/bin/sh\nexit 0\n")
            os.chmod(f"{stubs}/{name}", 0o755)
        full["PATH"] = f"{full['PATH']}:{stubs}" if env and "PATH" in env else f"{stubs}:{full['PATH']}"
        proc = subprocess.run([binary(), *args], env=full, capture_output=True, text=True, timeout=timeout,
                              errors="replace")
        text = ""
        if os.path.exists(dump):
            with open(dump, errors="replace") as f:
                text = f.read()
        return Result(proc.returncode, proc.stdout + proc.stderr, text)
