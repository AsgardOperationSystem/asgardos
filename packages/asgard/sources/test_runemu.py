#!/usr/bin/env python3
# spec: GAME-1 GAME-2 GAME-3 EMU-4 GPU-1 GPU-3
# requires: cmd:bash cmd:jq cmd:flock
# The real runemu.sh and profile functions, every path rewritten into a temp dir, with fake start_*.sh and helpers. GAME-1: what
# it does around any emulator (profile, pre-rotation, per-game options); GAME-2: the kill data's life around a launch; GAME-3: the
# real asgard-crashlog.sh reached from exit codes; EMU-4: which start script runs; GPU-1, GPU-3: the driver selection a game sees.
import os
import re
import shutil
import subprocess
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
RUNEMU = f"{HERE}/../../asgardos/sources/scripts/runemu.sh"
FUNCTIONS = f"{HERE}/../../asgardos/profile.d/001-functions"
CRASHLOG = f"{HERE}/asgard-crashlog.sh"
HOST_SEES = ["VK_DRIVER_FILES", "MESA_LOADER_DRIVER_OVERRIDE", "vk_wsi_wayland_prerotate", "egl_wayland_prerotate"]
RECORD = """#!/bin/sh
{ printf '%s' "${0##*/}"; printf '\\037%s' "$@"; echo; } >>"$T/trace"
"""
# A start script or emulator: records its arguments, what the game's environment holds and the kill data, then ends as told.
EMULATOR = """#!/bin/sh
{ printf '%s' "${0##*/}"; printf '\\037%s' "$@"; echo; } >>"$T/trace"
env >"$T/env"
cat "$T/tmp/.process-kill-data" >"$T/kill-during" 2>/dev/null
echo "emulator's own log line"
exit "$(cat "$T/exit")"
"""


def rewrite(text, t):
    paths = {"/storage": f"{t}/storage", "/usr/share/asgard/": f"{t}/asgard/", "/usr/bin/": f"{t}/bin/",
             "/usr/lib/gpu-drivers": f"{t}/gpu", "/var/log": f"{t}/log", "/tmp/": f"{t}/tmp/", "/run/": f"{t}/run/",
             "/sys/": f"{t}/sys/", ". /etc/profile": f". {t}/profile", ". /etc/os-release": ":"}
    return re.sub("|".join(map(re.escape, paths)), lambda m: paths[m.group(0)], text)   # one pass: t itself may be under /tmp


