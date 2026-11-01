# spec: TRO-1
# requires: file:build/AsgardOS-SM8550.aarch64/toolchain/usr/local/qt6/lib/libQt6Quick.so cmd:cmake
"""Run: python -I test_trophies.py  (no Thor, no network): the Trophies tab, from RA answers already in Home's cache. A NES ROM's
RetroAchievements hash skips its iNES header, so only rcheevos' hash of it, not a plain MD5, finds the game. One console's
hashing stands for rcheevos' others; signing in against the real service and a game's own achievement list are human checks."""
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../../tools/test"))
from home_harness import CFG, Root  # noqa: E402

CACHE = "storage/.config/asgard/ra"
RC_CONSOLE_NINTENDO = 7
HEADER, BODY = b"NES\x1a" + bytes(12), b"\x01\x02\x03" * 5000


def game(ident, title, digest, total):
    # The icon's URL is the media host + this, so user info makes it refused at this machine, not fetched from outside.
    return {"ID": ident, "Title": title, "ImageIcon": "@127.0.0.1:9/i.png", "NumAchievements": total, "Points": 50, "Hashes": [digest]}


with Root() as r:
    r.write("usr/config/emulationstation/es_systems.cfg",
            "<systemList><system><name>nes</name><fullname>NES</fullname><path>/storage/roms/nes</path><extension>.nes</extension>"
            '<emulators><emulator name="retroarch"><cores><core default="true">nestopia</core></cores></emulator></emulators>'
            "</system></systemList>")
    os.makedirs(f"{r.path}/storage/roms/nes")
    for name in ("Hashed", "PlainMd5", "Unknown"):
        with open(f"{r.path}/storage/roms/nes/{name}.nes", "wb") as f:
            f.write(HEADER + BODY + name.encode())
    ra_hash = lambda name: hashlib.md5(BODY + name.encode()).hexdigest()              # noqa: E731
    plain = hashlib.md5(HEADER + BODY + b"PlainMd5").hexdigest()
    r.write(f"{CACHE}/console-{RC_CONSOLE_NINTENDO}.json",
            json.dumps([game(1, "Hashed", ra_hash("Hashed"), 10), game(2, "PlainMd5", plain, 20)]))
    r.write(f"{CACHE}/progress.json", json.dumps({"Results": [{"GameID": 1, "NumAwarded": 3, "NumAwardedHardcore": 0}]}))
    r.write(CFG, "global.retroachievements.username=u\nglobal.retroachievements.webapikey=k\n")
    tab = r.run("rb rb", ms=1000)
    assert "1 of 3 hashed games have RetroAchievements sets" in tab.log, tab.log[-500:]
    assert "3/10" in tab.texts, tab.texts                     # the matched game's progress
    assert "0/20" not in tab.texts                            # a whole-file MD5 isn't RA's hash
print("ok")
