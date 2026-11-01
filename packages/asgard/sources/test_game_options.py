# spec: OVR-1 OVR-2 OVR-3 OVR-5 GPU-1 GPU-2 GPU-3
# requires: cmd:node lib:libSDL2-2.0.so.0 lib:libSDL2_ttf-2.0.so.0 lib:libSDL2_image-2.0.so.0
"""A game's and a system's settings rows: the real thor_settings.py --features answers, with the real row functions from
Settings.qml run in node against a fake system.cfg. OVR-1 what an unset row says, and that unsetting inherits again. OVR-2 the same
hardware rows for every registered emulator, at both levels, and that the profile script reads each key. OVR-3 the emulator and
core rows and the shader cache action (test_shader_cache.sh: the deleting; test_fake_emulator.py: reaching the launcher). OVR-5
es_features.cfg's options become rows with no code per emulator. GPU-1, 2, 3: the driver rows; test_runemu.py: what they select."""
import contextlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import thor_settings as ts  # noqa: E402

QML = open(f"{HERE}/../../asgard-home/src/qml/Settings.qml").read()
CATALOGUE = f"{HERE}/../../ui/emulationstation/config/common/es_features.cfg"
META = open(f"{HERE}/../../virtual/emulators/package.mk").read()
ts.FEATURES = CATALOGUE
ts.GPU_DRIVERS = ()


def features(emulator, core):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        ts.dump_features(emulator, core)
    return json.loads(out.getvalue())


def function(src, name):
    m = re.search(r"^( *)function " + name + r"\(.*?^\1}", src, re.M | re.S)
    assert m, name
    return m.group(0)


NODE = """
const [cfg, feats, emus] = JSON.parse(process.argv[1])
const get = (k, d) => cfg[k] ? cfg[k] : (d === undefined ? "" : d)
const set = (k, v) => { cfg[k] = v }
const q = v => "'" + v + "'"
const live = {}, shells = []
const coreTypes = ["little", "mid", "prime"]
const features = () => feats
const backend = { emulators: () => emus, playStats: () => ({}) }
const action = (icon, title, sub, run) => ({ kind: "action", title, sub, run })
const info = (icon, title, sub) => ({ kind: "info", title, sub })
const link = (icon, title, sub, page) => ({ kind: "link", title, sub, page })
const sh = (key, cmd) => shells.push(cmd)
%s
const walk = rows => rows.flat().flatMap(r => r.kind === "link" && r.page ? walk(r.page()) : [r])
const out = {}
const req = JSON.parse(process.argv[2])
for (const [name, code] of Object.entries(req)) out[name] = eval(code)
console.log(JSON.stringify({ out, cfg, shells }))
""" % "\n".join(function(QML, f) for f in ("allCoresOff", "optionRow", "optionsPage", "gamePage", "systemPage"))


def node(cfg, feats, requests, emus=()):
    """Runs JS expressions over the row functions; returns ({name: value}, system.cfg afterwards, shell commands)."""
    result = subprocess.run(["node", "-e", NODE, json.dumps([cfg, feats, list(emus)]), json.dumps(requests)],
                            check=True, capture_output=True, text=True)
    r = json.loads(result.stdout)
    return r["out"], r["cfg"], r["shells"]


CAP = {"key": "cpu_cap_mid", "label": "Big cores", "default": "100%", "choices": [["60%", "60"], ["80%", "80"], ["100%", "100"]]}
PLAIN = {"key": "ratio", "label": "Aspect ratio", "choices": [["4/3", "4/3"]]}
GAME, SYSTEM = '3ds["Pokemon X.3ds"]', "3ds"
VALUE = 'optionRow(%s, %s, %s).value'


def game_value(feature, cfg):
    return node(cfg, [feature], {"v": VALUE % (json.dumps(feature), json.dumps(GAME), json.dumps(SYSTEM))})[0]["v"]


