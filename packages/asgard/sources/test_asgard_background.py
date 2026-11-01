#!/usr/bin/env python3
# spec: GAME-6
# requires: cmd:killall cmd:pidof
# asgard-background.py against a real process and a fake swaymsg: hide moves the game's windows to the scratchpad and stops it
# (SIGSTOP), show continues it (SIGCONT) and puts each window back. That audio and input come back is a human check.
import importlib.util
import json
import os
import shutil
import stat
import subprocess
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))


def state_of(pid):
    with open(f"/proc/{pid}/stat") as f:
        return f.read().rsplit(")", 1)[1].split()[0]


def wait_state(pid, want):
    for _ in range(50):
        if state_of(pid) == want:
            return True
        time.sleep(0.02)
    return False


with tempfile.TemporaryDirectory() as d:
    name = f"fakegame{os.getpid()}"[:15]
    shutil.copy(shutil.which("sleep"), f"{d}/{name}")
    game = subprocess.Popen([f"{d}/{name}", "60"])
    bystander = subprocess.Popen([shutil.which("sleep"), "60"])
    try:
        tree = {"type": "root", "nodes": [
            {"type": "output", "name": "DSI-2", "nodes": [{"type": "workspace", "nodes": [
                {"type": "con", "id": 1, "pid": game.pid, "fullscreen_mode": 1},
                {"type": "con", "id": 2, "pid": bystander.pid, "app_id": "asgard-home", "fullscreen_mode": 1}]}]},
            {"type": "output", "name": "DSI-1", "nodes": [{"type": "workspace", "nodes": [
                {"type": "con", "id": 3, "pid": game.pid, "fullscreen_mode": 0}], "floating_nodes": [
                {"type": "floating_con", "id": 4, "pid": 4242424, "app_id": "lowerdeck", "fullscreen_mode": 1}]}]}]}
        with open(f"{d}/tree", "w") as f:
            json.dump(tree, f)
        os.makedirs(f"{d}/bin")
        with open(f"{d}/bin/swaymsg", "w") as f:
            f.write(f'#!/bin/sh\ncase "$1" in -t) cat "{d}/tree" ;; *) echo "$*" >>"{d}/calls" ;; esac\n')
        os.chmod(f"{d}/bin/swaymsg", stat.S_IRWXU)
        os.environ["PATH"] = f"{d}/bin:" + os.environ["PATH"]

        spec = importlib.util.spec_from_file_location("bg", f"{HERE}/asgard-background.py")
        bg = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bg)
        bg.STATE = f"{d}/asgard-bg.json"

        bg.hide([name])
        assert wait_state(game.pid, "T"), state_of(game.pid)
        assert state_of(bystander.pid) != "T"
        calls = open(f"{d}/calls").read().splitlines()
        # Out of fullscreen first, on its own (asgard-background.py says why); only the game's windows and lowerdeck go.
        assert calls == ["[con_id=1] fullscreen disable", "[con_id=1] move scratchpad", "[con_id=3] move scratchpad",
                         "[con_id=4] fullscreen disable", "[con_id=4] move scratchpad"], calls
        assert os.path.exists(bg.STATE)

        os.remove(f"{d}/calls")
        bg.show([name])
        assert wait_state(game.pid, "S"), state_of(game.pid)
        assert not os.path.exists(bg.STATE)
        calls = open(f"{d}/calls").read().splitlines()
        assert calls[:3] == ["[con_id=1] scratchpad show, move window to output DSI-2, floating disable, fullscreen enable",
                             "[con_id=3] scratchpad show, move window to output DSI-1, floating disable",
                             "[con_id=4] scratchpad show, move window to output DSI-1, fullscreen enable"], calls
        assert calls[3:] == ["[con_id=1] focus"], calls     # focus goes back to the game on the top screen
    finally:
        game.kill()
        bystander.kill()
        game.wait()
        bystander.wait()
print("ok")
