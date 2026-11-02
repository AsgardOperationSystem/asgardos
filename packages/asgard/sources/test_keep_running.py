#!/usr/bin/env python3
# spec: BAT-3
# requires: cmd:bash cmd:setsid cmd:flock cmd:timeout
# sleep_mode=screen, through the real scripts with their paths in a temp dir and fake system tools: asgard-perf-profile.sh holds the
# inhibitor and marker for the game's run only, power-handler hands the power key and lid to asgard-screens-off.sh, which turns the
# screens off and doesn't suspend or stop the game. That music keeps playing is a human check.
import os
import re
import subprocess
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
HANDLER = f"{HERE}/../../hardware/quirks/platforms/SM8550/bin/power-handler"
RECORD = '#!/bin/sh\n{ printf "%s" "${0##*/}"; printf " %s" "$@"; echo; } >>"$T/calls"\n'
OUTPUTS = '[{"name":"DSI-2","power":true},{"name":"DSI-1","power":false}]'
LIB = """TYPES="little mid prime"
autotune_stop() { :; }; autotune_start() { :; }; online_type() { :; }; set_cap() { :; }; set_gpu_cap() { :; }
offline_types() { :; }; write_affinity() { :; }
"""


def rewrite(path, t):
    paths = {". /etc/profile.d/001-functions": f". {t}/functions", ". /etc/profile": f". {t}/functions",
             ". /usr/share/asgard/asgard-cpu-lib.sh": f". {t}/lib", "/usr/share/asgard/": f"{t}/asgard/", "/usr/bin/": f"{t}/bin/",
             "/run/": f"{t}/run/", "/storage/": f"{t}/storage/"}
    with open(path) as f:
        return re.sub("|".join(map(re.escape, paths)), lambda m: paths[m.group(0)], f.read())


class Fixture:
    def __enter__(self):
        self._tmp = tempfile.TemporaryDirectory()
        t = self.t = self._tmp.name
        for d in ("asgard", "bin", "run", "storage/.config/system/configs"):
            os.makedirs(f"{t}/{d}")
        self.write("functions", f'get_setting() {{ [ "$1" = sleep_mode ] && cat "{t}/sleep_mode" 2>/dev/null; [ "$1" = sleep_bt ] && cat "{t}/sleep_bt" 2>/dev/null; [ "$1" = asgard.sleep_bt ] && cat "{t}/os_sleep_bt" 2>/dev/null; [ "$1" = system.suspendmode ] && echo off; }}\n'
                                f'export PATH="{t}/bin:$PATH"\n')
        self.write("lib", LIB)
        self.write("storage/.config/system/configs/system.cfg", "")
        for tool in ("systemctl", "ledcontrol", "rfkill", "bluetoothctl", "asgardos-fake-suspend"):
            self.write(f"bin/{tool}", RECORD, True)
        for tool in ("asgard-cpu-cap.sh",):
            self.write(f"asgard/{tool}", RECORD, True)
        self.write("bin/swaymsg", f'#!/bin/sh\ncase "$*" in *get_outputs*) echo \'{OUTPUTS}\' ;; *get_inputs*) echo "[]" ;; *) echo "swaymsg $*" >>"{t}/calls" ;; esac\n', True)
        self.write("bin/systemd-inhibit", f'#!/bin/sh\necho "systemd-inhibit $*" >>"{t}/calls"\nexec sleep 30\n', True)
        self.write("asgard/asgard-perf-profile.sh", rewrite(f"{HERE}/asgard-perf-profile.sh", t), True)
        self.write("asgard/asgard-screens-off.sh", rewrite(f"{HERE}/asgard-screens-off.sh", t), True)
        self.write("power-handler", rewrite(HANDLER, t), True)
        return self

    def __exit__(self, *_):
        try:
            os.kill(int(self.read("run/asgard-keep-running.pid")), 9)
        except (OSError, ValueError):
            pass
        self._tmp.cleanup()

    def write(self, name, text, executable=False):
        with open(f"{self.t}/{name}", "w") as f:
            f.write(text)
        if executable:
            os.chmod(f"{self.t}/{name}", 0o755)

    def read(self, name):
        with open(f"{self.t}/{name}") as f:
            return f.read()

    def has(self, name):
        return os.path.exists(f"{self.t}/{name}")

    def run(self, script, *args):
        subprocess.run(["bash", f"{self.t}/{script}", *args], check=False, capture_output=True, timeout=30,
                       env={"PATH": os.environ["PATH"], "T": self.t})
        calls = self.read("calls").splitlines() if self.has("calls") else []
        if self.has("calls"):
            os.remove(f"{self.t}/calls")
        return calls


