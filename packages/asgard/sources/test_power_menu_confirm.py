# spec: SET-3
# requires: file:build/AsgardOS-SM8550.aarch64/toolchain/usr/local/qt6/lib/libQt6Quick.so cmd:cmake
# gap: the power button's menu (PowerMenu.qml) restarts and powers off at once, without the confirmation Settings asks for
"""Run: python -I test_power_menu_confirm.py  (no Thor): SET-3's confirmation on the other way to restart or power off, the
on-screen power button. A QML copy opens the menu, as the tap would. On a host the command is only logged."""
import os
import shutil
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../../tools/test"))
import home_harness as hh  # noqa: E402
from home_harness import Root  # noqa: E402

with Root() as r:
    r.library()
    out = f"{r.path}/.qml"
    shutil.copytree(f"{hh.SRC}/qml", out)
    text = open(f"{out}/Main.qml").read()
    old = 'Component.onCompleted: if (debugInput) console.log("input: debug logging on (bottom window)")'
    assert old in text
    open(f"{out}/Main.qml", "w").write(text.replace(old, "Component.onCompleted: powerMenuPanel.show()"))
    env = {"ASGARD_HOME_QML": out}
    for keys, command in (("down a", "systemctl reboot"), ("down down a", "systemctl poweroff")):
        assert command not in r.run(keys, env=env, ms=300).log, command
print("ok")
