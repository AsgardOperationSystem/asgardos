#!/usr/bin/env python3
# Speaker / headphone EQ for Settings > Hardware > Audio and the in-game menu's Sound page. Prints JSON.
#   asgard-eq.py status                  {"speaker": "thor"|"joey"|"off", "headphones": "thor"|"off"|"autoeq", "headphones_name": ...,
#                                         "saved": [...], "tone": {output: [bass, mid, treble]}, "game": {output: mode}, "output": ...}
#   asgard-eq.py set speaker thor|joey|off, set headphones thor|off|autoeq
#   asgard-eq.py tone <speaker|headphones> <bass> <mid> <treble>   dB, each -6..6: a shelf at 100 Hz, a peak at 1 kHz, a shelf at 8 kHz
#   asgard-eq.py search <text>           AutoEQ profiles whose name has every word (needs internet)
#   asgard-eq.py autoeq <path> <name>    download that profile's ParametricEQ.txt and use it for the headphones
#   asgard-eq.py use <name>              use a headphone profile downloaded before (eq.json "profiles", no internet)
#   asgard-eq.py game <speaker> <headphones>   a game's override (each thor|joey|off|autoeq, or "default" = the saved
#                                        setting) until the next call; eq.json stays. "game default default" = back to it.
#                                        asgard-perf-profile.sh calls it around every game (Hardware overrides > Sound EQ)
#   asgard-eq.py regen                   rewrite 60-asgard-eq.conf from eq.json; restart PipeWire if it changed (post-update, at boot)
#   asgard-eq.py default-conf            print the shipped 50-thor-dsp.conf (test_asgard_eq.py checks the file is this)
#
# Every output's chain has one fixed shape (SND-7), whatever its EQ: per channel 12 raw biquads for the profile, a mixer
# (gain, stereo widening and, on the speaker, the choice of Joey's FIR), 3 raw biquads for bass / mid / treble, then the
# stereo limiter (AUD-2). A profile is only values, so a change is set on the running chain (pw-cli set-param) with no
# gap: PipeWire restarts never cut a game's sound, which SDL3's PulseAudio backend wouldn't get back. Only a chain of
# another shape (a config from before this) needs the restart, and never while a game runs.
# The Thor's own curves are 50-thor-dsp.conf (system), generated here; each module there loads only while
# asgard.eq.<output> is unset. 60-asgard-eq.conf sets that property for every output not on its defaults and has its chain
# with the saved values, as the same smart filter (thor_dsp_<output>), so PipeWire routing is unchanged.
import json, math, os, re, subprocess, sys, urllib.parse, urllib.request

STATE = "/storage/.config/asgard/eq.json"
CONF = "/storage/.config/pipewire/pipewire.conf.d/60-asgard-eq.conf"
OVERRIDE = "/run/asgard-eq-game.json"     # the running game's override, so a change meanwhile keeps it
PLAYING = "/run/thor-playing.txt"         # a game runs: never restart PipeWire
RAW = "https://raw.githubusercontent.com/jaakkopasanen/AutoEq/master/results/"
HEADPHONES_SINK = "alsa_output._sys_devices_platform_sound_sound_card0.HiFi__Headphones__sink"
SPEAKER_SINK = "alsa_output._sys_devices_platform_sound_sound_card0.HiFi__Speaker__sink"
SINKS = {"speaker": SPEAKER_SINK, "headphones": HEADPHONES_SINK}
OUTPUTS = ("speaker", "headphones")
MODES = {"speaker": ("thor", "joey", "off"), "headphones": ("thor", "off", "autoeq")}
TYPES = {"PK": "bq_peaking", "PEQ": "bq_peaking", "LSC": "bq_lowshelf", "LS": "bq_lowshelf",
         "HSC": "bq_highshelf", "HS": "bq_highshelf"}
