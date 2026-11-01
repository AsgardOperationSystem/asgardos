#!/usr/bin/env python3
# spec: PERF-1 PERF-2 PERF-3 PERF-4 PERF-5 CFG-7 CFG-12 PWR-8
# requires: cmd:bash cmd:awk cmd:setsid
"""asgard-cpu-cap.sh, asgard-perf-profile.sh and asgard-fan.sh against a fake sysfs and a stub systemctl: what Home and a
game get for each setting, the clusters' caps and cores, the GPU's cap, Auto, the fan, the gyro service. Copies of the
scripts with their paths rewritten into a temp dir, as test_post_update.py, so the host isn't touched. Whether the real
clocks move is the device check. CFG-7 here is only: these scripts and the gyro's units with the setting or its file
missing; Home with no system.cfg is test_home_offers.py."""
import os
import re
import stat
import subprocess
import sys
import tempfile
import types

HERE = os.path.dirname(os.path.abspath(__file__))
ROOTED = re.compile(r'(?<![\w.$/}-])/(sys|run|storage|usr|etc|var|tmp)(?=[/\s"\':]|$)', re.M)
CPU = "sys/devices/system/cpu"
GPU = "sys/class/devfreq/3d00000.gpu"
CFG = "storage/.config/system/configs/system.cfg"
STEPS = {"little": (0, [300000, 500000, 900000, 1000000, 1400000, 1700000, 2000000]),
         "mid": (3, [400000, 1000000, 1400000, 1900000, 2100000, 2400000, 2800000]),
         "prime": (7, [600000, 1200000, 1600000, 2000000, 2400000, 2900000, 3200000])}
GPU_STEPS = [220000000, 300000000, 350000000, 420000000, 500000000, 600000000, 680000000]
STOCK = {"little": 2000000, "mid": 2800000, "prime": 3200000, "gpu": 680000000}
HOME_DEFAULT = {"little": 1700000, "mid": 2100000, "prime": 2400000, "gpu": 680000000}  # 90 %, 75 %, 75 %, 100 %


class Box:
    """A temp root with the scripts' copies, a fake sysfs and stubs. One per scenario."""

    def __init__(self, cfg=""):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        self.write("etc/os-release", "")
        self.write("run/.keep", "")
        self.write("storage/.config/profile.d/.keep", "")
        self.install("../../asgardos/profile.d/001-functions", "etc/profile.d/001-functions")
        for name in ("asgard-cpu-lib.sh", "asgard-cpu-cap.sh", "asgard-perf-profile.sh", "asgard-fan.sh"):
            self.install(name, f"usr/share/asgard/{name}")
        self.stub("usr/bin/systemctl", 'echo "$*" >> "{root}/systemctl.log"')
        for name in ("asgard-eq.py", "asgard-autotune.py"):
            self.write(f"usr/share/asgard/{name}",
                       f'import sys\nopen("{self.root}/{name}.log", "a").write(" ".join(sys.argv[1:]) + "\\n")\n')
        self.write(f"{CPU}/online", "0-7\n")
        for n in range(1, 8):
            self.write(f"{CPU}/cpu{n}/online", "1\n")
        os.makedirs(f"{self.root}/{CPU}/cpu0")   # no online file, as if it can't go offline: a write to it would show
        for pol, steps in STEPS.values():
            p = f"{CPU}/cpufreq/policy{pol}"
            self.write(f"{p}/cpuinfo_max_freq", f"{steps[-1]}\n")
            self.write(f"{p}/cpuinfo_min_freq", f"{steps[0]}\n")
            self.write(f"{p}/scaling_available_frequencies", " ".join(map(str, steps)) + " \n")
            self.write(f"{p}/scaling_max_freq", "1\n")
        self.write(f"{GPU}/available_frequencies", " ".join(map(str, GPU_STEPS)) + "\n")
        self.write(f"{GPU}/min_freq", f"{GPU_STEPS[0]}\n")
        self.write(f"{GPU}/max_freq", "1\n")
        self.write("sys/class/hwmon/hwmon3/pwm1", "9\n")
        self.write("sys/class/hwmon/hwmon3/pwm1_enable", "9\n")
        if cfg is not None:
            self.write(CFG, cfg)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.tmp.cleanup()

    def write(self, name, text):
        path = f"{self.root}/{name}"
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(text)

    def read(self, name):
        try:
            with open(f"{self.root}/{name}") as f:
                return f.read()
        except FileNotFoundError:
            return ""

    def install(self, source, dest):
        text = ROOTED.sub(lambda m: f"{self.root}/{m.group(1)}", open(os.path.join(HERE, source)).read())
        # The image's bash is 5.3, where BASH_REMATCH can be local. An older host bash leaves that local empty.
        self.write(dest, text.replace("local -a keys=() BASH_REMATCH", "local -a keys=()"))
        os.chmod(f"{self.root}/{dest}", stat.S_IRWXU)

    def stub(self, name, body):
        self.write(name, "#!/bin/sh\n" + body.replace("{root}", self.root) + "\n")
        os.chmod(f"{self.root}/{name}", stat.S_IRWXU)

    def run(self, script, *args):
        return subprocess.run(["bash", f"{self.root}/usr/share/asgard/{script}", *args], capture_output=True, text=True,
                              timeout=60).returncode

    def caps(self):
        out = {t: int(self.read(f"{CPU}/cpufreq/policy{pol}/scaling_max_freq")) for t, (pol, _) in STEPS.items()}
        out["gpu"] = int(self.read(f"{GPU}/max_freq"))
        return out

    def offline(self):
        return [n for n in range(1, 8) if self.read(f"{CPU}/cpu{n}/online").strip() == "0"]

    def cfg(self):
        return self.read(CFG).splitlines()

    def log(self, name):
        return self.read(name).splitlines()

    def wait_log(self, name):
        for _ in range(100):
            if self.read(name):
                break
            subprocess.run(["sleep", "0.05"])
        return self.log(name)


