#!/usr/bin/env python3
# spec: VID-1
# requires: cmd:bash cmd:python3
"""Run: python -I test_screen_filter.py  (no Thor): asgard-screen-filter.sh against a fake root and system.cfg. The game's
choice beats its system's, which beats Settings > Display's (asgard.screen_filter), and with none it's bilinear; an
unknown value is bilinear too. For each emulator it knows, the right key, in the right section, with the value that
emulator uses for the choice, added when the config doesn't have it yet; a choice it lacks is bilinear. Each start
script calls it, and the option is on that emulator's options. That the picture changes is a human check."""
import os
import re
import subprocess
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "asgard-screen-filter.sh")
# The image's bash is 5.3, where BASH_REMATCH can be local; an older host bash leaves that local empty (test_get_setting.py)
FUNCS = open(os.path.join(HERE, "..", "..", "asgardos", "profile.d", "001-functions")).read() \
    .replace("local -a keys=() BASH_REMATCH", "local -a keys=()")
GAME = "Pokemon.nsp"


def run(root, cfg, *args):
    with open(f"{root}/system.cfg", "w") as f:
        f.write(cfg)
    with open(f"{root}/functions", "w") as f:
        f.write(re.sub(r'^J_CONF=.*$', f'J_CONF="{root}/system.cfg"', FUNCS, flags=re.M))
    p = subprocess.run(["bash", SCRIPT, *args], capture_output=True, text=True,
                       env={**os.environ, "FUNCTIONS": f"{root}/functions", "ROOT": root})
    assert p.returncode == 0, (args, p.stderr)
    return p.stdout.strip()