# OVR-1: the game's value, else what the row says it takes: the system's, the OS's, or Default.
assert game_value(CAP, {}) == "OS (100%)"
assert game_value(CAP, {"3ds.cpu_cap_mid": "80"}) == "Emulator settings (80%)"
assert game_value(CAP, {"3ds.cpu_cap_mid": "80", f"{GAME}.cpu_cap_mid": "60"}) == "60%"
assert game_value(PLAIN, {}) == "Default"
assert game_value(PLAIN, {"3ds.ratio": "4/3"}) == "Emulator settings (4/3)"
# At the system's own level there's nothing above but the OS.
assert node({}, [CAP], {"v": VALUE % (json.dumps(CAP), json.dumps(SYSTEM), '""')})[0]["v"] == "OS (100%)"
# Unsetting: stepping past the last value clears the game's key, and the row inherits again.
out, cfg, _ = node({"3ds.cpu_cap_mid": "80", f"{GAME}.cpu_cap_mid": "100"}, [CAP], {
    "s": "optionRow(%s, %s, %s).step(1); optionRow(%s, %s, %s).value" % ((json.dumps(CAP), json.dumps(GAME), json.dumps(SYSTEM)) * 2)})
assert cfg[f"{GAME}.cpu_cap_mid"] == "" and out["s"] == "Emulator settings (80%)", (out, cfg)
assert cfg["3ds.cpu_cap_mid"] == "80"   # a game's row leaves the system's key alone

# OVR-2: every emulator add_emu_core registers, whether es_features.cfg knows it or not, offers the same hardware rows.
HARDWARE = {"cpu_cap_little", "cpu_cap_mid", "cpu_cap_prime", "gpu_cap", "fan_mode", "motion", "eq_speaker", "eq_headphones", "sleep_mode"}
registered = {(e, c) for _, e, c, _ in re.findall(r"^\s*add_emu_core\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)", META, re.M)}
assert len(registered) > 100
catalogue = {}
real_load = ts.load_features
ts.load_features = lambda: catalogue or catalogue.update(real_load()) or catalogue   # one parse, not 500
for emulator, core in sorted(registered):
    keys = {f["key"] for f in features(emulator, core)}
    assert HARDWARE <= keys, (emulator, core, sorted(HARDWARE - keys))
ts.load_features = real_load
# At both levels, reached through the same pages, each with its own key.
walked = "walk(optionsPage(%s, 'x', 'y', %s)).map(r => r.title)"
feats = features("azahar", "azahar-sa")
titles = [f["label"] for f in feats]
out, _, _ = node({}, feats, {"game": walked % (json.dumps(GAME), json.dumps(SYSTEM)), "system": walked % (json.dumps(SYSTEM), '""')})
assert out["game"] == out["system"] and set(out["game"]) == set(titles), out
out, cfg, _ = node({}, [CAP], {"g": "optionRow(%s, %s, %s).step(1)" % (json.dumps(CAP), json.dumps(GAME), json.dumps(SYSTEM)),
                               "s": "optionRow(%s, %s, '').step(1)" % (json.dumps(CAP), json.dumps(SYSTEM))})
assert cfg == {f"{GAME}.cpu_cap_mid": "60", "3ds.cpu_cap_mid": "60"}, cfg
# And each of those keys is what the profile script reads for the game.
profile = "\n".join(ln for ln in open(f"{HERE}/asgard-perf-profile.sh") if not ln.lstrip().startswith("#"))
for key in HARDWARE - {"cpu_cap_little", "cpu_cap_mid", "cpu_cap_prime"}:
    assert f'get_setting {key} "$platform" "$game"' in profile or f'get_setting {key} "$1" "$2"' in profile, key
assert 'get_setting "cpu_cap_$t" "$platform" "$game"' in profile

# OVR-5: an option in es_features.cfg is a row, with no code naming it. A made-up emulator proves that; Azahar's are the real ones.
with tempfile.TemporaryDirectory() as d:
    with open(f"{d}/es_features.cfg", "w") as f:
        f.write('<features><emulator name="newemu" features="ratio"><features><feature name="turbo mode">'
                '<choice name="Fast" value="fast"/><choice name="Slow" value="slow"/></feature></features></emulator></features>')
    ts.FEATURES = f"{d}/es_features.cfg"
    feats = features("newemu", "newemu-sa")
    ts.FEATURES = CATALOGUE
by_key = {f["key"]: f for f in feats}
assert by_key["turbo_mode"]["choices"] == [["Fast", "fast"], ["Slow", "slow"]] and "ratio" in by_key, by_key.keys()
out, cfg, _ = node({}, feats, {"titles": walked % (json.dumps(GAME), json.dumps(SYSTEM))})
assert "Turbo mode" in out["titles"] and "Aspect ratio" in out["titles"], out
real = {f["key"] for f in features("azahar", "azahar-sa")}
assert {"screen_layout"} <= real and any("resolution" in k for k in real), sorted(real)
assert "shaderset" in {f["key"] for f in features("retroarch", "mgba")} and "ratio" in {f["key"] for f in features("retroarch", "mgba")}

