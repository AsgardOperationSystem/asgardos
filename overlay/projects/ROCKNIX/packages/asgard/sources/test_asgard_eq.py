#!/usr/bin/env python3
# python3 test_asgard_eq.py: ParametricEQ parsing, the generated filter-chain, the index search, game overrides (offline).
import importlib.util, os

spec = importlib.util.spec_from_file_location("eq", os.path.join(os.path.dirname(os.path.abspath(__file__)), "asgard-eq.py"))
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

# Thor curves only: no file. Speaker off: the property and no module. AutoEQ: the property and the chain.
assert eq.conf_text({}) is None and eq.conf_text({"speaker": "thor", "headphones": "thor"}) is None
t = eq.conf_text({"speaker": "off"})
assert 'asgard.eq.speaker = "off"' in t and "context.modules" not in t, t
t = eq.conf_text({"headphones": "autoeq", "headphones_name": "HD 600", "peq": PEQ})
assert 'asgard.eq.headphones = "autoeq"' in t and 'node.name = "thor_dsp_headphones"' in t and "AutoEQ: HD 600" in t
assert 'outputs = [ "f2L:Out" "f2R:Out" ]' in t and '"Gain 1" = 0.484172' in t, t        # 10^(-6.3/20)
assert t.count("{") == t.count("}") and t.count("[") == t.count("]")
assert eq.HEADPHONES_SINK in t

INDEX = """# Index
- [Sennheiser HD 600](./Super%20Review/over-ear/Sennheiser%20HD%20600) by Super Review
- [Sennheiser HD 600](./oratory1990/over-ear/Sennheiser%20HD%20600) by oratory1990
- [Sennheiser HD 650](./oratory1990/over-ear/Sennheiser%20HD%20650) by oratory1990
- [Apple AirPods Pro](./crinacle/711%20in-ear/Apple%20AirPods%20Pro) by crinacle on 711
"""
r = eq.search("hd 600", INDEX)
assert [x["by"] for x in r] == ["oratory1990", "Super Review"] and r[0]["path"] == "oratory1990/over-ear/Sennheiser HD 600", r
assert [x["name"] for x in eq.search("airpods", INDEX)] == ["Apple AirPods Pro"] and eq.search("", INDEX) == []
t = eq.conf_text({"speaker": "joey"})
assert 'asgard.eq.speaker = "joey"' in t and 'node.name = "thor_dsp_speaker"' in t and eq.SPEAKER_SINK in t, t
assert "asgard-limiter.so" in t and "joey-speaker.wav" in t and 'outputs = [ "lim:Out L" "lim:Out R" ]' in t, t
assert t.count("{") == t.count("}") and t.count("[") == t.count("]")
assert eq.main(["x", "set", "speaker", "autoeq"])["error"].startswith("usage") and eq.main(["x", "set", "headphones", "joey"])["error"].startswith("usage")

# Saved profiles: an old state (one peq, no "profiles") keeps its profile; "use" needs a saved name.
import tempfile
d = tempfile.mkdtemp()
eq.STATE = os.path.join(d, "eq.json")
open(eq.STATE, "w").write('{"headphones": "off", "headphones_name": "HD 600", "peq": "x"}')
assert eq.load_state()["profiles"] == {"HD 600": "x"} and eq.main(["x", "status"])["saved"] == ["HD 600"]
assert eq.main(["x", "use", "HD 650"])["error"].startswith("No saved")

# A game's override: on top of the saved state, which stays; "default" and autoeq without a profile keep the saved
# value; PipeWire restarts only when the config changes.
st = {"speaker": "joey", "headphones": "off"}
assert eq.game(st, "off", "default") == {"speaker": "off", "headphones": "off"} and st["speaker"] == "joey"
assert eq.game(st, "bogus", "autoeq") == st and eq.game(dict(st, peq=PEQ), "default", "autoeq")["headphones"] == "autoeq"
restarts = []
eq.subprocess.run = lambda *a, **k: restarts.append(a)
eq.CONF = os.path.join(d, "60-asgard-eq.conf")
open(eq.STATE, "w").write('{"speaker": "joey"}')
assert eq.main(["x", "game", "default", "default"]) == {"ok": True} and len(restarts) == 1   # first write
assert eq.main(["x", "game", "default", "default"]) == {"ok": True} and len(restarts) == 1   # unchanged: no restart
eq.main(["x", "game", "thor", "default"]); assert len(restarts) == 2 and not os.path.exists(eq.CONF)   # all Thor: no file
assert eq.load_state() == {"speaker": "joey"}                                                # saved state untouched
eq.main(["x", "game", "default", "default"]); assert len(restarts) == 3 and "joey" in open(eq.CONF).read()
print("ok")
