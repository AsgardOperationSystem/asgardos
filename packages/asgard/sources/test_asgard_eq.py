#!/usr/bin/env python3
# spec: SND-2 SND-3 SND-7
# python3 test_asgard_eq.py: ParametricEQ parsing, the raw biquads against PipeWire's own coefficients, one chain shape
# for every EQ, the shipped 50-thor-dsp.conf, the live change with no restart (a stub pw-cli), game overrides, tone,
# the index search (offline). That the change is heard with no gap in a game's sound is a device check.
import importlib.util, json, os, re, tempfile, types

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("eq", os.path.join(HERE, "asgard-eq.py"))
eq = importlib.util.module_from_spec(spec)
spec.loader.exec_module(eq)

PEQ = """Preamp: -6.3 dB
Filter 1: ON LSC Fc 105 Hz Gain 6.5 dB Q 0.70
Filter 2: ON PK Fc 125 Hz Gain -2.7 dB Q 0.55
Filter 3: OFF PK Fc 8445 Hz Gain 3.3 dB Q 1.61
Filter 4: ON HSC Fc 10000 Hz Gain -3.1 dB Q 0.70
"""
pre, f = eq.parse_peq(PEQ)
assert pre == -6.3 and f == [("bq_lowshelf", 105, 0.7, 6.5), ("bq_peaking", 125, 0.55, -2.7), ("bq_highshelf", 10000, 0.7, -3.1)], f

# --- Raw biquads: PipeWire 1.2.6's coefficients for the same filters (read from a Thor's running chain, 2026-11-08:
# pw-cli enum-params on thor_dsp_headphones, b0 b1 b2 a1 a2), so a profile sounds as it did with bq_peaking & co.
PIPEWIRE = {("bq_lowshelf", 105.0, 0.7, 7.4): (1.004180, -1.984209, 0.980316, -1.984291, 0.984414),
            ("bq_peaking", 2028.0, 1.63, 5.6): (1.049881, -1.823622, 0.839940, -1.823622, 0.889822),
            ("bq_peaking", 72.0, 0.25, -4.2): (0.991012, -1.953030, 0.962104, -1.953030, 0.953116),
            ("bq_highshelf", 10000.0, 0.7, -4.7): (0.731932, -0.110869, 0.128551, -0.459540, 0.209154)}
for filt, want in PIPEWIRE.items():
    got = eq.biquad(*filt)
    assert all(abs(a - b) < 2e-6 for a, b in zip(got, want)), (filt, got)
assert eq.biquad("bq_lowshelf", 105, 0.1, 7.4) == eq.biquad("bq_lowshelf", 105, 5, 7.4), "PipeWire's shelves ignore Q"


def response(coefs, freq):
    """|H| in dB of a cascade of (b0, b1, b2, a1, a2) at freq."""
    import cmath, math
    z = cmath.exp(-2j * math.pi * freq / eq.RATE)
    h = 1
    for b0, b1, b2, a1, a2 in coefs:
        h *= (b0 + b1 * z + b2 * z * z) / (1 + a1 * z + a2 * z * z)
    return 20 * math.log10(abs(h))


# Tone: +6 dB bass is +6 at 20 Hz and about nothing at 1 kHz; 0 dB everywhere is flat.
bass = [eq.biquad(lab, fc, q, g) for (lab, fc, q), g in zip(eq.TONE, (6, 0, 0))]
assert abs(response(bass, 20) - 6) < 0.3 and abs(response(bass, 1000)) < 0.3, (response(bass, 20), response(bass, 1000))
flat = [eq.biquad(lab, fc, q, 0) for lab, fc, q in eq.TONE]
assert all(abs(response(flat, x)) < 1e-6 for x in (20, 1000, 15000))

# --- One shape for every EQ: the same controls and the same graph, only the values differ (what makes a live change
# possible). Every chain ends in the limiter (AUD-2).
STATES = [{}, {"speaker": "joey"}, {"speaker": "off"}, {"headphones": "off"},
          {"headphones": "autoeq", "headphones_name": "HD 600", "peq": PEQ}, {"tone": {"speaker": [3, -2, 6], "headphones": [-6, 0, 1]}}]
shape = lambda st, out: re.sub(r"-?\d+(\.\d+)?(e-?\d+)?", "N", "\n".join(sum((list(x) for x in eq.graph(st, out)), [])))
for out in eq.OUTPUTS:
    keys = {tuple(eq.values(st, out)) for st in STATES}
    assert len(keys) == 1, f"{out}: the controls differ between EQs"
    assert len({shape(st, out) for st in STATES}) == 1, f"{out}: the graph differs between EQs"
    nodes, links, ins, outs = eq.graph({}, out)
    assert outs == ["lim:Out L", "lim:Out R"] and any("asgard-limiter.so" in n for n in nodes), out

