# spec: TOOL-1
# requires: file:build/AsgardOS-SM8550.aarch64/toolchain/usr/local/qt6/lib/libQt6Quick.so cmd:cmake
"""Run: python -I test_tools.py  (no Thor): the Tools. Asgard Files' copy, move, rename and delete, run for real across a fake
root's SD card, ROMs and internal storage. Asgard Music's playlists with a fake mpv. Home listing the Tools and starting them.
The start scripts' screens and keyboards, read as source. What this can't see, the windows on the right panels, playback with
the screens off, and Firefox, Terminal and Moonlight themselves, is for the device and human checks."""
import os
import shutil
import stat
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PACKAGES = os.path.join(HERE, "../..")
sys.path.insert(0, os.path.join(HERE, "../../../tools/test"))
from home_harness import Root  # noqa: E402

SD, ROMS, THOR = "storage/games-external", "storage/roms", "storage"
WINDOWS = ("Asgard Files", "Asgard Files (Bottom)")


def files(root, keys):
    return root.run(keys, args=["--files"], ms=800)


def wait(check):
    for _ in range(40):
        if check():
            return True
        time.sleep(0.05)
    return False


# ---- Asgard Files. It opens on the SD card; RB: next place. The actions: Y, then copy 0, move 1, paste 2, rename 3, delete 5.
PASTE_AFTER_COPY = "y down a"              # the cursor is still on Copy
PASTE_AFTER_MOVE = "y down left a"         # on Move
with Root() as r:
    r.write(f"{SD}/a.rom", "payload")
    os.makedirs(f"{r.path}/{ROMS}")
    res = files(r, "")
    assert all(res.window(w) for w in WINDOWS), res.log[-300:]
    assert "a.rom" in res.window(WINDOWS[0])

    files(r, f"y a rb {PASTE_AFTER_COPY}")                                  # SD card to ROMs: copied, the original stays
    assert wait(lambda: r.exists(f"{ROMS}/a.rom")) and r.read(f"{ROMS}/a.rom") == "payload"
    assert r.exists(f"{SD}/a.rom")

    files(r, f"y right a rb rb {PASTE_AFTER_MOVE}")                         # SD card to internal storage: moved
    assert wait(lambda: r.exists(f"{THOR}/a.rom")) and r.read(f"{THOR}/a.rom") == "payload"
    assert wait(lambda: not r.exists(f"{SD}/a.rom"))

    r.write(f"{SD}/b.rom", "other")
    typed = files(r, "y down right a")                                      # rename: the on-screen keyboard, with its name
    assert any("Rename b.rom" in t for t in typed.texts)
    files(r, "y down right a a start")                                      # A types the first key
    assert r.read(f"{SD}/b.romq") == "other" and not r.exists(f"{SD}/b.rom")

    delete = "y down down right a"
    asked = files(r, f"{delete}")
    assert any("Delete b.romq" in t for t in asked.texts) and r.exists(f"{SD}/b.romq")
    files(r, f"{delete} b")
    assert r.exists(f"{SD}/b.romq")
    files(r, f"{delete} a")
    assert wait(lambda: not r.exists(f"{SD}/b.romq"))

# ---- Asgard Music: the playlists folder, picked with the pad; mpv is faked and never plays
bin_dir = tempfile.mkdtemp()
open(f"{bin_dir}/mpv", "w").write("#!/bin/sh\nexec sleep 30\n")
os.chmod(f"{bin_dir}/mpv", os.stat(f"{bin_dir}/mpv").st_mode | stat.S_IEXEC)
with Root() as r:
    r.write("storage/.config/gmu/playlists/Road Trip.m3u", "song.mp3\n")
    res = r.run("", args=["--music"], env={"PATH": f"{bin_dir}:{os.environ['PATH']}"}, ms=500)
    assert res.window("Asgard Music") and res.window("Asgard Music (Bottom)"), res.log[-300:]
    assert res.shows("Road Trip")
shutil.rmtree(bin_dir)

# ---- Home: the Tools system, from ROCKNIX's music system, with Asgard's own art and names
with Root() as r:
    r.write("usr/config/emulationstation/es_systems.cfg",
            "<systemList><system><name>music</name><fullname>Music Player</fullname><path>/storage/.config/gmu/playlists</path>"
            '<extension>.sh .m3u</extension><emulators><emulator name="asgard-music"><cores><core default="true">x</core></cores>'
            "</emulator></emulators></system></systemList>")
    r.write("usr/share/asgard-home/media/music/gamelist.xml", open(os.path.join(PACKAGES, "asgard-home/src/media/music/gamelist.xml")).read())
    tools = ("Firefox", "Files", "Moonlight", "Terminal", "Start Music Player")
    for tool in tools:
        r.write(f"storage/.config/gmu/playlists/{tool}.sh", "#!/bin/sh\n")
    assert r.run("", ms=300).shows("Tools")
    opened = r.run("a", ms=300).window("Asgard Home")
    for tool in tools:
        assert tool in opened, tool
    assert "launch /storage/.config/gmu/playlists/Files.sh (music)" in r.run("a a", ms=300).log     # alphabetical: Files first

# ---- The start scripts: each entry is made at boot, its windows go where they should
tuning = open(os.path.join(HERE, "../autostart/090-asgard-tuning")).read()
for link in ("/usr/bin/start_firefox.sh /storage/.config/gmu/playlists/Firefox.sh",
             "/usr/share/asgard/start_terminal.sh /storage/.config/gmu/playlists/Terminal.sh",
             "/usr/bin/start_moonlight-qt.sh /storage/.config/gmu/playlists/Moonlight.sh",
             "/usr/bin/start_asgard-files.sh /storage/.config/gmu/playlists/Files.sh"):
    assert f"ln -sfn {link}" in tuning, link
TOP = "move container to output DSI-2, fullscreen enable"
BOTTOM = "move container to output DSI-1, fullscreen enable"
KEYBOARD = f"'[title=\"^Asgard Keyboard$\"] {BOTTOM}'"
SCRIPTS = {"apps/firefox/sources/start_firefox.sh": (TOP, KEYBOARD, "--osk firefox"),
           "asgard/sources/start_terminal.sh": (TOP, KEYBOARD, "--osk qterminal"),
           "apps/moonlight-qt/sources/start_moonlight-qt.sh": (TOP,),
           "asgard-home/src/start_asgard-files.sh": (TOP, BOTTOM),
           "asgard-home/src/start_asgard-music.sh": (TOP, BOTTOM)}
for script, wanted in SCRIPTS.items():
    text = open(os.path.join(PACKAGES, script)).read()
    for part in wanted:
        assert part in text, (script, part)
print("ok")
