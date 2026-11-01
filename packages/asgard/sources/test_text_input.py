# spec: TXT-1 TXT-2 TXT-3
# requires: file:build/AsgardOS-SM8550.aarch64/toolchain/usr/local/qt6/lib/libQt6Quick.so cmd:cmake
"""Run: python -I test_text_input.py  (no Thor): a game's text prompt: asgard-home --text-input offscreen, and thor_text_input.py
around a fake keyboard and a fake swaymsg. TXT-1: the keyboard window, sway's rules for it, and Eden Duo's patch calling the
helper; a real prompt in a game is a human check. TXT-3: what's asked of sway and that nothing outlives a killed game; that
the panel really lights is a human check."""
import json
import os
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "../../../tools/test"))
import home_harness as hh  # noqa: E402
from home_harness import Root  # noqa: E402

WINDOW = "Asgard Text Input (Bottom)"
HELPER = os.path.join(HERE, "thor_text_input.py")


def alive(pid):
    try:
        with open(f"/proc/{pid}/stat") as f:
            return f.read().rsplit(")", 1)[1].split()[0] != "Z"
    except OSError:
        return False


def wait_gone(pid, what):
    for _ in range(100):
        if not alive(pid):
            return
        time.sleep(0.05)
    os.kill(pid, signal.SIGKILL)
    raise AssertionError(what)


def done_on_start(root):
    """The keyboard pressing Done by itself: the pad can't, without ASGARD_SHOT, which keeps stdout quiet."""
    out = f"{root.path}/.qml"
    shutil.rmtree(out, ignore_errors=True)
    shutil.copytree(f"{hh.SRC}/qml", out)
    text = open(f"{out}/TextInput.qml").read()
    old = "    Keyboard {\n        id: keyboard"
    assert old in text
    open(f"{out}/TextInput.qml", "w").write(
        text.replace(old, '    Timer { interval: 100; running: true; onTriggered: keyboard.press("ok") }\n' + old))
    return {"ASGARD_HOME_QML": out, "ASGARD_SHOT": ""}


# ---- The keyboard itself: asgard-home --text-input
with Root() as r:
    shown = r.run("a", args=["--text-input", "--title=Your name"], ms=300)
    assert "Your name" in shown.window(WINDOW) and any(t.startswith("q") for t in shown.window(WINDOW))   # A typed the first key
    answer = r.run("", args=["--text-input", "--initial=héllo wörld"], env=done_on_start(r), timeout=20)
    assert answer.rc == 0 and answer.log.startswith("héllo wörld"), answer.log[:200]      # TXT-2: on stdout, exit 0
    assert r.run("b", args=["--text-input"], ms=300).rc == 1                               # TXT-2: backed out
    assert r.run("", args=["--text-input"], env={"ASGARD_HOME_QML": r.path}, ms=300).rc == 2   # TXT-2: couldn't start

    # TXT-3: killed with its parent, even with no helper around it
    parent = subprocess.Popen([sys.executable, "-c", """
import os, subprocess, sys, time
env = {**os.environ, "ASGARD_SHOT": "", "ASGARD_ROOT": sys.argv[2], "ASGARD_HOME_QML": sys.argv[3], "QT_QPA_PLATFORM": "offscreen",
       "LD_LIBRARY_PATH": sys.argv[4] + "/lib", "QT_PLUGIN_PATH": sys.argv[4] + "/plugins", "QML_IMPORT_PATH": sys.argv[4] + "/qml",
       "QML2_IMPORT_PATH": sys.argv[4] + "/qml"}
child = subprocess.Popen([sys.argv[1], "--text-input"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
print(child.pid, flush=True)
time.sleep(60)
""", hh.binary(), r.path, f"{hh.SRC}/qml", hh.QT], stdout=subprocess.PIPE, text=True)
    keyboard = int(parent.stdout.readline())
    time.sleep(1)
    assert alive(keyboard), "the keyboard didn't stay up"
    parent.kill()
    parent.wait()
    wait_gone(keyboard, "the keyboard outlived its parent")

# ---- The helper around it, with fake tools
tmp = tempfile.mkdtemp()
calls = f"{tmp}/calls"


def tool(name, body):
    path = f"{tmp}/{name}"
    open(path, "w").write("#!/bin/sh\n" + body)
    os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC)


