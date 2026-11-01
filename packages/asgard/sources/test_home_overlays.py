# spec: MENU-1 SND-5
# requires: file:build/AsgardOS-SM8550.aarch64/toolchain/usr/local/qt6/lib/libQt6Quick.so cmd:cmake
"""Run: python -I test_home_overlays.py  (no Thor): where Home's two over-the-game surfaces show, offscreen. A game can't run on
a host, so a QML copy opens them. MENU-1: the menu is in the window on the physical bottom screen, swapped or not (the tap
itself is test_ayn_button.py). SND-5: asgard-osd reaches Home's overlay, drawn with Theme, as a layer above games; that it
really shows over a running game is a human check."""
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "../../../tools/test"))
import home_harness as hh  # noqa: E402
from home_harness import Root  # noqa: E402


def copy(root, name, old, new):
    out = f"{root.path}/.qml"
    shutil.rmtree(out, ignore_errors=True)
    shutil.copytree(f"{hh.SRC}/qml", out)
    text = open(f"{out}/{name}").read()
    assert old in text, old
    open(f"{out}/{name}", "w").write(text.replace(old, new))
    return {"ASGARD_HOME_QML": out}


# MENU-1: sway puts the title with "(Bottom)" on DSI-1; L+R makes the windows trade titles
with Root() as r:
    r.library()
    env = copy(r, "GameMenu.qml", "property bool open: backend.gameMenu", "property bool open: true")
    for swap in ("1", "0"):
        r.write(hh.CFG, f"asgard.swap_screens={swap}\n")
        res = r.run("", env=env, ms=300)
        assert "Paused" in res.window("Asgard Home (Bottom)"), swap
        assert "Paused" not in res.window("Asgard Home"), swap

# SND-5: the overlay, on the signal asgard-osd's command raises; values held to 0-100
with Root() as r:
    r.library()
    assert "60%" not in r.run("", ms=300).window("Asgard OSD")
    for what, value, shown in (("Volume", 60, "60%"), ("Brightness", 140, "100%")):
        env = copy(r, "Osd.qml", "    property bool shown: false",
                   f"    property bool shown: false\n    Component.onCompleted: backend.osd('{what}', {value})")
        assert shown in r.run("", env=env, ms=300).window("Asgard OSD"), what

qml = open(f"{hh.SRC}/qml/Osd.qml").read()
assert "color: Theme.pill; border.color: Theme.pillRim" in qml and "font.family: Theme.font" in qml        # Home's style
main = open(f"{hh.SRC}/main.cpp").read()
assert 'win->objectName() == "osd"' in main and "setLayer(LayerShellQt::Window::LayerOverlay)" in main     # above fullscreen games
backend = open(f"{hh.SRC}/backend.cpp").read()
assert re.search(r'cmd\.startsWith\("osd "\).*?emit osd\(p\[1\], p\[2\]\.toInt\(\)\)', backend, re.S)
sense = open(os.path.join(HERE, "../../sysutils/system-utils/sources/scripts/input_sense")).read()
assert "/usr/share/asgard/asgard-osd Volume" in sense and "/usr/share/asgard/asgard-osd Brightness" in sense

# asgard-osd itself, a temp copy on a temp FIFO: with Home up the message goes to it, not to mako
with tempfile.TemporaryDirectory() as d:
    fifo = f"{d}/cmd"
    os.mkfifo(fifo)
    text = open(os.path.join(HERE, "asgard-osd")).read()
    assert "FIFO=/run/asgard-home.cmd" in text
    open(f"{d}/osd", "w").write(text.replace("FIFO=/run/asgard-home.cmd", f"FIFO={fifo}"))
    for tool in ("pidof", "busctl"):
        open(f"{d}/{tool}", "w").write(f"#!/bin/sh\necho {tool} >> {d}/ran\nexit 0\n")
        os.chmod(f"{d}/{tool}", os.stat(f"{d}/{tool}").st_mode | stat.S_IEXEC)
    reader = os.open(fifo, os.O_RDONLY | os.O_NONBLOCK)
    subprocess.run(["bash", f"{d}/osd", "Volume", "60"], check=True, env={**os.environ, "PATH": f"{d}:{os.environ['PATH']}"}, timeout=10)
    assert os.read(reader, 100) == b"osd Volume 60\n"
    os.close(reader)
    assert "busctl" not in open(f"{d}/ran").read()
print("ok")
