# spec: SET-3
# requires: cmd:node
# gap: Settings > About also offers a .img.gz in /storage/.update as an update; SET-3 says only a .tar
"""Run: python -I test_update_offer.py  (no Thor, no Qt): SET-3's "only when a .tar is in /storage/.update": the listing
Settings runs to decide (Settings.qml's refresh), on a temp folder. The offer itself is in test_home_settings.py."""
import os
import re
import subprocess
import tempfile

QML = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../asgard-home/src/qml/Settings.qml")
command = re.search(r'sh\("update", "(.*)"\)', open(QML).read()).group(1)


def offered(*names):
    with tempfile.TemporaryDirectory() as d:
        for name in names:
            open(os.path.join(d, name), "w").close()
        return subprocess.run(["sh", "-c", command.replace("/storage/.update", d)], capture_output=True, text=True).stdout.strip()


assert offered() == ""
assert offered("notes.txt", "x.tar.part") == ""
assert offered("AsgardOS.tar").endswith("/AsgardOS.tar")
assert offered("AsgardOS.img.gz") == ""
print("ok")