with tempfile.TemporaryDirectory() as root:
    # precedence
    for cfg, want in (("", "bilinear"), ("asgard.screen_filter=nearest\n", "nearest"),
                      ("asgard.screen_filter=nearest\nswitch.screen_filter=fsr\n", "fsr"),
                      (f'asgard.screen_filter=nearest\nswitch.screen_filter=fsr\nswitch["{GAME}"].screen_filter=sharp\n', "sharp"),
                      ("asgard.screen_filter=bogus\n", "bilinear"),
                      # melonDS's own option, before VID-1, used the same name with 1 / 0
                      ("switch.screen_filter=0\n", "nearest"), ("switch.screen_filter=1\n", "bilinear")):
        got = run(root, cfg, "get", "switch", GAME)
        assert got == want, (cfg, got, want)

    # Eden and Eden Duo: [Renderer] scaling_filter, with \default=false, added to a config that has no [Renderer] yet
    eden = f"{root}/storage/.config/eden"
    os.makedirs(eden)
    for emu, ini in (("eden", "qt-config.ini"), ("eden-duo", "sdl2-config.ini")):
        path = f"{eden}/{ini}"
        with open(path, "w") as f:
            f.write("[UI]\ntheme=dark\n")
        for choice, n in (("nearest", "0"), ("bilinear", "1"), ("fsr", "6"), ("sharp", "1"), ("", "1")):
            run(root, f"switch.screen_filter={choice}\n" if choice else "", "apply", emu, "switch", GAME)
            text = open(path).read()
            section = text.split("[Renderer]", 1)[1]
            assert re.search(rf"^scaling_filter={n}$", section, re.M), (emu, choice, text)
            assert re.search(r"^scaling_filter\\default=false$", section, re.M), (emu, choice, text)
            assert text.count("scaling_filter=") == 1 and text.count("[Renderer]") == 1, (emu, choice, text)
            assert "[UI]\ntheme=dark" in text, text

    # The rest: (emulator, file under root, section or None, {choice: the line it writes}). Each starts from a config that
    # lacks the key (or, for RPCS3's YAML, has it), and a second apply replaces the line rather than adding another.
    S = "storage/.config"
    CASES = [
        ("armsx2", f"{S}/ARMSX2/inis/PCSX2.ini", "EmuCore/GS",
         {"nearest": "linear_present_mode = 0", "bilinear": "linear_present_mode = 1", "sharp": "linear_present_mode = 2",
          "fsr": "linear_present_mode = 1"}),
        ("aethersx2", f"{S}/aethersx2/inis/PCSX2.ini", "EmuCore/GS",
         {"nearest": "linear_present = false", "bilinear": "linear_present = true", "sharp": "linear_present = true"}),
        ("flycast", f"{S}/flycast/emu.cfg", "config",
         {"nearest": "rend.LinearInterpolation = no", "bilinear": "rend.LinearInterpolation = yes"}),
        ("dolphin", f"{S}/dolphin-emu/GFX.ini", "Enhancements",
         {"nearest": "OutputResampling = 0", "bilinear": "OutputResampling = 1", "sharp": "OutputResampling = 5"}),
        ("azahar", f"{S}/azahar/qt-config.ini", "Layout",
         {"nearest": "filter_mode=false", "bilinear": "filter_mode=true"}),
        ("xemu", f"{S}/xemu/xemu.toml", "display", {"nearest": "filtering = 'nearest'", "bilinear": "filtering = 'linear'"}),
        ("ppsspp", f"{S}/ppsspp/PSP/SYSTEM/ppsspp.ini", "DisplayLayout.Landscape",
         {"nearest": "BufferFiltering = 2", "bilinear": "BufferFiltering = 1"}),
        ("nanoboyadvance", f"{S}/nanoboyadvance/config.toml", "video",
         {"nearest": 'filter = "nearest"', "bilinear": 'filter = "linear"'}),
        ("melonds", f"{S}/melonDS/melonDS.ini", "", {"nearest": "ScreenFilter=0", "bilinear": "ScreenFilter=1"}),
        ("vita3k", f"{S}/Vita3K/config.yml", "",
         {"nearest": "screen-filter: Nearest", "bilinear": "screen-filter: Bilinear", "fsr": "screen-filter: FSR"}),
        ("hatarisa", "tmp/hatari/.hatari-temp.cfg", "Screen",
         {"nearest": "nRenderScaleQuality = 0", "bilinear": "nRenderScaleQuality = 1"}),
        ("scummvm-sa", f"{S}/scummvm/scummvm.ini", "scummvm", {"nearest": "filtering=false", "bilinear": "filtering=true"}),
        ("cemu", f"{S}/Cemu/settings.xml", None,
         {"nearest": "    <UpscaleFilter>3</UpscaleFilter>", "bilinear": "    <UpscaleFilter>0</UpscaleFilter>"}),
        ("rpcs3", f"{S}/rpcs3/config.yml", None,
         {"nearest": "  Output Scaling Mode: Nearest", "bilinear": "  Output Scaling Mode: Bilinear",
          "fsr": "  Output Scaling Mode: FidelityFX Super Resolution"}),
    ]
    for emu, rel, section, table in CASES:
        path = f"{root}/{rel}"
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write({"rpcs3": "Video:\n  Renderer: Vulkan\n  Output Scaling Mode: Bilinear\n",
                     "cemu": "<content>\n  <Graphic>\n    <UpscaleFilter>1</UpscaleFilter>\n  </Graphic>\n</content>\n"}.get(emu)
                    or ("Other=1\n" if section == "" else "[Other]\nx = 1\n"))
        for choice, line in list(table.items()) * 2:
            run(root, f"psx.screen_filter={choice}\n", "apply", emu, "psx", GAME)
            text = open(path).read()
            body = text if not section else text.split(f"[{section}]\n", 1)[1].split("\n[", 1)[0]
            assert line in body.splitlines(), (emu, choice, text)
            key = line.split("=")[0].split(":")[0].split(">")[0].strip()
            assert sum(1 for l in body.splitlines() if l.split("=")[0].split(":")[0].split(">")[0].strip() == key) == 1, \
                (emu, choice, text)
            if section:
                assert "[Other]\nx = 1" in text, (emu, text)
    # PPSSPP's portrait layout gets the same (the last choice applied above was bilinear)
    assert "[DisplayLayout.Portrait]\nBufferFiltering = 1" in open(f"{root}/{S}/ppsspp/PSP/SYSTEM/ppsspp.ini").read()