# OVR-3: a game's Emulator row picks the next one and that emulator's first core, for this game only; its Core row steps; going back
# to the system's clears both; Delete shader cache runs the script on this game. The same at the system's level.
EMUS = [{"name": "retroarch", "cores": ["mgba", "gambatte"]}, {"name": "alt", "cores": ["alt-gba"]}]
G = '{path: "/roms/gba/Metroid.gba", sys: "gba", sysName: "GBA", emulator: "retroarch", core: "mgba"}'
K = 'gba["Metroid.gba"]'
PAGE = f"gamePage({G})"
out, cfg, _ = node({}, [], {"x": f"{PAGE}[0][0].step(1)"}, EMUS)
assert cfg == {f"{K}.emulator": "alt", f"{K}.core": "alt-gba"}, cfg
out, cfg, _ = node({}, [], {"x": f"{PAGE}[0][1].step(1)"}, EMUS)
assert cfg == {f"{K}.emulator": "retroarch", f"{K}.core": "gambatte"}, cfg
out, cfg, _ = node({f"{K}.emulator": "alt", f"{K}.core": "alt-gba"}, [], {"title": f"{PAGE}[0][1].title", "x": f"{PAGE}[0][1].run()"}, EMUS)
assert out["title"].startswith("Use GBA") and cfg == {f"{K}.emulator": "", f"{K}.core": ""}, (out, cfg)
out, _, shells = node({}, [], {"x": f"{PAGE}[1].find(r => r.title === 'Delete shader cache').run()"}, EMUS)
assert shells == ["/usr/share/asgard/asgard-shader-cache.sh 'gba' '/roms/gba/Metroid.gba' 2>&1"], shells
S = '{name: "gba", fullname: "GBA", emulator: "retroarch", core: "mgba"}'
out, cfg, _ = node({}, [], {"x": f"systemPage({S}).flat()[0].step(1)"}, EMUS)
assert cfg == {"gba.emulator": "alt", "gba.core": "alt-gba"}, cfg

# GPU-1, GPU-2: the driver row lists both places' builds, the image's and the user's; unset names the image's Mesa.
with tempfile.TemporaryDirectory() as d:
    for path in ("image/mesa-25.3.6", "user/mine", "user/no-icd"):
        os.makedirs(f"{d}/{path}")
    open(f"{d}/image/mesa-25.3.6/icd.json", "w").close()
    open(f"{d}/user/mine/icd.json", "w").close()
    ts.GPU_DRIVERS = (f"{d}/user", f"{d}/image", f"{d}/not-there")
    ts.open = lambda path, *a: io.StringIO("mesa-26.2.6\n") if path == "/usr/share/mesa/version" else open(path, *a)
    row = next(f for f in features("azahar", "azahar-sa") if f["key"] == "gpu_driver")
    assert row["choices"] == [["mesa-25.3.6", "mesa-25.3.6"], ["mine", "mine"]], row
    assert row["default"] == "mesa-26.2.6", row
    out, _, _ = node({}, [row], {"v": VALUE % (json.dumps(row), json.dumps(GAME), json.dumps(SYSTEM))})
    assert out["v"] == "OS (mesa-26.2.6)", out
    # An emulator es_features.cfg doesn't know gets it too.
    assert "gpu_driver" in {f["key"] for f in features("amiberry", "amiberry")}
    del ts.open
    ts.GPU_DRIVERS = ()
assert ("/storage/.config/gpu-drivers", "/usr/lib/gpu-drivers") == tuple(
    re.search(r'^GPU_DRIVERS = \("(.*?)", "(.*?)"\)', open(f"{HERE}/thor_settings.py").read(), re.M).groups())

# GPU-3: OpenGL's row offers the native driver, with Zink for a system's game to go back to, and unset names Zink.
row = next(f for f in features("azahar", "azahar-sa") if f["key"] == "gl_driver")
assert ["freedreno", "zink"] == [c[1] for c in row["choices"]] and row["default"] == "Zink", row
print("ok")