class Fixture:
    def __enter__(self):
        self._tmp = tempfile.TemporaryDirectory()
        t = self.t = self._tmp.name
        for d in ("storage/.config/system/configs", "storage/.config/thor", "asgard", "bin", "gpu", "log", "tmp/cores",
                  "run", "sys"):
            os.makedirs(f"{t}/{d}")
        self.cfg("")
        self.script("exit", "0\n", False)
        for name in ("performance", "gpu_profiling", "gpu_performance_level", "get_gpu_performance_level", "systemctl"):
            self.script(f"bin/{name}", RECORD)
        self.script("bin/game-guides-tool", RECORD)
        self.script("bin/setsettings.sh", "#!/bin/sh\necho 0\n")
        self.script("asgard/asgard-perf-profile.sh", RECORD)
        self.script("bin/swaymsg", """#!/bin/sh
case "$*" in *get_outputs*) cat "$T/outputs" ;; esac
""")
        self.script("outputs", '[{"focused":true,"active":true,"name":"DSI-2","transform":"90","current_mode":{"width":1080,"height":1920}},'
                    '{"focused":false,"active":true,"name":"DSI-1","transform":"90","current_mode":{"width":1080,"height":1240}}]', False)
        os.symlink(shutil.which("bash"), f"{t}/bin/bash")
        shutil.copy(CRASHLOG, f"{t}/asgard/asgard-crashlog.sh")
        os.chmod(f"{t}/asgard/asgard-crashlog.sh", 0o755)   # package.mk's chmod
        with open(FUNCTIONS) as f:
            functions = rewrite(f.read(), t)
        # The image's bash is 5.3, where BASH_REMATCH can be local (test_get_setting.py); an older host's leaves that local empty.
        functions = functions.replace("local -a keys=() BASH_REMATCH", "local -a keys=()")
        self.script("functions", functions, False)
        self.script("profile", f'. {t}/functions\nexport PATH="{t}/bin:$PATH"\n', False)
        with open(RUNEMU) as f:
            self.script("runemu.sh", rewrite(f.read(), t))
        return self

    def __exit__(self, *_):
        self._tmp.cleanup()

    def script(self, name, text, executable=True):
        with open(f"{self.t}/{name}", "w") as f:
            f.write(text)
        if executable:
            os.chmod(f"{self.t}/{name}", 0o755)

    def cfg(self, text):
        self.script("storage/.config/system/configs/system.cfg", text, False)

    def launch(self, rom="/roms/gba/Metroid.gba", system="gba", core="melonds-sa", emulator="melonds", code=0, **env):
        """Runs it; returns (its exit code, what the game's environment held of HOST_SEES)."""
        self.script("exit", f"{code}\n", False)
        for name in (f"start_{core.rsplit('-', 1)[0]}.sh",):
            self.script(f"bin/{name}", EMULATOR)
        proc = subprocess.run(["bash", f"{self.t}/runemu.sh", rom, f"-P{system}", f"--core={core}", f"--emulator={emulator}",
                               "--controllers="], capture_output=True, text=True, timeout=60,
                              env={"PATH": os.environ["PATH"], "T": self.t, "CRASH_DIR": f"{self.t}/crashes",
                                   "EXEC_LOG": f"{self.t}/log/exec.log", "SAVE_MARKER": f"{self.t}/tmp/asgard-save-log", **env})
        seen = {}
        if os.path.exists(f"{self.t}/env"):
            with open(f"{self.t}/env") as f:
                seen = {k: v for k, v in (ln.rstrip("\n").split("=", 1) for ln in f if "=" in ln) if k in HOST_SEES}
        return proc, seen

    def trace(self):
        with open(f"{self.t}/trace") as f:
            return [ln.rstrip("\n").split("\x1f") for ln in f]

    def crashes(self):
        d = f"{self.t}/crashes"
        return sorted(os.listdir(d)) if os.path.isdir(d) else []


# EMU-4: /usr/bin/start_<core minus -sa>.sh, with the ROM and system.
for core, script in (("melonds-sa", "start_melonds.sh"), ("eden-duo-sa", "start_eden-duo.sh"), ("azahar-sa", "start_azahar.sh")):
    with Fixture() as f:
        proc, _ = f.launch(core=core, emulator=core.rsplit("-", 1)[0])
        assert proc.returncode == 0, proc.stderr
        assert [script, "/roms/gba/Metroid.gba", "gba"] in f.trace(), f.trace()

# GAME-2: no stale kill data for the launcher to inherit; a start script's set_kill is what's there during the game; runemu's
# own for RetroArch; none left afterwards that names the game.
with Fixture() as f:
    f.script("tmp/.process-kill-data", "-9 stale-from-last-game\n", False)
    f.launch()
    assert os.path.getsize(f"{f.t}/kill-during") == 0, "a launcher that declares nothing inherited the last game's kill data"
    with open(f"{f.t}/tmp/.process-kill-data") as k:
        assert k.read().split() == ["emulationstation"]
with Fixture() as f:
    f.script("bin/retroarch", EMULATOR)
    f.launch(core="mgba", emulator="retroarch")
    with open(f"{f.t}/kill-during") as k:
        assert k.read().split() == ["retroarch", "retroarch32"]
    call = next(t for t in f.trace() if t[0] == "retroarch")
    assert f"{f.t}/tmp/cores/mgba_libretro.so" in call and "/roms/gba/Metroid.gba" in call, call

