#!/usr/bin/env python3
# spec: AUD-1 AUD-2 AUD-3 SND-1
# requires: cmd:bash cmd:awk cmd:flock
"""Tree and script checks for the sound setup: the rule that puts headphones first (that the output moves when a jack is
plugged is a human check), every EQ filter pinned at 100 % with `volume` setting the real sink (run with a stub pactl),
and asgard-eq.py's accepted modes. AUD-2's limiter here is Joey's; the Thor presets' headroom is test_eq_headroom.py."""
import importlib.util
import os
import re
import stat
import subprocess
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("eq", os.path.join(HERE, "asgard-eq.py"))
eq = importlib.util.module_from_spec(spec)
spec.loader.exec_module(eq)
read = lambda name: open(os.path.join(HERE, name)).read()

# --- AUD-1: headphones outrank the speaker's ALSA priority (1000), on the sink that's really there.
RULE = read("../wireplumber/60-thor-headphones-first.conf")
assert f'node.name = "{eq.HEADPHONES_SINK}"' in RULE, "the rule doesn't name the headphones' sink"
session = re.search(r"priority\.session = (\d+)", RULE)
assert session and int(session.group(1)) > 1000, RULE
assert re.search(r"cp \$\{PKG_DIR\}/wireplumber/\*\.conf \$\{INSTALL\}/usr/share/wireplumber/wireplumber\.conf\.d/", read("../package.mk"))

# --- AUD-2: each chain, shipped or generated, keeps its node at 100 %, in front of the real sink.
PEQ = "Preamp: -3 dB\nFilter 1: ON PK Fc 100 Hz Gain 3 dB Q 1\n"
SHIPPED = read("../pipewire/50-thor-dsp.conf")
CHAINS = {"shipped": SHIPPED, "joey": eq.conf_text({"speaker": "joey"}),
          "autoeq": eq.conf_text({"headphones": "autoeq", "headphones_name": "X", "peq": PEQ})}
for name, text in CHAINS.items():
    captures = re.findall(r"capture\.props = \{(.*?)\n\s*\}\n\s*playback\.props", text, re.S)
    assert captures and len(captures) == text.count("libpipewire-module-filter-chain"), name
    for cap in captures:
        assert "state.restore-props = false" in cap, f"{name}: a level could be restored on the filter"
        assert "filter.smart = true" in cap and re.search(rf'filter\.smart\.target = \{{ node\.name = "({eq.SPEAKER_SINK}|{eq.HEADPHONES_SINK})" \}}', cap), (name, cap)
assert "asgard-limiter.so" in CHAINS["joey"] and 'outputs = [ "lim:Out L" "lim:Out R" ]' in CHAINS["joey"], "Joey's +15 dB isn't limited"

# `volume` with a stub pactl, as the image's /bin/sh: bash. A copy with its paths rewritten, as test_post_update.py.
ROOTED = re.compile(r'(?<![\w.$/}-])/(sys|run|storage|usr|etc|var|tmp)(?=[/\s"\':]|$)', re.M)