# Sources by measurement quality, for the result order (AutoEQ lists one entry per source and rig).
SOURCES = ["oratory1990", "crinacle", "Rtings", "Innerfidelity", "HypetheSonics", "Headphone.com Legacy"]
RATE = 48000                              # the Thor's only clock rate (clock.allowed-rates = [ 48000 ])
SLOTS = 12                                # profile biquads per channel: the Thor speaker curve's 12; AutoEQ uses 10
TONE = (("bq_lowshelf", 100.0, 0.707), ("bq_peaking", 1000.0, 0.7), ("bq_highshelf", 8000.0, 0.707))
TONE_MAX = 6
JOEY_IR = "/usr/share/asgard/eq/joey-speaker.wav"
# Joey's Retro Handhelds JamesDSP speaker preset: GraphicEQ with its +15 dB output gain (eq/joey-speaker.wav, from
# eq/gen-speaker-ir.py), its stereo widener (width 2: L' = 1.5 L - 0.5 R), then the limiter.
# The Thor's own: the Android JamesDSP "Thor Speakers" preset (15-band EQ 25 Hz..16 kHz: -8,-7,-5,-2,+1.5,+1.5,0,-0.5,0,
# +0.5,+1.5,+2,+1,+0.5,0 dB) as 2/3-octave peaking filters, -2 dB headroom; headphones: loudness EQ + light widening.
THOR = {
    "speaker": ([("bq_peaking", f, 2.15, g) for f, g in ((25, -8), (40, -7), (63, -5), (100, -2), (160, 1.5), (250, 1.5),
                 (630, -0.5), (1600, 0.5), (2500, 1.5), (4000, 2), (6300, 1), (10000, 0.5))], (0.7943, 0.0)),
    "headphones": ([("bq_lowshelf", 105, 0.707, 4.0), ("bq_peaking", 3000, 1.2, -1.5), ("bq_highshelf", 9000, 0.707, 2.5)],
                   (0.6467, -0.0844)),
}
os.environ.setdefault("XDG_RUNTIME_DIR", "/var/run/0-runtime-dir")   # pw-cli, pw-dump and pw-metadata from any caller


def load_state():
    try:
        with open(STATE) as f:
            st = json.load(f)
    except (OSError, ValueError):
        return {}
    # Every downloaded profile is kept ("profiles": name -> ParametricEQ.txt); a state from before that keeps its one.
    if "profiles" not in st and st.get("peq"):
        st["profiles"] = {st.get("headphones_name") or "AutoEQ": st["peq"]}
    return st


def parse_peq(text):
    """AutoEQ / EqualizerAPO ParametricEQ.txt -> (preamp dB, [(label, freq, q, gain)])."""
    pre, filters = 0.0, []
    for line in text.splitlines():
        m = re.match(r"\s*Preamp:\s*(-?[\d.]+)\s*dB", line)
        if m:
            pre = float(m.group(1))
        m = re.match(r"\s*Filter\s*\d*:\s*ON\s+(\w+)\s+Fc\s+([\d.]+)\s*Hz\s+Gain\s+(-?[\d.]+)\s*dB\s+Q\s+([\d.]+)", line)
        if m and m.group(1) in TYPES:
            filters.append((TYPES[m.group(1)], float(m.group(2)), float(m.group(4)), float(m.group(3))))
    return pre, filters


def biquad(label, freq, q, gain, rate=RATE):
    """(b0, b1, b2, a1, a2), a0 = 1: PipeWire 1.2.6's own formulas (filter-chain biquad.c), so a raw biquad sounds the
    same as its bq_peaking / bq_lowshelf / bq_highshelf. Its shelves have a fixed slope (S = 1) and ignore Q."""
    f = max(0.0, min(freq * 2 / rate, 1.0))
    A = 10 ** (gain / 40)
    if label == "bq_peaking":
        if f <= 0 or f >= 1:
            return (1.0, 0.0, 0.0, 0.0, 0.0)
        if q <= 0:
            return (A * A, 0.0, 0.0, 0.0, 0.0)
        w0 = math.pi * f
        alpha, k = math.sin(w0) / (2 * q), math.cos(w0)
        b0, b1, b2, a0, a1, a2 = 1 + alpha * A, -2 * k, 1 - alpha * A, 1 + alpha / A, -2 * k, 1 - alpha / A
    elif label in ("bq_lowshelf", "bq_highshelf"):
        low = label == "bq_lowshelf"
        if f >= 1:
            return (A * A if low else 1.0, 0.0, 0.0, 0.0, 0.0)
        if f <= 0:
            return (1.0 if low else A * A, 0.0, 0.0, 0.0, 0.0)
        w0 = math.pi * f
        alpha = 0.5 * math.sin(w0) * math.sqrt(2)
        k, k2, ap, am = math.cos(w0), 2 * math.sqrt(A) * alpha, A + 1, A - 1
        if low:
            b0, b1, b2 = A * (ap - am * k + k2), 2 * A * (am - ap * k), A * (ap - am * k - k2)
            a0, a1, a2 = ap + am * k + k2, -2 * (am + ap * k), ap + am * k - k2
        else:
            b0, b1, b2 = A * (ap + am * k + k2), -2 * A * (am + ap * k), A * (ap + am * k - k2)
            a0, a1, a2 = ap - am * k + k2, 2 * (am - ap * k), ap - am * k - k2
    else:
        raise ValueError(label)
    return (b0 / a0, b1 / a0, b2 / a0, a1 / a0, a2 / a0)


