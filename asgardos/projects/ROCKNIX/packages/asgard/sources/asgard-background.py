#!/usr/bin/env python3
"""asgard-background.py hide|show NAME...: Asgard Home's "Back to Home" (hide) and "Return to <game>" (show).

hide: the game's windows (those of NAME's processes and their children, plus ROCKNIX's lowerdeck) go to sway's
scratchpad, each one's output and fullscreen/floating state noted in /run/asgard-bg.json (its presence also tells
thor_ayn_button.py a game is in the background), then NAME's processes are frozen (SIGSTOP).
show: SIGCONT, and the windows go back where they were. NAME comes from ROCKNIX's kill data (runningGame()).
"""
import json
import os
import subprocess
import sys

STATE = "/run/asgard-bg.json"
ENV = dict(os.environ, SWAYSOCK=os.environ.get("SWAYSOCK", "/run/0-runtime-dir/sway-ipc.0.sock"))


def sway(*args):
    return subprocess.run(["swaymsg", *args], capture_output=True, text=True, env=ENV).stdout


def windows(node, output=None):
    """(output, window) for every window in a sway tree."""
    if node.get("type") == "output":
        output = node["name"]
    if node.get("type") in ("con", "floating_con") and node.get("pid"):
        yield output, node
    for child in node.get("nodes", []) + node.get("floating_nodes", []):
        yield from windows(child, output)


def family(names):
    """PIDs of the named processes and all their descendants (Steam's game windows belong to gamescope's children)."""
    out = set(subprocess.run(["pidof", *names], capture_output=True, text=True).stdout.split())
    parent = {}
    for p in os.listdir("/proc"):
        if p.isdigit():
            try:
                parent[p] = open(f"/proc/{p}/stat").read().rsplit(")", 1)[1].split()[1]
            except OSError:
                pass
    grew = True
    while grew:
        new = {p for p, pp in parent.items() if pp in out} - out
        out |= new
        grew = bool(new)
    return out


def pick(tree, pids):
    return [{"id": w["id"], "output": o, "fullscreen": w.get("fullscreen_mode", 0),
             "floating": w["type"] == "floating_con"}
            for o, w in windows(tree) if str(w["pid"]) in pids or w.get("app_id") == "lowerdeck"]


def hide(names):
    state = pick(json.loads(sway("-t", "get_tree")), family(names))
    json.dump(state, open(STATE, "w"))
    for w in state:
        # Fullscreen out first, on its own: moved to the scratchpad straight from fullscreen, LEGO Racers' (UE) surface
        # stayed drawn at 0,0 over Home, hidden container or not (sway 1.11, 2026-10-16).
        if w["fullscreen"]:
            sway(f"[con_id={w['id']}] fullscreen disable")
        sway(f"[con_id={w['id']}] move scratchpad")
    subprocess.run(["killall", "-STOP", *names], capture_output=True)


def show(names):
    subprocess.run(["killall", "-CONT", *names], capture_output=True)
    try:
        state = json.load(open(STATE))
        os.remove(STATE)
    except (OSError, ValueError):
        return
    for w in state:
        cmd = f"[con_id={w['id']}] scratchpad show, move window to output {w['output']}"
        if not w["floating"]:
            cmd += ", floating disable"
        if w["fullscreen"]:
            cmd += ", fullscreen enable"
        sway(cmd)
    top = next((w for w in state if w["output"] == "DSI-2"), state[0] if state else None)
    if top:
        sway(f"[con_id={top['id']}] focus")


if __name__ == "__main__":
    t = {"type": "root", "nodes": [{"type": "output", "name": "DSI-2", "nodes": [{"type": "workspace", "nodes": [
        {"type": "con", "id": 5, "pid": 100, "fullscreen_mode": 1},
        {"type": "con", "id": 6, "pid": 200, "app_id": "asgard-home"}]}]},
        {"type": "output", "name": "DSI-1", "nodes": [{"type": "workspace", "nodes": [], "floating_nodes": [
            {"type": "floating_con", "id": 7, "pid": 300, "app_id": "lowerdeck"}]}]}]}
    assert pick(t, {"100"}) == [{"id": 5, "output": "DSI-2", "fullscreen": 1, "floating": False},
                                {"id": 7, "output": "DSI-1", "fullscreen": 0, "floating": True}]
    if len(sys.argv) > 2 and sys.argv[1] in ("hide", "show"):
        (hide if sys.argv[1] == "hide" else show)(sys.argv[2:])