def game_caps(cfg):
    with Box(cfg) as b:
        b.run("asgard-perf-profile.sh", "cpu", "gba", "X.gba")
        return b.caps()


# --- PERF-1: each type's cap is the highest step at or under its share of that cluster's top clock, or its cores off.
got = game_caps("gba.cpu_cap_little=50\ngba.cpu_cap_mid=60\ngba.cpu_cap_prime=40\n")
assert got == {"little": 1000000, "mid": 1400000, "prime": 1200000, "gpu": 680000000}, got
got = game_caps("gba.cpu_cap_little=10\ngba.cpu_cap_mid=25\ngba.cpu_cap_prime=150\n")   # 25-100: under and over are held
assert got["little"] == 500000 and got["mid"] == 400000 and got["prime"] == 3200000, got
for off, cores in (("little", [1, 2]), ("mid", [3, 4, 5, 6]), ("prime", [7])):
    with Box(f"gba.cpu_cap_{off}=off\n") as b:
        b.run("asgard-perf-profile.sh", "cpu", "gba", "X.gba")
        assert b.offline() == cores, (off, b.offline())
        assert not b.read(f"{CPU}/cpu0/online"), "CPU0 written"   # PERF-2

# --- PERF-2: with all three off, one type stays on, in the game's profile and in the menu's.
with Box("gba.cpu_cap_little=off\ngba.cpu_cap_mid=off\ngba.cpu_cap_prime=off\n") as b:
    b.run("asgard-perf-profile.sh", "cpu", "gba", "X.gba")
    assert b.offline() == [1, 2, 3, 4, 5, 6], b.offline()
with Box("asgard.cpu_cap.little=off\nasgard.cpu_cap.mid=off\nasgard.cpu_cap.prime=off\n") as b:
    b.run("asgard-cpu-cap.sh")
    assert b.offline() == [1, 2, 3, 4, 5, 6] and not b.read(f"{CPU}/cpu0/online"), b.offline()

# --- PERF-3: the menu's defaults and values apply in Home.
with Box() as b:
    assert b.run("asgard-cpu-cap.sh") == 0
    assert b.caps() == HOME_DEFAULT, b.caps()
MENU = "asgard.cpu_cap.little=25\nasgard.cpu_cap.mid=off\nasgard.cpu_cap.prime=50\nasgard.gpu_cap=25\nasgard.motion=1\n"
with Box(MENU) as b:
    b.run("asgard-cpu-cap.sh")
    home = b.caps()
    assert home["little"] == 500000 and home["prime"] == 1600000 and home["gpu"] == GPU_STEPS[0], home
    assert b.offline() == [3, 4, 5, 6], b.offline()
    # A game starts at stock, every core on: the menu's keys aren't a scope (CFG-12), and neither is its gyro.
    assert b.run("asgard-perf-profile.sh", "apply", "gba", "X.gba") == 0
    assert b.caps() == STOCK and b.offline() == [], (b.caps(), b.offline())
    assert b.log("systemctl.log") == ["stop asgard-motiond"], b.log("systemctl.log")   # CFG-12, PWR-8
    # And the menu's profile comes back after it.
    assert b.run("asgard-perf-profile.sh", "restore") == 0
    assert {**b.caps(), "mid": 0} == {**home, "mid": 0} and b.offline() == [3, 4, 5, 6], (b.caps(), b.offline())
    assert b.log("systemctl.log")[-1] == "start asgard-motiond", b.log("systemctl.log")   # PWR-8