IDENTITY = (1.0, 0.0, 0.0, 0.0, 0.0)


def tone_of(st, out):
    t = (st.get("tone") or {}).get(out) or [0, 0, 0]
    return [max(-TONE_MAX, min(TONE_MAX, float(x))) for x in (list(t) + [0, 0, 0])[:3]]


def is_default(st, out):
    return st.get(out, "thor") == "thor" and not any(tone_of(st, out))


def values(st, out):
    """The chain's controls for this state: {"node:control": value}, the same names for every mode."""
    mode = st.get(out, "thor")
    filters, gains = [], (1.0, 0.0, 0.0, 0.0)          # gains: own channel, other channel, own FIR, other FIR
    if mode == "thor":
        filters, (g, x) = THOR[out]
        gains = (g, x, 0.0, 0.0)
    elif mode == "joey" and out == "speaker":
        gains = (0.0, 0.0, 1.5, -0.5)
    elif mode == "autoeq" and out == "headphones" and st.get("peq"):
        pre, filters = parse_peq(st["peq"])
        gains = (10 ** (pre / 20), 0.0, 0.0, 0.0)
    coefs = [biquad(*f) for f in filters[:SLOTS]] + [IDENTITY] * max(0, SLOTS - len(filters))
    tones = [biquad(lab, fc, q, g) for (lab, fc, q), g in zip(TONE, tone_of(st, out))]
    v = {}
    for c in "LR":
        for prefix, bqs in (("s", coefs), ("t", tones)):
            for i, (b0, b1, b2, a1, a2) in enumerate(bqs):
                for k, x in zip(("b0", "b1", "b2", "a0", "a1", "a2"), (b0, b1, b2, 1.0, a1, a2)):
                    v[f"{prefix}{i}{c}:{k}"] = x
        for i, g in enumerate(gains[:4 if out == "speaker" else 2]):
            v[f"sel{c}:Gain {i + 1}"] = g
    return v


def num(x):
    return f"{x:.9g}"