TREE = {"type": "root", "nodes": [{"type": "output", "name": "DSI-1", "nodes": [{"id": 42, "pid": 7, "fullscreen_mode": 1}]}]}
tool("systemctl", "")
tool("swaymsg", f'''echo "swaymsg $*" >> {calls}
case "$*" in
  "-t get_tree -r") cat {tmp}/tree ;;
  "-t get_outputs -r") cat {tmp}/outputs ;;
esac
''')
tool("asgard-text-input", f'''echo "keyboard $*" >> {calls}
[ -n "$FAKE_TEXT" ] && printf %s "$FAKE_TEXT"
[ -n "$FAKE_PID" ] && {{ echo $$ > "$FAKE_PID"; exec sleep 60; }}
exit ${{FAKE_EXIT:-0}}
''')


def helper(powered, fullscreen, env=None, path=None):
    open(f"{tmp}/tree", "w").write(json.dumps(TREE if fullscreen else {"type": "root"}))
    open(f"{tmp}/outputs", "w").write(json.dumps([{"name": "DSI-1", "power": powered}]))
    if os.path.exists(calls):
        os.remove(calls)
    return subprocess.run([sys.executable, HELPER, "--title=Name"], capture_output=True, text=True, timeout=20,
                          env={**os.environ, "PATH": path or f"{tmp}:{os.environ['PATH']}", **(env or {})})


def log():
    return open(calls).read().splitlines()


# TXT-2: the answer passes through, and any other end of the keyboard is a failure
done = helper(True, False, {"FAKE_TEXT": "Link"})
assert done.returncode == 0 and done.stdout == "Link"
assert any(line.startswith("keyboard --text-input") and "--title=Name" in line for line in log())
cancelled = helper(True, False, {"FAKE_EXIT": "1"})
assert cancelled.returncode == 1 and cancelled.stdout == ""
assert helper(True, False, {"FAKE_EXIT": "9"}).returncode == 2
no_keyboard = f"{tmp}/no-keyboard"
os.mkdir(no_keyboard)
shutil.copy(f"{tmp}/swaymsg", no_keyboard)
shutil.copy(f"{tmp}/systemctl", no_keyboard)
assert helper(True, False, path=f"{no_keyboard}:/usr/bin:/bin").returncode == 2            # nothing to run

# TXT-3: the screen goes back to how it was
helper(True, False)
assert "swaymsg output DSI-1 power off" not in log() and not [c for c in log() if "fullscreen enable" in c]
helper(False, True)
order = log()
keyboard_at = next(i for i, c in enumerate(order) if c.startswith("keyboard"))
assert order.index("swaymsg [con_id=42] fullscreen enable") > keyboard_at                  # the window it took it from
assert order.index("swaymsg output DSI-1 power off") > keyboard_at                         # it was off

# TXT-3: the game killed with the keyboard open: both go, and the screen still goes back
pid_file = f"{tmp}/pid"
game = subprocess.Popen([sys.executable, "-c", """
import subprocess, sys, time
print(subprocess.Popen([sys.executable, sys.argv[1]]).pid, flush=True)
time.sleep(60)
""", HELPER], stdout=subprocess.PIPE, text=True, env={**os.environ, "PATH": f"{tmp}:{os.environ['PATH']}", "FAKE_PID": pid_file})
wrapper = int(game.stdout.readline())
for _ in range(100):
    if os.path.exists(pid_file) and open(pid_file).read().strip():
        break
    time.sleep(0.05)
keyboard = int(open(pid_file).read())
assert alive(keyboard)
game.send_signal(signal.SIGKILL)
game.wait()
wait_gone(wrapper, "the helper outlived the game")
wait_gone(keyboard, "the keyboard outlived the game")
assert "swaymsg output DSI-1 power off" in log() and "swaymsg [con_id=42] fullscreen enable" in log()
shutil.rmtree(tmp)

# ---- TXT-1 and TXT-3 in the tree: the sway rules that place it, and who calls it
rules = open(os.path.join(HERE, "thor-sway-rotate.sh")).read()
assert 'assign [title="^Asgard Text Input"] output DSI-1' in rules
assert 'for_window [title="^Asgard Text Input"] fullscreen enable' in rules
init = open(os.path.join(HERE, "../../wayland/compositor/sway/autostart/111-sway-init")).read()
assert any("Bottom" in line and " power on" in line for line in init.splitlines())   # ROCKNIX's rule for the title's "Bottom"
assert f'title: "{WINDOW}"' in open(f"{hh.SRC}/qml/TextInput.qml").read()
patch = open(os.path.join(HERE, "../../emulators/standalone/eden-duo-sa/patches/0004-eden-cli-software-keyboard.patch")).read()
assert '+constexpr const char* HELPER = "/usr/share/asgard/thor_text_input.py";' in patch
print("ok")