# Every emulator the script knows: its start script calls it, and the option is on its options page
script = open(SCRIPT).read()
body = re.search(r"^apply\(\) \{.*?^\}", script, re.M | re.S).group(0)
known = set()
for pattern in re.findall(r"^    ([a-z0-9|-]+)\)", body, re.M):
    known.update(pattern.split("|"))
STARTS = {"eden": ["eden-sa/scripts/start_eden.sh"], "eden-duo": ["eden-duo-sa/scripts/start_eden-duo.sh"],
          "armsx2": ["armsx2-sa/scripts/start_armsx2.sh"], "aethersx2": ["aethersx2-sa/scripts/start_aethersx2.sh"],
          "flycast": ["flycast-sa/scripts/start_flycast.sh"],
          "dolphin": ["dolphin-sa/scripts/start_dolphin_gc.sh", "dolphin-sa/scripts/start_dolphin_wii.sh"],
          "azahar": ["azahar-sa/scripts/start_azahar.sh"], "rpcs3": ["rpcs3-sa/scripts/start_rpcs3.sh"],
          "xemu": ["xemu-sa/scripts/start_xemu.sh"], "ppsspp": ["ppsspp-sa/scripts/start_ppsspp.sh"],
          "nanoboyadvance": ["nanoboyadvance-sa/scripts/start_nanoboyadvance.sh"],
          "melonds": ["melonds-sa/scripts/start_melonds.sh"], "vita3k": ["vita3k-sa/scripts/start_vita3k.sh"],
          "hatarisa": ["hatarisa/scripts/start_hatarisa.sh"]}
# Emulators that take it another way: (emulator, file, what the file has to do with it)
OTHER = {"cemu": ("standalone/cemu-sa/scripts/start_cemu.sh", r'asgard-screen-filter\.sh apply cemu wiiu "\$\{FILE\}"'),
         "scummvm-sa": ("../asgardos/sources/scripts/runemu.sh",
                        r'"\$\{EMULATOR\}" = scummvm-sa \] && \S*asgard-screen-filter\.sh apply scummvm-sa'),
         "retroarch": ("../asgardos/sources/scripts/setsettings.sh",
                       r'asgard-screen-filter\.sh get "\$\{PLATFORM\}" "\$\{ROM\}"\)" = nearest \] && smooth=false'),
         "dsperate": ("standalone/dsperate-sa/scripts/start_dsperate.sh",
                      r'asgard-screen-filter\.sh get "\$\{PLATFORM\}" "\$\{GAME\}"\)" = nearest \] && SMOOTH=0'),
         "mupen64plus": ("standalone/mupen64plus-sa/mupen64plus-sa-core/scripts/start_mupen64plus.sh",
                         r'asgard-screen-filter\.sh get "\$\{PLATFORM\}" "\$\{GAME\}"\)" = nearest \] && HYBRID=False'),
         "hypseus-singe": ("standalone/hypseus-singe/scripts/start_hypseus.sh",
                           r'asgard-screen-filter\.sh get "\$\{2\}" "\$\{1##\*/\}"\)" = nearest \] \|\| params="\$\{params\} -linear_scale"')}
for emu, (rel, pattern) in OTHER.items():
    assert re.search(pattern, open(os.path.join(HERE, "..", "..", "emulators", rel)).read()), (emu, rel)
mupen = open(os.path.join(HERE, "..", "..", "emulators", OTHER["mupen64plus"][0])).read()
assert "EnableHybridFilter]=False" not in mupen and mupen.count("EnableHybridFilter]=${HYBRID}") == 2
assert known == set(STARTS) | {"cemu", "scummvm-sa"}, known
for emu, starts in STARTS.items():
    for start in starts:
        text = open(os.path.join(HERE, "..", "..", "emulators", "standalone", start)).read()
        assert re.search(rf'asgard-screen-filter\.sh apply {emu} "\$\{{?(PLATFORM|2)\}}?" "\$\{{(GAME|ROMNAME|1##\*/)\}}"', text), start
ts = open(os.path.join(HERE, "thor_settings.py")).read()
listed = set(re.findall(r'"([a-z0-9-]+)": \[(?:NEAREST|BILINEAR)', ts))
assert listed == known | set(OTHER), (listed, known | set(OTHER))
print("ok")
