#!/usr/bin/env python3
# spec: CFG-5 CFG-6
"""Tree check over Asgard's own code (packages/asgard, packages/asgard-home): a setting it reads or writes is `asgard.*`,
one of ROCKNIX's names below, or a game option; and a path under /storage/.config is Asgard's or a known other program's.
Adding to these lists is a decision that CFG-5 or CFG-6 allows it: a new setting takes the prefix, new state goes in
asgard/, and logs go in thor/."""
import glob
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
PACKAGES = os.path.abspath(os.path.join(HERE, "../.."))

# ROCKNIX's existing keys that Asgard reads or writes (CFG-5: these names stay), each present at the fork point.
ROCKNIX = """
analogsticks.led audio.volume bluetooth.enabled cooling.profile display.brightness2 global.retroachievements
global.retroachievements.hardcore global.retroachievements.password global.retroachievements.username led.color
root.password system.hostname system.suspendmode system.timezone tailscale.up wifi.enabled wifi.key wifi.ssid zerotier.up
""".split()
# Known not to follow CFG-5: test_setting_names.py holds them to it, so they don't fail here too.
KNOWN = """
asgardos.bottomscreen.type global.retroachievements.webapikey screenscraper.devid screenscraper.devpassword
screenscraper.password screenscraper.username
""".split()

FILES = [p for pattern in ("asgard/sources/*.py", "asgard/sources/*.sh", "asgard/autostart/*", "asgard/sleep.d/*",
                           "asgard-home/src/*.cpp", "asgard-home/src/qml/*.qml")
         for p in glob.glob(os.path.join(PACKAGES, pattern))
         if not os.path.basename(p).startswith("test_")]
assert len(FILES) > 30, FILES


def read(path):
    with open(path, errors="replace") as f:
        return f.read()


# --- CFG-5. A key is what these calls name literally; `name` patterns are for a key built from a literal and a variable.
SHELL_CALLS = [r'\b(?:get_setting|set_setting|setkey)\s+"?([a-z][\w.]*)']
CODE_CALLS = [r'\bconf\.(?:get|set)\(\s*"([a-z][\w.]*)"',                  # thor_panel.py, thor_settings.py
              r'\bsetting\(\s*(?:m_root,\s*)?"([a-z][\w.]*)"']             # Backend, Files, Music, motiond
QML_CALLS = [r'\b(?:get|set)\(\s*"([a-z][\w.]*)"',                         # Settings.qml
             r'(?:toggle|choice)\([^\n]*?"((?:[a-z][\w]*\.)+[a-z][\w.]*)"']  # its rows name their key
# A game option is a suffix of <system>.<key>, read as get_setting <key> <system> <game>: CFG-12 and thor_settings' PERF_FEATURES
# name these, and they stay short for ROCKNIX's option rows to work. Everything else has to be dotted.
# screen_filter: VID-1's per-game and per-system option (asgard-screen-filter.sh), with asgard.screen_filter for the OS.
GAME_OPTION = re.compile(r"^(cpu_cap_\w*|gpu_cap|fan_mode|motion|eq_speaker|eq_headphones|sleep_\w*|top_\w*|bottom_\w*"
                         r"|screen_filter)$")
found = {}
for path in FILES:
    text = read(path)
    kind = os.path.splitext(path)[1]
    if kind not in (".qml", ".py", ".cpp"):
        text = re.sub(r"(^|\s)#.*$", "", text, flags=re.M)   # a shell comment isn't a read
    for call in QML_CALLS + CODE_CALLS if kind == ".qml" else CODE_CALLS if kind in (".py", ".cpp") else SHELL_CALLS:
        for key in re.findall(call, text, re.M):
            found.setdefault(key.rstrip("."), os.path.relpath(path, PACKAGES))
assert not {"asgard.motion", "audio.volume", "motion", "asgard.fan_manual", "system.suspendmode"} - set(found), sorted(found)
bad = {k: where for k, where in found.items()
       if not k.startswith("asgard.") and k not in ROCKNIX + KNOWN and not GAME_OPTION.match(k)}
assert not bad, f"new settings need the asgard. prefix (CFG-5), or the list here if they're ROCKNIX's: {bad}"

# --- CFG-6.
# Other programs' own config, whose location isn't ours to choose. ROCKNIX's are the system/, sway/, profile.d/ ones.
OTHERS = {"asgard", "thor", "autostart", "azahar", "gmu", "gpu-drivers", "mako", "pipewire", "profile.d", "qterminal.org",
          "retroarch", "sway", "system", "wireguard", "zerotier", "zerotier-networks",
          # the emulators asgard-screen-filter.sh writes the screen filter into (VID-1)
          "ARMSX2", "aethersx2", "dolphin-emu", "eden", "flycast", "nanoboyadvance", "ppsspp", "rpcs3", "xemu",
          "Cemu", "melonDS", "Vita3K", "scummvm"}
used = {}
for path in FILES:
    for name in re.findall(r"/storage/\.config/([\w.-]+)", read(path)):
        used.setdefault(name, os.path.relpath(path, PACKAGES))
assert {"asgard", "thor"} <= set(used), used
bad = {k: where for k, where in used.items() if k not in OTHERS}
assert not bad, f"new Asgard state goes in /storage/.config/asgard/, logs in /storage/.config/thor/ (CFG-6): {bad}"
print("config conventions: ok")