def graph(st, out):
    """Nodes, links, inputs and outputs of the fixed chain, with this state's values."""
    v, nodes, links = values(st, out), [], []
    for c, o in (("L", "R"), ("R", "L")):
        if out == "speaker":
            nodes.append(f'{{ type = builtin name = in{c} label = copy }}')
            nodes.append(f'{{ type = builtin name = conv{c} label = convolver config = {{ filename = "{JOEY_IR}" channel = 0 }} }}')
            links += [f'{{ output = "in{c}:Out" input = "s0{c}:In" }}', f'{{ output = "in{c}:Out" input = "conv{c}:In" }}']
        for prefix, n in (("s", SLOTS), ("t", len(TONE))):
            for i in range(n):
                name = f"{prefix}{i}{c}"
                co = " ".join(f"{k} = {num(v[f'{name}:{k}'])}" for k in ("b0", "b1", "b2", "a0", "a1", "a2"))
                ctl = " ".join(f'"{k}" = {num(v[f"{name}:{k}"])}' for k in ("b0", "b1", "b2", "a0", "a1", "a2"))
                nodes.append(f'{{ type = builtin name = {name} label = bq_raw config = {{ coefficients = [ {{ rate = {RATE} {co} }} ] }} '
                             f'control = {{ {ctl} }} }}')
                if i:
                    links.append(f'{{ output = "{prefix}{i - 1}{c}:Out" input = "{name}:In" }}')
        ins = 4 if out == "speaker" else 2
        gains = " ".join(f'"Gain {i + 1}" = {num(v[f"sel{c}:Gain {i + 1}"])}' for i in range(ins))
        nodes.append(f'{{ type = builtin name = sel{c} label = mixer control = {{ {gains} }} }}')
        links += [f'{{ output = "s{SLOTS - 1}{c}:Out" input = "sel{c}:In 1" }}', f'{{ output = "s{SLOTS - 1}{o}:Out" input = "sel{c}:In 2" }}']
        if out == "speaker":
            links += [f'{{ output = "conv{c}:Out" input = "sel{c}:In 3" }}', f'{{ output = "conv{o}:Out" input = "sel{c}:In 4" }}']
        links += [f'{{ output = "sel{c}:Out" input = "t0{c}:In" }}', f'{{ output = "t{len(TONE) - 1}{c}:Out" input = "lim:In {c}" }}']
    nodes.append('{ type = ladspa name = lim plugin = "/usr/lib/ladspa/asgard-limiter.so" label = asgard_limiter '
                 'control = { "Threshold (dB)" = -0.1 "Release (ms)" = 500 } }')
    inputs = ["inL:In", "inR:In"] if out == "speaker" else ["s0L:In", "s0R:In"]
    return nodes, links, inputs, ["lim:Out L", "lim:Out R"]


def description(st, out):
    mode = st.get(out, "thor")
    name = {"thor": "Thor DSP", "joey": "Thor DSP, Joey", "off": "EQ off"}.get(mode, "AutoEQ: " + st.get("headphones_name", ""))
    return f"{name} ({out.capitalize()})"


def chain(graph_, name, desc, target, condition=None):
    """A stereo filter-chain module around a graph, as the smart filter in front of target."""
    nodes, links, inputs, outputs = graph_
    q = lambda xs: " ".join(f'"{x}"' for x in xs)
    cond = f"    condition = [ {{ {condition} = null }} ]\n" if condition else ""
    return f'''  {{ name = libpipewire-module-filter-chain
{cond}    args = {{
      node.description = "{desc}"
      media.name = "{desc}"
      filter.graph = {{
        nodes = [
          {chr(10).join("          " + n for n in nodes).lstrip()}
        ]
        links = [
          {chr(10).join("          " + l for l in links).lstrip()}
        ]
        inputs = [ {q(inputs)} ]
        outputs = [ {q(outputs)} ]
      }}
      capture.props = {{
        node.name = "{name}"
        media.class = Audio/Sink
        # Always 100 %: the volume keys work on the real sink; a level restored here (WirePlumber state) is hidden.
        state.restore-props = false
        audio.position = [ FL FR ]
        filter.smart = true
        filter.smart.name = "{name.replace('_', '-')}"
        filter.smart.target = {{ node.name = "{target}" }}
      }}
      playback.props = {{
        node.name = "{name}.out"
        audio.position = [ FL FR ]
        node.passive = true
        stream.dont-remix = true
      }}
    }}
  }}
'''


def module(st, out, condition=None):
    return chain(graph(st, out), f"thor_dsp_{out}", description(st, out), SINKS[out], condition)


def default_conf():
    return ("# Generated by asgard-eq.py default-conf: the Thor's own EQ for the speaker and the headphones (see asgard-eq.py).\n"
            "# WirePlumber smart filters: each chain attaches to its own sink. Each module loads only while asgard.eq.<output>\n"
            "# is unset: 60-asgard-eq.conf (Settings > Hardware > Audio) sets it and brings its own.\n"
            "context.modules = [\n" + "".join(module({}, out, f"asgard.eq.{out}") for out in OUTPUTS) + "]\n")


