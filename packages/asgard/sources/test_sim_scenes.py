# spec: DEV-16 DEV-18
# requires: file:build/AsgardOS-SM8550.aarch64/toolchain/usr/local/qt6/lib/libQt6Quick.so cmd:cmake
"""Run: python -I test_sim_scenes.py  (no Thor, no network): every scene of tools/sim/shots.py renders on a simulated
Thor and shows what it should, with Asgard Home in ASGARD_SIM. In it Home runs no command (each exec is answered from
the root's sim/exec.json), and shows the root's name, version and free space, never the desktop's (DEV-16). Where
lavapipe is installed it renders on Vulkan, the only renderer that draws Home's rounded art."""
import os
import socket
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "../../.."))

with tempfile.TemporaryDirectory() as tmp:
    env = {**os.environ, "ASGARD_SIM_LIBRARY": f"{tmp}/none.tsv", "ASGARD_SIM_ROOT": f"{tmp}/root",
           "ASGARD_SIM_SHOTS": f"{tmp}/shots"}
    made = subprocess.run([sys.executable, "-I", f"{REPO}/tools/sim/make-root.py", "--out", f"{tmp}/root"], env=env,
                          capture_output=True, text=True)
    assert made.returncode == 0, made.stderr
    os.environ.update(env)
    sys.path.insert(0, f"{REPO}/tools/sim")
    import shots  # noqa: E402  (reads ASGARD_SIM_ROOT and ASGARD_SIM_SHOTS at import)

    assert shots.main([]) == 0   # every scene shows its expected text
    for scene in shots.SCENES:
        assert any(f.startswith(scene + "-") and f.endswith(".png") for f in os.listdir(f"{tmp}/shots")), scene

    # Nothing runs and nothing of the desktop shows: Settings and About
    missing, shown = shots.shoot("about")
    assert "\nexec: " not in "\n" + shown.log and "sim exec: uname -r" in shown.log, shown.log
    host = socket.gethostname()
    assert not any(host in t for t in shown.texts), host
    assert shown.shows("●  Thor") and shown.shows("AYN Thor  ·  SM8550"), shown.texts

    # A game in play: the launcher Home started asked for the menu as RetroArch, whose pause stays off the network
    missing, shown = shots.shoot("ingame")
    assert not missing and "sim retroarch: PAUSE_TOGGLE" in shown.log, shown.log

    # Drawn on the GPU path (Vulkan on lavapipe) where there's one: the software renderer leaves every tile empty
    if os.path.exists(shots.LAVAPIPE):
        missing, shown = shots.shoot("home", extra={"QSG_INFO": "1"})
        assert "Creating QRhi with backend Vulkan" in shown.log, shown.log
print("ok")
