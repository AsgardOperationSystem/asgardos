#!/usr/bin/env python3
# spec: GAME-4
# playlog.py, the writer of /run/thor-playing.txt, with its paths in a temp dir: it names the game, emulator and core while a game
# runs and is gone after. That Home calls it around every launch is test_fake_emulator.py.
import importlib.util
import os
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("playlog", f"{HERE}/playlog.py")
playlog = importlib.util.module_from_spec(spec)
spec.loader.exec_module(playlog)

with tempfile.TemporaryDirectory() as d:
    playlog.LOG, playlog.PLAYING, playlog.PLAYING_TXT = f"{d}/log", f"{d}/playing.json", f"{d}/playing.txt"
    playlog.start("/roms/3ds/Pokemon X.3ds", "3ds", "azahar", "azahar-sa")
    fields = open(playlog.PLAYING_TXT).read().rstrip("\n").split("|")
    assert fields[:3] == ["3ds", "azahar", "azahar-sa"] and fields[4] == "Pokemon X", fields
    assert fields[3] == str(os.getppid()), fields          # the launching shell, which the game descends from
    assert playlog.playing()["rom"] == "/roms/3ds/Pokemon X.3ds"
    playlog.stop()
    assert not os.path.exists(playlog.PLAYING_TXT) and not os.path.exists(playlog.PLAYING)

    # A newline can't break the one line, and a '|' in the game's name stays in the last field.
    playlog.start("/roms/gba/A|B.gba", "gba", "retro\narch", "mgba")
    line = open(playlog.PLAYING_TXT).read()
    assert line.count("\n") == 1 and line.split("|")[1] == "retro arch" and line.rstrip("\n").split("|", 4)[4] == "A|B", line
    playlog.stop()

    # A PC app's name is its Name=; a stop with nothing running leaves nothing behind and doesn't fail.
    desktop = f"{d}/App.desktop"
    open(desktop, "w").write("[Desktop Entry]\nName=My Port\nExec=x\n")
    playlog.start(desktop, "pc")
    assert open(playlog.PLAYING_TXT).read().rstrip("\n").split("|")[4] == "My Port"
    playlog.stop()
    playlog.stop()
    assert not os.path.exists(playlog.PLAYING_TXT)
print("ok")