# A game's overrides go on top of stock, and don't outlive it.
with Box("asgard.cpu_cap.mid=50\ngba.cpu_cap_mid=60\n") as b:
    b.run("asgard-perf-profile.sh", "apply", "gba", "X.gba")
    assert b.caps() == {**STOCK, "mid": 1400000}, b.caps()
    b.run("asgard-perf-profile.sh", "restore")
    assert b.caps() == {**HOME_DEFAULT, "mid": 1400000}, b.caps()
RUNEMU = open(os.path.join(HERE, "../../asgardos/sources/scripts/runemu.sh")).read()
assert re.search(r"asgard-perf-profile\.sh apply", RUNEMU) and re.search(r"asgard-perf-profile\.sh restore", RUNEMU), \
    "runemu.sh no longer puts the profile around a game"
TUNING = open(os.path.join(HERE, "../autostart/090-asgard-tuning")).read()
assert re.search(r"^/usr/share/asgard/asgard-cpu-cap\.sh$", TUNING, re.M), "the menu's profile isn't applied at boot"

# --- PERF-4: the GPU's cap, in Home and per game; Auto per game only.
with Box("asgard.gpu_cap=60\n") as b:
    b.run("asgard-cpu-cap.sh")
    assert b.caps()["gpu"] == 350000000, b.caps()
for value, want in (("50", 300000000), ("10", GPU_STEPS[0]), ("150", 680000000)):   # 25 % is under this table's lowest
    got = game_caps(f"gba.gpu_cap={value}\n")["gpu"]
    assert got == want, (value, got)
with Box("gba.gpu_cap=autotune\ngba.cpu_cap_mid=autotune\n") as b:
    b.run("asgard-perf-profile.sh", "cpu", "gba", "X.gba")
    assert b.caps() == STOCK, b.caps()
    assert b.wait_log("asgard-autotune.py.log") == ["mid gpu"], b.log("asgard-autotune.py.log")
with Box("asgard.gpu_cap=autotune\nasgard.cpu_cap.mid=autotune\n") as b:   # games only
    b.run("asgard-cpu-cap.sh")
    assert b.caps() == HOME_DEFAULT and not b.log("asgard-autotune.py.log"), b.caps()

# The per-game choices that every emulator gets. thor_settings.py is the SDL panel's too: only its tables are needed here.
sys.modules["sdlui"] = types.ModuleType("sdlui")
sys.modules["sdlui"].__getattr__ = lambda name: None
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True
import thor_settings  # noqa: E402

offers = dict(thor_settings.PERF_FEATURES)
percents = [str(v) for v in range(25, 101, 5)]
for t in ("little", "mid", "prime"):
    assert [v for _, v in offers[f"cpu cap {t}"]] == ["off", "autotune"] + percents, offers[f"cpu cap {t}"]   # PERF-1, -4
assert [v for _, v in offers["gpu cap"]] == ["autotune"] + percents, offers["gpu cap"]

# --- PERF-5: fixed speeds and curves.
modes = [v for _, v in offers["fan mode"]]
assert {"quiet", "moderate", "aggressive"} <= set(modes) and any(v.isdigit() for v in modes), modes
DROPIN = open(os.path.join(HERE, "../fancontrol.service.d/asgard-fan.conf")).read()
assert "ExecCondition=/usr/share/asgard/asgard-fan.sh" in DROPIN, "a fixed speed is no longer applied by fancontrol's unit"
PWM, ENABLE = "sys/class/hwmon/hwmon3/pwm1", "sys/class/hwmon/hwmon3/pwm1_enable"
with Box("asgard.fan_manual=128\n") as b:   # every restart of fancontrol, so every launch, sets it and skips the curve
    assert b.run("asgard-fan.sh") == 1
    assert b.read(PWM).strip() == "128" and b.read(ENABLE).strip() == "1"
for cfg in ("", "asgard.fan_manual=\n"):
    with Box(cfg) as b:                     # a curve: fancontrol starts, the PWM is its own
        assert b.run("asgard-fan.sh") == 0
        assert b.read(PWM).strip() == "9"
FIXED = "asgard.fan_manual=128\ncooling.profile=moderate\n"
with Box(FIXED) as b:                       # a game with no fan option leaves it
    b.run("asgard-perf-profile.sh", "apply", "gba", "X.gba")
    assert "asgard.fan_manual=128" in b.cfg() and "restart fancontrol" not in b.log("systemctl.log"), b.cfg()
    b.run("asgard-perf-profile.sh", "restore")
    assert "asgard.fan_manual=128" in b.cfg(), b.cfg()
