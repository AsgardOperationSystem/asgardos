# spec: PANEL-1 PANEL-2 PANEL-4
# requires: file:build/AsgardOS-SM8550.aarch64/toolchain/usr/local/qt6/lib/libQt6Quick.so cmd:cmake lib:libSDL2-2.0.so.0 lib:libSDL2_ttf-2.0.so.0 lib:libSDL2_image-2.0.so.0
"""Run: python -I test_thor_panel_view.py  (no Thor): Thor Panel's real QML offscreen, talking to the real thor_panel.py --serve
with its settings, readings and commands faked: what it shows and what each button runs. PANEL-1: only that its window is
the bottom screen's, by title and sway rule (test_ayn_button.py has the freezing). Whether the radios and LEDs react: human."""
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "../../../tools/test"))
from home_harness import Root  # noqa: E402

WINDOW = "Thor Panel (Bottom)"
SERVE = """
import json, os, sys
sys.path.insert(0, %r)
sys.dont_write_bytecode = True
import thor_panel as tp
tmp = %r
tp.STATE = tmp + "/state.json"
tp.RA_CFG = tmp + "/retroarch.cfg"
tp.SHOTS = tmp + "/shots"
class Conf:
    file = tmp + "/conf.json"
    def data(self):
        return json.load(open(self.file))
    def get(self, key, default=""):
        return self.data().get(key, default)
    def set(self, key, value):
        d = self.data()
        d.pop(key, None) if value is None else d.__setitem__(key, value)
        json.dump(d, open(self.file, "w"))
tp.conf = Conf()
def run_cmd(cmd, *_):
    open(tmp + "/ran", "a").write(cmd + "\\n")
    return 0, ""
tp.run_cmd = run_cmd
gauge = lambda n, v, u: {"name": n, "value": v, "unit": u, "frac": 0.5}
tp.stats = lambda st: {"temp": 47, "fan": 33, "bat": "87", "charging": False, "net": 1.5, "fps": 59,
                       "gauges": [gauge("CPU", "1.20", "GHz"), gauge("GPU", "300", "MHz"), gauge("PWR", "4.00", "W"), gauge("RAM", "2.00", "GB")]}
real_read = tp.read
tp.read = lambda path, default="": "-9 azahar" if path == "/tmp/.process-kill-data" else real_read(path, default)
tp.serve()
"""

tmp = tempfile.mkdtemp()
serve = f"{tmp}/serve.py"
open(serve, "w").write(SERVE % (HERE, tmp))


def panel(keys, settings=None):
    json.dump(settings or {}, open(f"{tmp}/conf.json", "w"))
    open(f"{tmp}/retroarch.cfg", "w").write('input_rumble_gain = "100"\n')
    if os.path.exists(f"{tmp}/ran"):
        os.remove(f"{tmp}/ran")
    with Root() as r:
        # Python takes a moment to answer the first status, and keys act on its values: Select does nothing here, so it waits.
        res = r.run(" ".join(["select"] * 20 + [keys]), args=["--panel"], env={"ASGARD_PANEL": serve}, ms=800)
    res.shown = res.window(WINDOW)
    res.ran = open(f"{tmp}/ran").read().splitlines() if os.path.exists(f"{tmp}/ran") else []
    res.conf = json.load(open(f"{tmp}/conf.json"))
    return res


# PANEL-1's part: where it goes
first = panel("")
assert first.shown, "no window: " + first.log[-500:]
assert "Bottom" in WINDOW   # ROCKNIX's sway rule for "Bottom" titles puts it on DSI-1 (and test_text_input.py reads that rule)

# PANEL-2, page 1: status, FPS, temperature, the gauges and the fan
for text in ("Current FPS", "59", "47°C", "87%", "CPU", "GPU", "PWR", "RAM", "1.20", "Fan", "Smart"):
    assert text in first.shown, text
fan = panel("down down right")
assert "systemctl restart fancontrol" in fan.ran and fan.conf["cooling.profile"] == "aggressive" and "Sport" in fan.shown
back = panel("down down left")
assert back.conf["cooling.profile"] == "quiet"

# PANEL-4: the toggles, in order, each doing its own thing
labels = ["Wi-Fi", "Airplane mode", "Vibration", "Ambient LED", "Screenshot", "Clean memory", "Quit game", "120 Hz"]
at = [first.shown.index(label) for label in labels]
assert at == sorted(at), first.shown
EFFECTS = {"a": "wifictl disable", "right a": "rfkill block all", "right right right a": "ledcontrol rgb",
           "down a": "grim -o DSI-2", "down right a": "echo 3 > /proc/sys/vm/drop_caches",
           "down right right a": "killall -TERM azahar; killall -CONT azahar",
           "down right right right a": "swaymsg output DSI-2 mode 1080x1920@60Hz"}
for keys, effect in EFFECTS.items():
    ran = panel(keys).ran
    assert any(effect in c for c in ran), (keys, effect, ran)
assert 'input_rumble_gain = "0"' in (panel("right right a") and open(f"{tmp}/retroarch.cfg").read())    # Vibration
refresh = panel("down right right right a")
assert refresh.conf["asgard.refresh"] == "60" and "60 Hz" in refresh.shown                               # the top screen's rate
assert panel("down right right a").rc == 0                                                                # Quit game: "close" ends it

# PANEL-2, page 2: volume and each screen's brightness
page2 = panel("rb")
for text in ("Volume", "Top screen", "Bottom screen", "Linked"):
    assert text in page2.shown, text
assert "Current FPS" not in page2.shown
assert "volume 55" in panel("rb right").ran
# The lock: linked moves both, separate moves the one
linked = panel("rb down right", {"display.brightness2": "50", "display.brightness": "50"})
assert "brightness set 55" in linked.ran and linked.shown.count("55%") == 2
split = {"asgard.brightness_split": "1", "display.brightness2": "50", "display.brightness": "30"}
apart = panel("rb down right", split)
assert "brightness set 2 55" in apart.ran and apart.shown.count("55%") == 1 and "30%" in apart.shown and "Separate" in apart.shown
assert "brightness set 1 35" in panel("rb down down right", split).ran
assert panel("rb up a").conf["asgard.brightness_split"] == "1"                   # the lock, from linked
shutil.rmtree(tmp)
print("ok")