# GAME-1: the CPU and fan profile around the game, for that system and ROM file.
with Fixture() as f:
    f.launch()
    trace = f.trace()
    names = [t[0] for t in trace]
    apply_ = trace.index(["asgard-perf-profile.sh", "apply", "gba", "Metroid.gba"])
    assert apply_ < names.index("start_melonds.sh") < trace.index(["asgard-perf-profile.sh", "restore"]), trace
    # A crash still gets the profile undone.
    f.launch(code=139)
    assert f.trace().count(["asgard-perf-profile.sh", "restore"]) == 2

# GAME-1: the pre-rotation the output's transform asks for, when the plane can't do it.
with Fixture() as f:
    _, seen = f.launch(DEVICE_SCANOUT_SCALING="true", DEVICE_PRE_ROTATION="true")
    assert seen.get("vk_wsi_wayland_prerotate") == "270" and seen.get("egl_wayland_prerotate") == "270", seen
    os.remove(f"{f.t}/env")
    _, seen = f.launch(DEVICE_SCANOUT_SCALING="true", DEVICE_PRE_ROTATION="false")
    assert "vk_wsi_wayland_prerotate" not in seen, seen

# GAME-3 end to end: clean codes keep no log, others do, and the launcher's own status follows; Quit and save log keeps it too.
for code, kept, status in ((0, 0, 0), (137, 0, 0), (143, 0, 0), (1, 1, 1), (139, 1, 1), (134, 1, 1)):
    with Fixture() as f:
        proc, _ = f.launch(code=code)
        assert proc.returncode == status, (code, proc.returncode, proc.stderr)
        assert len(f.crashes()) == kept, (code, f.crashes())
        if kept:
            with open(f"{f.t}/crashes/{f.crashes()[0]}") as log:
                text = log.read()
            assert f"exit code: {code}" in text and "emulator's own log line" in text, text
with Fixture() as f:
    f.script("tmp/asgard-save-log", "", False)
    proc, _ = f.launch(code=137)
    assert proc.returncode == 0 and len(f.crashes()) == 1

# GPU-1: unset is the image's Mesa; the per-game choice beats the system's; a user's build wins over the image's; a name with no
# build behind it falls back rather than breaking the game.
with Fixture() as f:
    for top in ("gpu/mesa-a", "gpu/mesa-b", "gpu/both", "storage/.config/gpu-drivers/both", "storage/.config/gpu-drivers/mine"):
        os.makedirs(f"{f.t}/{top}")
        f.script(f"{top}/icd.json", "{}", False)
    gpu, user = f"{f.t}/gpu", f"{f.t}/storage/.config/gpu-drivers"
    for cfg, want in (("", None),
                      ("gba.gpu_driver=mesa-a\n", f"{gpu}/mesa-a/icd.json"),
                      ('gba.gpu_driver=mesa-a\ngba["Metroid.gba"].gpu_driver=mesa-b\n', f"{gpu}/mesa-b/icd.json"),
                      ("gba.gpu_driver=mine\n", f"{user}/mine/icd.json"),
                      ("gba.gpu_driver=both\n", f"{user}/both/icd.json"),
                      ("gba.gpu_driver=missing\n", None)):
        f.cfg(cfg)
        _, seen = f.launch()
        assert seen.get("VK_DRIVER_FILES") == want, (cfg, seen)

# GPU-3: unset leaves the image's default (Zink, from the quirk, in the environment). freedreno replaces it, per game or
# system, under the name Mesa's loader knows it by, which works here (sdlui.py).
with Fixture() as f:
    for cfg, want in (("", None), ("gba.gl_driver=freedreno\n", "msm"), ('gba["Metroid.gba"].gl_driver=freedreno\n', "msm"),
                      ('gba.gl_driver=freedreno\ngba["Metroid.gba"].gl_driver=zink\n', "zink"),
                      ('nds.gl_driver=freedreno\n', None)):
        f.cfg(cfg)
        _, seen = f.launch()
        assert seen.get("MESA_LOADER_DRIVER_OVERRIDE") == want, (cfg, seen)
print("ok")