def volume(default, sinks, arg="40"):
    with tempfile.TemporaryDirectory() as t:
        def install(source, dest):
            text = ROOTED.sub(lambda m: f"{t}/{m.group(1)}", read(source))
            os.makedirs(os.path.dirname(f"{t}/{dest}"), exist_ok=True)
            with open(f"{t}/{dest}", "w") as f:
                f.write(text.replace("local -a keys=() BASH_REMATCH", "local -a keys=()"))   # host bash older than the image's
            os.chmod(f"{t}/{dest}", stat.S_IRWXU)

        install("../../asgardos/profile.d/001-functions", "etc/profile.d/001-functions")
        install("../../asgardos/sources/scripts/volume", "usr/bin/volume")
        open(f"{t}/etc/os-release", "w").close()
        os.makedirs(f"{t}/storage/.config/system/configs")
        os.makedirs(f"{t}/tmp")
        with open(f"{t}/storage/.config/system/configs/system.cfg", "w") as f:
            f.write("audio.volume=50\n")
        listing = "".join(f"{i}\t{s}\tPipeWire\ts32le 2ch 48000Hz\tSUSPENDED\n" for i, s in enumerate(sinks))
        with open(f"{t}/listing", "w") as f:
            f.write(listing)
        with open(f"{t}/usr/bin/sleep", "w") as f:
            f.write("#!/bin/sh\nexit 0\n")
        with open(f"{t}/usr/bin/pactl", "w") as f:
            f.write(f"""#!/bin/sh
case "$1" in
  get-default-sink) echo {default} ;;
  list) cat {t}/listing ;;
  --) shift; echo "$*" >> {t}/set.log ;;
esac
""")
        with open(f"{t}/usr/bin/pw-metadata", "w") as f:
            f.write(f'#!/bin/sh\necho "$*" >> {t}/meta.log\n')
        for tool in ("sleep", "pactl", "pw-metadata"):
            os.chmod(f"{t}/usr/bin/{tool}", stat.S_IRWXU)
        assert subprocess.run(["bash", f"{t}/usr/bin/volume", arg], capture_output=True, timeout=30).returncode == 0
        log = open(f"{t}/set.log").read().splitlines() if os.path.exists(f"{t}/set.log") else []
        meta = open(f"{t}/meta.log").read().splitlines() if os.path.exists(f"{t}/meta.log") else []
        assert meta == [f"0 asgard.volume {arg}"], meta   # AUD-3: the level outputs appear at
        return log, open(f"{t}/storage/.config/system/configs/system.cfg").read()


FILTER = "thor_dsp_speaker"
# The default is the filter: the level goes on the device, and the filter is put back to 100 %.
log, cfg = volume(FILTER, [FILTER, eq.SPEAKER_SINK, "thor_dsp_headphones", eq.HEADPHONES_SINK])
assert log[-1] == f"set-sink-volume {eq.SPEAKER_SINK} 40%", log
assert f"set-sink-volume {FILTER} 100%" in log and "set-sink-volume thor_dsp_headphones 100%" in log, log
assert not [x for x in log if x.startswith("set-sink-volume thor_dsp") and not x.endswith(" 100%")], log
assert "audio.volume=40\n" in cfg, cfg
log, _ = volume("thor_dsp_headphones", ["thor_dsp_headphones", eq.HEADPHONES_SINK, eq.SPEAKER_SINK])
assert log[-1] == f"set-sink-volume {eq.HEADPHONES_SINK} 40%", log
# The device isn't up yet (boot): nothing lands on the filter, the level is only saved.
log, cfg = volume(FILTER, [FILTER])
assert not [x for x in log if not x.endswith(" 100%")], log
assert "audio.volume=40\n" in cfg, cfg
# No filter (EQ off): the default sink itself.
log, _ = volume(eq.SPEAKER_SINK, [eq.SPEAKER_SINK])
assert log == [f"set-sink-volume {eq.SPEAKER_SINK} 40%"], log

# --- SND-1: what asgard-eq.py takes for each output. Settings' rows are test_home_offers.py.
applied = []
eq.apply = lambda st, save=True: applied.append(dict(st))
eq.load_state = lambda: {}
for out, modes, others in (("speaker", ("thor", "joey", "off"), ("autoeq",)), ("headphones", ("thor", "off"), ("joey",))):
    for mode in modes:
        assert eq.main(["", "set", out, mode]) == {"ok": True}, (out, mode)
        assert applied.pop()[out] == mode
    for mode in others:
        assert eq.main(["", "set", out, mode]) != {"ok": True}, (out, mode)
eq.load_state = lambda: {"peq": PEQ}
assert eq.main(["", "set", "headphones", "autoeq"]) == {"ok": True}
assert eq.main(["", "game", "default", "default"]) == {"ok": True}
eq.load_state = lambda: {}
assert "error" in eq.main(["", "set", "headphones", "autoeq"]), "AutoEQ with no profile isn't refused"
print("audio: ok")