v = eq.values({"speaker": "joey"}, "speaker")
assert [v[f"selL:Gain {i}"] for i in (1, 2, 3, 4)] == [0.0, 0.0, 1.5, -0.5] and v["s0L:b0"] == 1.0 and v["s0L:a1"] == 0.0
v = eq.values({}, "speaker")
assert v["selL:Gain 1"] == 0.7943 and abs(v["s0L:b0"] - eq.biquad("bq_peaking", 25, 2.15, -8)[0]) < 1e-12
v = eq.values({"headphones": "autoeq", "peq": PEQ}, "headphones")
assert abs(v["selL:Gain 1"] - 10 ** (-6.3 / 20)) < 1e-9 and v["s3L:b0"] == 1.0, v["selL:Gain 1"]      # 3 filters, then identity
assert [eq.values({}, "headphones")[f"selR:Gain {i}"] for i in (1, 2)] == [0.6467, -0.0844]

# --- The shipped 50-thor-dsp.conf is the generator's, each module behind its asgard.eq.<output>.
SHIPPED = open(os.path.join(HERE, "../pipewire/50-thor-dsp.conf")).read()
assert SHIPPED == eq.default_conf(), "50-thor-dsp.conf is stale: python3 asgard-eq.py default-conf > ../pipewire/50-thor-dsp.conf"
assert SHIPPED.count("condition = [ { asgard.eq.speaker = null } ]") == 1 and SHIPPED.count("condition = [ { asgard.eq.headphones = null } ]") == 1

# --- 60-asgard-eq.conf: none on the defaults; an output off its defaults gets its property and its chain.
assert eq.conf_text({}) is None and eq.conf_text({"speaker": "thor", "headphones": "thor", "tone": {"speaker": [0, 0, 0]}}) is None
t = eq.conf_text({"speaker": "off"})
assert 'asgard.eq.speaker = "off"' in t and t.count("libpipewire-module-filter-chain") == 1 and 'node.name = "thor_dsp_speaker"' in t
t = eq.conf_text({"headphones": "autoeq", "headphones_name": "HD 600", "peq": PEQ})
assert 'asgard.eq.headphones = "autoeq"' in t and 'node.name = "thor_dsp_headphones"' in t and "AutoEQ: HD 600" in t and eq.HEADPHONES_SINK in t
t = eq.conf_text({"tone": {"headphones": [2, 0, 0]}})
assert 'asgard.eq.headphones = "thor"' in t and "thor_dsp_speaker" not in t, "tone alone needs its own chain"
for st in STATES[1:]:
    t = eq.conf_text(st)
    assert t.count("{") == t.count("}") and t.count("[") == t.count("]"), st

INDEX = """# Index
- [Sennheiser HD 600](./Super%20Review/over-ear/Sennheiser%20HD%20600) by Super Review
- [Sennheiser HD 600](./oratory1990/over-ear/Sennheiser%20HD%20600) by oratory1990
- [Sennheiser HD 650](./oratory1990/over-ear/Sennheiser%20HD%20650) by oratory1990
- [Apple AirPods Pro](./crinacle/711%20in-ear/Apple%20AirPods%20Pro) by crinacle on 711
"""
r = eq.search("hd 600", INDEX)
assert [x["by"] for x in r] == ["oratory1990", "Super Review"] and r[0]["path"] == "oratory1990/over-ear/Sennheiser HD 600", r
assert [x["name"] for x in eq.search("airpods", INDEX)] == ["Apple AirPods Pro"] and eq.search("", INDEX) == []
assert eq.main(["x", "set", "speaker", "autoeq"])["error"].startswith("usage") and eq.main(["x", "set", "headphones", "joey"])["error"].startswith("usage")

# --- A stub PipeWire: pw-dump lists both filters, pw-cli reports their controls (the fixed shape, or an older one).
d = tempfile.mkdtemp()
eq.STATE, eq.CONF = os.path.join(d, "eq.json"), os.path.join(d, "60-asgard-eq.conf")
eq.OVERRIDE, eq.PLAYING = os.path.join(d, "eq-game.json"), os.path.join(d, "playing")
pw = {"shape": True, "calls": []}


def fake_run(args):
    pw["calls"].append(args)
    ok = lambda out="": types.SimpleNamespace(returncode=0, stdout=out)
    if args[0] == "pw-dump":
        return ok(json.dumps([{"id": 40, "type": "PipeWire:Interface:Node", "info": {"props": {"node.name": "thor_dsp_speaker"}}},
                              {"id": 42, "type": "PipeWire:Interface:Node", "info": {"props": {"node.name": "thor_dsp_headphones"}}}]))
    if args[:2] == ["pw-cli", "enum-params"]:
        out = "speaker" if args[2] == "40" else "headphones"
        return ok("".join(f'String "{k}"\n' for k in eq.values({}, out)) if pw["shape"] else 'String "f0L:Gain"\n')
    if args[0] == "pw-metadata":
        return ok(f"update: id:0 key:'default.audio.sink' value:'{{\"name\":\"{eq.HEADPHONES_SINK}\"}}'")
    return ok()