def conf_text(st):
    changed = [out for out in OUTPUTS if not is_default(st, out)]
    if not changed:
        return None
    out = "# Written by asgard-eq.py (Settings > Hardware > Audio); delete to go back to the Thor's own EQ.\n"
    out += "context.properties = { " + " ".join(f'asgard.eq.{o} = "{st.get(o, "thor")}"' for o in changed) + " }\n"
    return out + "context.modules = [\n" + "".join(module(st, o) for o in changed) + "]\n"


def game(st, speaker, headphones):
    """The saved state with a game's overrides on top; "default" (or anything unknown) keeps the saved value, and
    autoeq without a downloaded profile does too."""
    eff = dict(st)
    for out, mode in (("speaker", speaker), ("headphones", headphones)):
        if mode in MODES[out] and (mode != "autoeq" or st.get("peq")):
            eff[out] = mode
    return eff


def override():
    try:
        with open(OVERRIDE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def effective(st):
    ov = override()
    return game(st, ov.get("speaker", "default"), ov.get("headphones", "default"))


def run(args):
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None


def node_ids():
    """thor_dsp_<output> -> PipeWire id, of the running filters."""
    r = run(["pw-dump"])
    try:
        objs = json.loads(r.stdout) if r and r.returncode == 0 else []
    except ValueError:
        objs = []
    ids = {}
    for o in objs:
        name = ((o.get("info") or {}).get("props") or {}).get("node.name")
        if name in (f"thor_dsp_{out}" for out in OUTPUTS) and o.get("type") == "PipeWire:Interface:Node":
            ids[name] = o["id"]
    return ids


def live(st):
    """Set every value on the running chains. False if one isn't running or isn't of the fixed shape."""
    ids = node_ids()
    for out in OUTPUTS:
        nid = ids.get(f"thor_dsp_{out}")
        if nid is None:
            return False
        r = run(["pw-cli", "enum-params", str(nid), "Props"])
        shape = f'"sel{"L"}:Gain {4 if out == "speaker" else 2}"', f'"t{len(TONE) - 1}R:b0"', f'"s{SLOTS - 1}R:b0"'
        if not r or r.returncode != 0 or not all(s in r.stdout for s in shape):
            return False
        params = " ".join(f'"{k}" {num(x)}' for k, x in values(st, out).items())
        r = run(["pw-cli", "set-param", str(nid), "Props", f"{{ params = [ {params} ] }}"])
        if not r or r.returncode != 0:
            return False
    return True


def write_conf(text):
    """True if 60-asgard-eq.conf changed."""
    try:
        with open(CONF) as f:
            old = f.read()
    except OSError:
        old = None
    if text == old:
        return False
    if text is None:
        os.remove(CONF)
    else:
        os.makedirs(os.path.dirname(CONF), exist_ok=True)
        with open(CONF + ".tmp", "w") as f:
            f.write(text)
        os.replace(CONF + ".tmp", CONF)
    return True


def restart():
    # The filter-chains are read at PipeWire's start: a ~2 s gap in any playing audio, and SDL3 games lose their sound.
    run(["systemctl", "restart", "pipewire", "pipewire-pulse", "wireplumber"])


def apply(st, save=True):
    """Save the state, write the config for the next start, and set the values on the running chains. Only chains of
    another shape need the restart, and a running game keeps its sound: it waits (later = True) for the next launch."""
    if save:
        os.makedirs(os.path.dirname(STATE), exist_ok=True)
        tmp = STATE + ".tmp"
        with open(tmp, "w") as f:
            json.dump(st, f)
        os.replace(tmp, STATE)
    eff = effective(st)
    changed = write_conf(conf_text(eff))
    if live(eff):
        return {"ok": True}
    if os.path.exists(PLAYING):
        return {"ok": True, "later": True}
    if changed:
        restart()
    return {"ok": True}


def output():
    """Which output plays now: speaker, headphones (the jack) or bluetooth."""
    r = run(["pw-metadata", "0", "default.audio.sink"])
    text = r.stdout if r else ""
    return "headphones" if HEADPHONES_SINK in text else "bluetooth" if "bluez_output" in text else "speaker"


def fetch(url):
    with urllib.request.urlopen(url, timeout=15) as r:
        return r.read().decode("utf-8", "replace")


def search(query, index):
    """Index lines: - [Name](./source/rig/Name) by source[ on rig]"""
    words = query.lower().split()
    hits = []
    for m in re.finditer(r"^- \[(.+?)\]\(\./(.+?)\) by (.+)$", index, re.M):
        name, path, by = m.groups()
        if words and all(w in name.lower() for w in words):
            src = by.split(" on ")[0]
            rank = SOURCES.index(src) if src in SOURCES else len(SOURCES)
            hits.append((not name.lower().startswith(words[0]), rank, name, {"name": name, "by": by, "path": urllib.parse.unquote(path)}))
    hits.sort(key=lambda h: h[:3])
    return [h[3] for h in hits[:30]]


def main(argv):
    st = load_state()
    cmd = argv[1] if len(argv) > 1 else "status"
    if cmd == "status":
        ov = {k: v for k, v in override().items() if v in MODES.get(k, ())}
        return {"speaker": st.get("speaker", "thor"), "headphones": st.get("headphones", "thor"),
                "headphones_name": st.get("headphones_name", ""), "saved": sorted(st.get("profiles", {}), key=str.lower),
                "tone": {out: tone_of(st, out) for out in OUTPUTS}, "game": ov, "output": output()}
    if cmd == "set" and len(argv) == 4 and argv[2] in MODES and argv[3] in MODES[argv[2]]:
        if argv[3] == "autoeq" and not st.get("peq"):
            return {"error": "No AutoEQ profile chosen yet"}
        st[argv[2]] = argv[3]
        return apply(st) or {"ok": True}
    if cmd == "tone" and len(argv) == 6 and argv[2] in MODES:
        try:
            t = [float(x) for x in argv[3:6]]
        except ValueError:
            t = None
        if t is None or any(abs(x) > TONE_MAX for x in t):
            return {"error": f"tone: three numbers from -{TONE_MAX} to {TONE_MAX} (dB)"}
        st.setdefault("tone", {})[argv[2]] = t
        return apply(st) or {"ok": True}
    if cmd == "game" and len(argv) == 4:
        ov = {out: mode for out, mode in zip(OUTPUTS, argv[2:4]) if mode in MODES[out]}
        if ov:
            with open(OVERRIDE + ".tmp", "w") as f:
                json.dump(ov, f)
            os.replace(OVERRIDE + ".tmp", OVERRIDE)
        elif os.path.exists(OVERRIDE):
            os.remove(OVERRIDE)
        apply(st, save=False)
        return {"ok": True}
    if cmd == "regen":
        if write_conf(conf_text(effective(st))):
            restart()
        return {"ok": True}
    if cmd == "search" and len(argv) >= 3:
        try:
            return {"results": search(" ".join(argv[2:]), fetch(RAW + "INDEX.md"))}
        except OSError:
            return {"error": "No internet connection: AutoEQ needs it to search"}
    if cmd == "autoeq" and len(argv) == 4:
        path, name = argv[2], argv[3]
        try:
            peq = fetch(RAW + urllib.parse.quote(f"{path}/{os.path.basename(path)} ParametricEQ.txt"))
        except OSError:
            return {"error": "No internet connection: AutoEQ needs it to download the profile"}
        if not parse_peq(peq)[1]:
            return {"error": "That profile has no parametric EQ"}
        st.update(headphones="autoeq", headphones_name=name, peq=peq)
        st.setdefault("profiles", {})[name] = peq
        return apply(st) or {"ok": True}
    if cmd == "use" and len(argv) == 3:
        peq = st.get("profiles", {}).get(argv[2])
        if not peq:
            return {"error": "No saved profile named " + argv[2]}
        st.update(headphones="autoeq", headphones_name=argv[2], peq=peq)
        return apply(st) or {"ok": True}
    return {"error": "usage: status | set speaker|headphones thor|off|autoeq | tone <output> <bass> <mid> <treble> | search <text> | "
                     "autoeq <path> <name> | use <name> | game <speaker> <headphones> | regen | default-conf"}


if __name__ == "__main__":
    if sys.argv[1:] == ["default-conf"]:
        sys.stdout.write(default_conf())
    else:
        print(json.dumps(main(sys.argv)))