# A game without it: no marker, no inhibitor, and the power key goes on to the normal path.
with Fixture() as f:
    calls = f.run("asgard/asgard-perf-profile.sh", "apply", "music", "Song.mp3")
    assert not f.has("run/asgard-keep-running") and not any("systemd-inhibit" in c for c in calls), calls
    calls = f.run("power-handler", "power")
    assert calls and calls[0].startswith("asgardos-fake-suspend"), calls
    assert not f.has("run/asgard-screens-off.active")

# sleep_mode=screen: the marker and the inhibitor for the game's run, and gone with it.
with Fixture() as f:
    f.write("sleep_mode", "screen\n")
    calls = f.run("asgard/asgard-perf-profile.sh", "apply", "music", "Song.mp3")
    assert f.read("run/asgard-keep-running") == "music\tSong.mp3\n"
    for _ in range(50):
        if any("systemd-inhibit" in c for c in calls):
            break
        subprocess.run(["sleep", "0.02"])
        calls += f.run("asgard/asgard-cpu-cap.sh")
    assert any("--what=sleep:handle-lid-switch" in c and "--mode=block" in c for c in calls), calls
    pid = int(f.read("run/asgard-keep-running.pid"))
    os.kill(pid, 0)

    # The power key: the screens that were lit go off and nothing suspends; a second press brings them back.
    calls = f.run("power-handler", "power")
    assert "swaymsg -q output DSI-2 power off" in calls and "swaymsg -q output DSI-1 power off" not in calls, calls
    assert f.has("run/asgard-screens-off.active")
    assert not any("suspend" in c for c in calls), calls
    calls = f.run("power-handler", "power")
    assert "swaymsg -q output DSI-2 power on, output DSI-2 dpms on" in calls, calls
    assert not f.has("run/asgard-screens-off.active")

    # The lid does the same.
    calls = f.run("power-handler", "lid", "close")
    assert "swaymsg -q output DSI-2 power off" in calls and not any("suspend" in c for c in calls), calls
    calls = f.run("power-handler", "lid", "open")
    assert "swaymsg -q output DSI-2 power on, output DSI-2 dpms on" in calls, calls

    # The game ends with the screens off: they come back, the marker and inhibitor go.
    f.run("power-handler", "power")
    calls = f.run("asgard/asgard-perf-profile.sh", "restore")
    assert "swaymsg -q output DSI-2 power on, output DSI-2 dpms on" in calls, calls
    assert not f.has("run/asgard-keep-running")
    for _ in range(50):
        try:
            os.kill(pid, 0)
        except OSError:
            break
        subprocess.run(["sleep", "0.02"])
    else:
        raise AssertionError("the inhibitor outlived the game")


def keep_running(f, bt="off"):
    f.write("run/asgard-keep-running", "music\tSong.mp3\n")
    f.write("sleep_bt", bt + "\n")


# Set to stay on: the radio isn't touched, so headphones keep playing.
with Fixture() as f:
    keep_running(f, "on")
    assert not any("rfkill block" in c for c in f.run("power-handler", "lid", "close"))

# Unset, it takes Settings > Performance; the game's own wins over that.
with Fixture() as f:
    keep_running(f, "")
    f.write("os_sleep_bt", "off\n")
    assert "rfkill block bluetooth" in f.run("power-handler", "lid", "close")
with Fixture() as f:
    keep_running(f, "on")
    f.write("os_sleep_bt", "off\n")
    assert not any("rfkill block" in c for c in f.run("power-handler", "lid", "close"))