with Box(FIXED + "gba.fan_mode=quiet\n") as b:   # a game's curve replaces it while it runs, and it comes back
    b.run("asgard-perf-profile.sh", "apply", "gba", "X.gba")
    assert not [x for x in b.cfg() if x.startswith("asgard.fan_manual=")] and "cooling.profile=quiet" in b.cfg(), b.cfg()
    assert "restart fancontrol" in b.log("systemctl.log")
    b.run("asgard-perf-profile.sh", "restore")
    assert "asgard.fan_manual=128" in b.cfg() and "cooling.profile=moderate" in b.cfg(), b.cfg()
with Box("cooling.profile=moderate\ngba.fan_mode=200\n") as b:   # a game's fixed speed goes away with it
    b.run("asgard-perf-profile.sh", "apply", "gba", "X.gba")
    assert "asgard.fan_manual=200" in b.cfg(), b.cfg()
    b.run("asgard-perf-profile.sh", "restore")
    assert not [x for x in b.cfg() if x.startswith("asgard.fan_manual=")], b.cfg()

# --- PWR-8: the gyro service only while asked for.
def motion(cfg, *args):
    with Box(cfg) as b:
        assert b.run("asgard-perf-profile.sh", "motion", *args) == 0
        return b.log("systemctl.log")


assert motion("") == ["stop asgard-motiond"]
assert motion("asgard.motion=1\n") == ["start asgard-motiond"]
assert motion("asgard.motion=0\n") == ["stop asgard-motiond"]
assert motion("gba.motion=on\n", "gba", "X.gba") == ["start asgard-motiond"]
assert motion('gba["X.gba"].motion=on\n', "gba", "X.gba") == ["start asgard-motiond"]
assert motion('gba["X.gba"].motion=on\n', "gba", "Y.gba") == ["stop asgard-motiond"]
assert motion("gba.motion=off\n", "gba", "X.gba") == ["stop asgard-motiond"]
assert motion("asgard.motion=1\n", "gba", "X.gba") == ["stop asgard-motiond"]   # CFG-12
PACKAGE = open(os.path.join(HERE, "../package.mk")).read()
enabled = re.search(r"for unit in ([^;]*);.*\n\s*enable_service", PACKAGE).group(1).split()
assert "thor-sensorspd" in enabled and "asgard-motiond" not in enabled, enabled   # started on request, not at boot
assert re.search(r"^/usr/share/asgard/asgard-perf-profile\.sh motion$", TUNING, re.M), "the menu's gyro isn't applied at boot"

# --- CFG-12: Sound EQ is the exception: unset passes "default", which asgard-eq.py takes from the saved setting (SND-3).
with Box() as b:
    b.run("asgard-perf-profile.sh", "apply", "gba", "X.gba")
    b.run("asgard-perf-profile.sh", "restore")
    assert b.log("asgard-eq.py.log") == ["game default default"] * 2, b.log("asgard-eq.py.log")
with Box("gba.eq_speaker=joey\ngba.eq_headphones=off\n") as b:
    b.run("asgard-perf-profile.sh", "apply", "gba", "X.gba")
    assert b.log("asgard-eq.py.log") == ["game joey off"], b.log("asgard-eq.py.log")

# --- CFG-7: with no system.cfg at all, Home gets its defaults, a game stock, the fan its curve.
with Box(None) as b:
    assert b.run("asgard-cpu-cap.sh") == 0 and b.caps() == HOME_DEFAULT, b.caps()
    assert b.run("asgard-perf-profile.sh", "apply", "gba", "X.gba") == 0 and b.caps() == STOCK, b.caps()
    assert b.run("asgard-perf-profile.sh", "restore") == 0 and b.caps() == HOME_DEFAULT, b.caps()
    assert b.run("asgard-fan.sh") == 0
# The gyro's data can't ship: its service needs the sensor server, which starts only when sensors-root is there.
SENSORS = open(os.path.join(HERE, "../system.d/thor-sensorspd.service")).read()
MOTIOND = open(os.path.join(HERE, "../system.d/asgard-motiond.service")).read()
assert re.search(r"^ConditionPathExists=/storage/\.config/asgard/sensors-root/", SENSORS, re.M), "sensors-root isn't required"
assert re.search(r"^BindsTo=thor-sensorspd\.service$", MOTIOND, re.M), "the gyro can start without the sensor server"

print("perf profile: ok")
