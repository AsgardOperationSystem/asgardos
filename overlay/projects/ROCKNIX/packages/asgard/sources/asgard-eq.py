#!/usr/bin/env python3
# Speaker / headphone EQ for Settings > Hardware > Audio. Prints JSON.
#   asgard-eq.py status                  {"speaker": "thor"|"joey"|"off", "headphones": "thor"|"off"|"autoeq", "headphones_name": ...}
#   asgard-eq.py set speaker thor|joey|off, set headphones thor|off|autoeq
#   asgard-eq.py search <text>           AutoEQ profiles whose name has every word (needs internet)
#   asgard-eq.py autoeq <path> <name>    download that profile's ParametricEQ.txt and use it for the headphones
# The Thor's own curves are 50-thor-dsp.conf (system); each module there loads only while asgard.eq.<output> is unset.
# We write 60-asgard-eq.conf: that property for every output not on "thor", plus the AutoEQ filter-chain, as the same
# smart filter (thor_dsp_headphones) so PipeWire routing is unchanged. PipeWire 1.2.6's parametric-equalizer module
# ignores capture.props (it named its node effect_input.eq11), so the ParametricEQ.txt is turned into biquads here.
import json, os, re, subprocess, sys, urllib.parse, urllib.request

STATE = "/storage/.config/asgard/eq.json"
CONF = "/storage/.config/pipewire/pipewire.conf.d/60-asgard-eq.conf"
RAW = "https://raw.githubusercontent.com/jaakkopasanen/AutoEq/master/results/"
HEADPHONES_SINK = "alsa_output._sys_devices_platform_sound_sound_card0.HiFi__Headphones__sink"
SPEAKER_SINK = "alsa_output._sys_devices_platform_sound_sound_card0.HiFi__Speaker__sink"
TYPES = {"PK": "bq_peaking", "PEQ": "bq_peaking", "LSC": "bq_lowshelf", "LS": "bq_lowshelf",
         "HSC": "bq_highshelf", "HS": "bq_highshelf"}
# Sources by measurement quality, for the result order (AutoEQ lists one entry per source and rig).
SOURCES = ["oratory1990", "crinacle", "Rtings", "Innerfidelity", "HypetheSonics", "Headphone.com Legacy"]


def load_state():
    try:
        with open(STATE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


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


def peq_graph(pre, filters):
    """ParametricEQ as a graph: preamp (a mixer gain), then the biquads, per channel."""
    nodes, links, out = [], [], {}
    for ch in "LR":
        nodes.append(f'{{ type = builtin name = pre{ch} label = mixer control = {{ "Gain 1" = {10 ** (pre / 20):.6f} }} }}')
        prev = f"pre{ch}:Out"
        for i, (label, fc, q, gain) in enumerate(filters):
            nodes.append(f'{{ type = builtin name = f{i}{ch} label = {label} control = {{ "Freq" = {fc} "Q" = {q} "Gain" = {gain} }} }}')
            links.append(f'{{ output = "{prev}" input = "f{i}{ch}:In" }}')
            prev = f"f{i}{ch}:Out"
        out[ch] = prev
    return nodes, links, ["preL:In 1", "preR:In 1"], [out["L"], out["R"]]


def joey_graph():
    """Joey's Retro Handhelds JamesDSP speaker preset: GraphicEQ with its +15 dB output gain (eq/joey-speaker.wav,
    from eq/gen-speaker-ir.py), its stereo widener (width 2: L' = 1.5 L - 0.5 R), then a -0.1 dB limiter, 500 ms."""
    ir = "/usr/share/asgard/eq/joey-speaker.wav"
    nodes = [f'{{ type = builtin name = conv{c} label = convolver config = {{ filename = "{ir}" channel = 0 }} }}' for c in "LR"]
    nodes += [f'{{ type = builtin name = wide{c} label = mixer control = {{ "Gain 1" = 1.5 "Gain 2" = -0.5 }} }}' for c in "LR"]
    nodes.append('{ type = ladspa name = lim plugin = "/usr/lib/ladspa/asgard-limiter.so" label = asgard_limiter '
                 'control = { "Threshold (dB)" = -0.1 "Release (ms)" = 500 } }')
    links = ['{ output = "convL:Out" input = "wideL:In 1" }', '{ output = "convR:Out" input = "wideL:In 2" }',
             '{ output = "convR:Out" input = "wideR:In 1" }', '{ output = "convL:Out" input = "wideR:In 2" }',
             '{ output = "wideL:Out" input = "lim:In L" }', '{ output = "wideR:Out" input = "lim:In R" }']
    return nodes, links, ["convL:In", "convR:In"], ["lim:Out L", "lim:Out R"]


def chain(graph, name, desc, target):
    """A stereo filter-chain module around a graph, as the smart filter in front of target."""
    nodes, links, inputs, outputs = graph
    q = lambda xs: " ".join(f'"{x}"' for x in xs)
    return f'''  {{ name = libpipewire-module-filter-chain
    args = {{
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


def conf_text(st):
    props = [f'asgard.eq.{k} = "{st[k]}"' for k in ("speaker", "headphones") if st.get(k, "thor") != "thor"]
    if not props:
        return None
    out = "# Written by asgard-eq.py (Settings > Hardware > Audio); delete to go back to the Thor's own EQ.\n"
    out += "context.properties = { " + " ".join(props) + " }\n"
    mods = []
    if st.get("speaker") == "joey":
        mods.append(chain(joey_graph(), "thor_dsp_speaker", "Thor DSP (Speaker, Joey)", SPEAKER_SINK))
    if st.get("headphones") == "autoeq" and st.get("peq"):
        mods.append(chain(peq_graph(*parse_peq(st["peq"])), "thor_dsp_headphones",
                          "AutoEQ: " + st.get("headphones_name", ""), HEADPHONES_SINK))
    if mods:
        out += "context.modules = [\n" + "".join(mods) + "]\n"
    return out


def apply(st):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    tmp = STATE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(st, f)
    os.replace(tmp, STATE)
    text = conf_text(st)
    if text is None:
        if os.path.exists(CONF):
            os.remove(CONF)
    else:
        os.makedirs(os.path.dirname(CONF), exist_ok=True)
        with open(CONF + ".tmp", "w") as f:
            f.write(text)
        os.replace(CONF + ".tmp", CONF)
    # The filter-chains are read at PipeWire's start: a ~2 s gap in any playing audio.
    subprocess.run(["systemctl", "restart", "pipewire", "pipewire-pulse", "wireplumber"], check=False)


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
        return {"speaker": st.get("speaker", "thor"), "headphones": st.get("headphones", "thor"),
                "headphones_name": st.get("headphones_name", "")}
    if cmd == "set" and len(argv) == 4 and (argv[2], argv[3]) in {(o, m) for o in ("speaker", "headphones") for m in ("thor", "off")} | {
            ("speaker", "joey"), ("headphones", "autoeq")}:
        if argv[3] == "autoeq" and not st.get("peq"):
            return {"error": "No AutoEQ profile chosen yet"}
        st[argv[2]] = argv[3]
        apply(st)
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
        apply(st)
        return {"ok": True}
    return {"error": "usage: status | set speaker|headphones thor|off|autoeq | search <text> | autoeq <path> <name>"}


if __name__ == "__main__":
    print(json.dumps(main(sys.argv)))