# Set off: down with the screens, back with them.
with Fixture() as f:
    keep_running(f)
    assert "rfkill block bluetooth" in f.run("power-handler", "lid", "close")
    assert "rfkill unblock bluetooth" in f.run("power-handler", "lid", "open")

# What was connected reconnects once the radio's up, and only if the radio was taken down.
BLUETOOTHCTL = RECORD + '''case "$1" in
  devices) echo "Device AA:BB:CC:DD:EE:FF WH-1000XM4" ;;
  show) cat "$T/powered" ;;
esac
'''


def connects(f, wait=3.0):
    """The connect calls recorded within `wait` seconds, for what runs on after the script has returned."""
    end = time.monotonic() + wait
    while time.monotonic() < end:
        if f.has("calls") and "connect" in f.read("calls"):
            subprocess.run(["sleep", "0.1"])
            break
        subprocess.run(["sleep", "0.05"])
    return [c for c in (f.read("calls") if f.has("calls") else "").splitlines() if " connect " in c]


with Fixture() as f:
    keep_running(f)
    f.write("bin/bluetoothctl", BLUETOOTHCTL, True)
    f.write("powered", "Powered: yes\n")
    f.run("power-handler", "lid", "close")
    assert "bt=AA:BB:CC:DD:EE:FF" in f.read("run/asgard-screens-off.active")
    opened = f.run("power-handler", "lid", "open")   # it may already have connected by the time this returns
    assert [c for c in opened if " connect " in c] + connects(f) == ["bluetoothctl -- connect AA:BB:CC:DD:EE:FF"]
with Fixture() as f:                                   # kept on: nothing to reconnect
    keep_running(f, "on")
    f.write("bin/bluetoothctl", BLUETOOTHCTL, True)
    f.write("powered", "Powered: yes\n")
    f.run("power-handler", "lid", "close")
    f.run("power-handler", "lid", "open")
    assert connects(f, 1) == []
with Fixture() as f:                                   # waits for the radio, and the screens going off again ends it
    keep_running(f)
    f.write("bin/bluetoothctl", BLUETOOTHCTL, True)
    f.write("powered", "Powered: no\n")
    f.run("power-handler", "lid", "close")
    f.run("power-handler", "lid", "open")
    assert connects(f, 1) == []
    f.run("power-handler", "lid", "close")
    f.write("powered", "Powered: yes\n")
    assert connects(f, 2) == []

# A block that fails partway still comes back (2026-11-02: Bluetooth stayed off after the lid opened, and Connect failed).
with Fixture() as f:
    keep_running(f)
    f.write("bin/rfkill", RECORD + 'case "$1" in block) exit 1 ;; esac\n', True)
    f.run("power-handler", "lid", "close")
    assert "rfkill unblock bluetooth" in f.run("power-handler", "lid", "open")

# A lid opened while the close is still working waits for it, so what the close turned off comes back after.
with Fixture() as f:
    keep_running(f)
    f.write("bin/rfkill", RECORD + 'case "$1" in block) sleep 1; echo "block done" >>"$T/calls" ;; esac\n', True)
    closing = subprocess.Popen(["bash", f"{f.t}/power-handler", "lid", "close"], env={"PATH": os.environ["PATH"], "T": f.t})
    for _ in range(200):
        if f.has("calls") and "rfkill block" in f.read("calls"):
            break
        subprocess.run(["sleep", "0.02"])
    calls = f.run("power-handler", "lid", "open")
    closing.wait(timeout=30)
    assert "rfkill unblock bluetooth" in calls and calls.index("block done") < calls.index("rfkill unblock bluetooth"), calls
    assert not f.has("run/asgard-screens-off.active")

# What the script leaves running doesn't keep the lock: the next lid or power press isn't held up for it.
with Fixture() as f:
    keep_running(f)
    f.write("asgard/asgard-cpu-cap.sh", RECORD + "sleep 5 >/dev/null 2>&1 &\n", True)
    f.run("power-handler", "lid", "close")
    f.run("power-handler", "lid", "open")
    start = time.monotonic()
    f.run("power-handler", "lid", "close")
    assert time.monotonic() - start < 3, "a child held the lock"
print("ok")
