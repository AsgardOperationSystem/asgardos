#!/usr/bin/env python3
# spec: OVR-2 OVR-4 PERF-3
# requires: cmd:bash cmd:flock cmd:timeout
"""Back to Home and back, through the real scripts with their paths in a temp dir and fake system tools: the menu's profile while
the game waits frozen, the game's again before it continues. That the clocks really move is a device check."""
import os
import re
import subprocess
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = open(f"{HERE}/../../asgard-home/src/backend.cpp").read()
RECORD = '#!/bin/sh\n{ printf "%s" "${0##*/}"; printf " %s" "$@"; echo; } >>"$T/calls"\n'
LIB = """TYPES="little mid prime"
rec() { echo "$*" >>"$T/calls"; }
autotune_stop() { rec autotune_stop; }; autotune_start() { rec autotune_start "$@"; sleep 5 >/dev/null 2>&1 & }
online_type() { :; }; set_cap() { rec set_cap "$@"; }; set_gpu_cap() { rec set_gpu_cap "$@"; }
offline_types() { :; }; write_affinity() { :; }
"""
FUNCTIONS = """get_setting() { case "$1" in cpu_cap_mid) echo 60 ;; cpu_cap_prime) cat "$T/prime" 2>/dev/null ;; gpu_cap) echo 50 ;; fan_mode) echo 200 ;;
  asgard.fan_manual) sed -n 's/^asgard.fan_manual=//p' "$T/storage/.config/system/configs/system.cfg" ;;
  top_*|bottom_*) [ -n "$2" ] && sed -n "s/^$1=//p" "$T/game" 2>/dev/null ;;
  *) sed -n "s/^$1=//p" "$T/storage/.config/system/configs/system.cfg" ;; esac; }
export PATH="$T/bin:$PATH"
"""


class Fixture:
    def __enter__(self):
        self._tmp = tempfile.TemporaryDirectory()
        t = self.t = self._tmp.name
        for d in ("asgard", "bin", "run", "storage/.config/system/configs", "sys/module/panel_chipone_icna35xx/parameters"):
            os.makedirs(f"{t}/{d}")
        self.write("functions", FUNCTIONS)
        self.write("lib", LIB)
        self.write("storage/.config/system/configs/system.cfg", "asgard.fan_manual=128\n")
        self.write("run/asgard-perf.saved", "")
        for tool in ("systemctl", "ledcontrol", "rfkill", "bluetoothctl", "brightness", "pidof"):
            self.write(f"bin/{tool}", RECORD, True)
        self.write("asgard/asgard-cpu-cap.sh", RECORD, True)
        self.write("bin/swaymsg", RECORD + 'case "$*" in *get_*) echo "[]" ;; esac\n', True)
        for name in ("asgard-perf-profile.sh", "asgard-screens-off.sh"):
            self.write(f"asgard/{name}", self.rewrite(f"{HERE}/{name}"), True)
        return self

    def __exit__(self, *_):
        self._tmp.cleanup()

    def rewrite(self, path):
        t = self.t
        paths = {". /etc/profile.d/001-functions": f". {t}/functions", ". /usr/share/asgard/asgard-cpu-lib.sh": f". {t}/lib",
                 "/usr/share/asgard/": f"{t}/asgard/", "/run/": f"{t}/run/", "/storage/": f"{t}/storage/", "/sys/module/": f"{t}/sys/module/"}
        return re.sub("|".join(map(re.escape, paths)), lambda m: paths[m.group(0)], open(path).read())

    def write(self, name, text, executable=False):
        with open(f"{self.t}/{name}", "w") as f:
            f.write(text)
        if executable:
            os.chmod(f"{self.t}/{name}", 0o755)

    def read(self, name):
        return open(f"{self.t}/{name}").read()

    def has(self, name):
        return os.path.exists(f"{self.t}/{name}")

    def run(self, script, *args):
        subprocess.run(["bash", f"{self.t}/asgard/{script}", *args], check=False, capture_output=True, timeout=30,
                       env={"PATH": os.environ["PATH"], "T": self.t})
        calls = [c.strip() for c in self.read("calls").splitlines()] if self.has("calls") else []
        if calls:
            os.remove(f"{self.t}/calls")
        return calls

    def fan(self):
        return re.findall(r"^asgard\.fan_manual=(.*)$", self.read("storage/.config/system/configs/system.cfg"), re.M)


PROFILE = "asgard-perf-profile.sh"

# The round trip: the menu's in Home, the game's again on return, and the fan with them.
with Fixture() as f:
    f.run(PROFILE, "game", "3ds", "Zelda.3ds")                  # as apply leaves it: the game's fan on
    assert f.fan() == ["200"]
    calls = f.run(PROFILE, "home")
    assert "asgard-cpu-cap.sh" in calls and not any(c.startswith("set_cap") for c in calls), calls
    assert f.has("run/asgard-perf.home") and f.fan() == ["128"] and not f.has("run/asgard-perf.saved.fan")
    calls = f.run(PROFILE, "game", "3ds", "Zelda.3ds")
    assert "set_cap mid 60" in calls and "set_gpu_cap 50" in calls and "asgard-cpu-cap.sh" not in calls, calls
    assert not f.has("run/asgard-perf.home") and f.fan() == ["200"]

    # A game that's quit from Home restores as usual, and leaves no marker behind.
    f.run(PROFILE, "home")
    f.write("bin/python3", "#!/bin/sh\n", True)
    f.run(PROFILE, "restore")
    assert not f.has("run/asgard-perf.home") and not f.has("run/asgard-perf.saved")