eq.run = fake_run
calls = lambda verb: [c for c in pw["calls"] if verb in c]

# Old state formats: one peq and no "profiles" keeps its profile; "use" needs a saved name.
open(eq.STATE, "w").write('{"headphones": "off", "headphones_name": "HD 600", "peq": "x"}')
assert eq.load_state()["profiles"] == {"HD 600": "x"} and eq.main(["x", "status"])["saved"] == ["HD 600"]
assert eq.main(["x", "use", "HD 650"])["error"].startswith("No saved")

# Live: the values go to both running chains, and PipeWire doesn't restart.
open(eq.STATE, "w").write("{}")
assert eq.main(["x", "set", "speaker", "joey"]) == {"ok": True}
sets = calls("set-param")
assert [c[2] for c in sets] == ["40", "42"] and not calls("systemctl"), pw["calls"]
assert '"selL:Gain 3" 1.5' in sets[0][4] and '"s11R:a2"' in sets[0][4] and sets[0][4].startswith("{ params = [ "), sets[0][4][:80]
assert json.load(open(eq.STATE))["speaker"] == "joey" and 'asgard.eq.speaker = "joey"' in open(eq.CONF).read()

# Tone: saved per output, set live, and refused outside -6..6.
pw["calls"] = []
assert eq.main(["x", "tone", "headphones", "2", "0", "-1"]) == {"ok": True} and json.load(open(eq.STATE))["tone"]["headphones"] == [2, 0, -1]
assert len(calls("set-param")) == 2 and not calls("systemctl")
assert "error" in eq.main(["x", "tone", "headphones", "7", "0", "0"]) and "error" in eq.main(["x", "tone", "speaker", "a", "0", "0"])
s = eq.main(["x", "status"])
assert s["tone"] == {"speaker": [0, 0, 0], "headphones": [2, 0, -1]} and s["output"] == "headphones" and s["game"] == {}, s

# A chain of an older shape: restart only if the config changed, and never while a game plays (it waits: later).
pw["shape"], pw["calls"] = False, []
assert eq.main(["x", "set", "speaker", "off"]) == {"ok": True} and len(calls("systemctl")) == 1
pw["calls"] = []
eq.main(["x", "set", "speaker", "off"]); assert not calls("systemctl"), "unchanged config, restarted anyway"
open(eq.PLAYING, "w").close()
assert eq.main(["x", "set", "speaker", "joey"]) == {"ok": True, "later": True} and not calls("systemctl")
os.remove(eq.PLAYING)
pw["shape"] = True

# A game's override: on top of the saved state, which stays; "default" and autoeq without a profile keep the saved
# value; a change meanwhile keeps the override in what plays; "game default default" ends it.
st = {"speaker": "joey", "headphones": "off"}
assert eq.game(st, "off", "default") == {"speaker": "off", "headphones": "off"} and st["speaker"] == "joey"
assert eq.game(st, "bogus", "autoeq") == st and eq.game(dict(st, peq=PEQ), "default", "autoeq")["headphones"] == "autoeq"
open(eq.STATE, "w").write('{"speaker": "joey"}')
pw["calls"] = []
assert eq.main(["x", "game", "off", "default"]) == {"ok": True} and json.load(open(eq.OVERRIDE)) == {"speaker": "off"}
assert '"selL:Gain 1" 1 ' in calls("set-param")[0][4] and not calls("systemctl")        # off: straight through
assert eq.main(["x", "status"])["game"] == {"speaker": "off"}
pw["calls"] = []
eq.main(["x", "set", "headphones", "off"])
assert '"selL:Gain 3" 0 ' in calls("set-param")[0][4], "a change during the game dropped its override"
assert json.load(open(eq.STATE)) == {"speaker": "joey", "headphones": "off"}                # saved state: the user's
eq.main(["x", "game", "default", "default"])
assert not os.path.exists(eq.OVERRIDE) and '"selL:Gain 3" 1.5' in calls("set-param")[-2][4]

# regen (post-update): the config from eq.json, restarting only when it changed.
os.remove(eq.CONF)
pw["calls"] = []
eq.main(["x", "regen"]); assert len(calls("systemctl")) == 1 and "joey" in open(eq.CONF).read()
eq.main(["x", "regen"]); assert len(calls("systemctl")) == 1
print("ok")