# No game's profile on (it ended meanwhile): neither does anything.
with Fixture() as f:
    os.remove(f"{f.t}/run/asgard-perf.saved")
    assert f.run(PROFILE, "home") == [] and f.run(PROFILE, "game", "3ds", "Zelda.3ds") == []
    assert not f.has("run/asgard-perf.home")

# Screens back on in Home with a game waiting: the menu's profile, not the game's.
with Fixture() as f:
    f.write("run/asgard-keep-running", "music\tSong.mp3\n")
    f.write("run/asgard-screens-off.active", "")
    f.run(PROFILE, "home")
    calls = f.run("asgard-screens-off.sh", "lid", "open")
    assert "asgard-cpu-cap.sh" in calls and not any(c.startswith("set_cap") for c in calls), calls
    # And with the game on screen, the game's.
    f.run(PROFILE, "game", "music", "Song.mp3")
    f.write("run/asgard-screens-off.active", "")
    assert "set_cap mid 60" in f.run("asgard-screens-off.sh", "lid", "open")

# Autotune outlives the script, and doesn't keep the lock: going back to Home isn't held up for it.
with Fixture() as f:
    f.write("prime", "autotune\n")
    f.run(PROFILE, "game", "3ds", "Zelda.3ds")
    start = time.monotonic()
    f.run(PROFILE, "home")
    assert time.monotonic() - start < 3, "autotune held the lock"

# The screens. No overrides: nothing is touched, so a game doesn't blink at launch or on the way back.
with Fixture() as f:
    assert not [c for c in f.run(PROFILE, "screens", "3ds", "Zelda.3ds") if c.split()[0] in ("swaymsg", "brightness", "pidof")]
    assert not f.has("run/asgard-screen-override.cfg")

# Overrides apply live under Settings' keys, and Settings' own values stay. Only the top's Ultra Black cycles a panel.
with Fixture() as f:
    cfg = "storage/.config/system/configs/system.cfg"
    f.write(cfg, f.read(cfg) + "asgard.refresh=120\ndisplay.brightness2=50\n")
    before = f.read(cfg)
    f.write("game", "top_refresh=60\ntop_brightness=70\nbottom_warmth=2\nbottom_refresh=120\ntop_ultra_black=0\n")
    calls = f.run(PROFILE, "screens", "3ds", "Zelda.3ds")
    assert "swaymsg output DSI-2 mode 1080x1920@60Hz" in calls and "swaymsg output DSI-1 mode 1080x1240@120Hz" in calls, calls
    assert "brightness apply 2 70" in calls and "pidof asgard-gamma" in calls
    assert calls.index("swaymsg output DSI-2 power off") < calls.index("swaymsg output DSI-2 power on")
    assert f.read("sys/module/panel_chipone_icna35xx/parameters/ultra_black").strip() == "N"
    over = f.read("run/asgard-screen-override.cfg").splitlines()
    assert sorted(over) == sorted(["asgard.refresh=60", "display.brightness2=70", "asgard.warmth.bottom=2",
                                   "asgard.refresh_bottom=120", "asgard.ultra_black=0"]), over
    assert f.read(cfg) == before, "an override reached Settings' keys"

    # The same again: nothing moves.
    assert not [c for c in f.run(PROFILE, "screens", "3ds", "Zelda.3ds") if c.split()[0] in ("swaymsg", "brightness", "pidof")]

    # Home: Settings' values come back, and returning puts the game's on again.
    calls = f.run(PROFILE, "home")
    assert "swaymsg output DSI-2 mode 1080x1920@120Hz" in calls and "swaymsg output DSI-1 mode 1080x1240@60Hz" in calls, calls
    assert "brightness apply 2 50" in calls and "swaymsg output DSI-2 power on" in calls
    assert f.read("sys/module/panel_chipone_icna35xx/parameters/ultra_black").strip() == "Y"
    assert not f.has("run/asgard-screen-override.cfg")
    calls = f.run(PROFILE, "game", "3ds", "Zelda.3ds")
    assert "swaymsg output DSI-2 mode 1080x1920@60Hz" in calls and "brightness apply 2 70" in calls, calls

    # The game ends: the same, with no leftovers.
    f.write("bin/python3", "#!/bin/sh\n", True)
    calls = f.run(PROFILE, "restore")
    assert "swaymsg output DSI-2 mode 1080x1920@120Hz" in calls and not f.has("run/asgard-screen-override.cfg"), calls

# Screens off with the lid: Ultra Black waits for the next power-on rather than lighting the panel.
with Fixture() as f:
    f.write("run/asgard-screens-off.active", "")
    f.write("game", "top_ultra_black=0\n")
    calls = f.run(PROFILE, "screens", "3ds", "Zelda.3ds")
    assert not [c for c in calls if "power" in c], calls
    assert f.read("sys/module/panel_chipone_icna35xx/parameters/ultra_black").strip() == "N"

# Home asks for them at the right moments, the game's before it's continued.
back = BACKEND[BACKEND.index("void Backend::toBackground()"):BACKEND.index("void Backend::resumeGame()")]
assert back.index("asgard-background.py") < back.index("asgard-perf-profile.sh home")
resume = BACKEND[BACKEND.index("void Backend::resumeGame()"):BACKEND.index("// RetroArch's network command port")]
assert resume.index("asgard-perf-profile.sh game") < resume.index("asgard-background.py")
print("ok")
