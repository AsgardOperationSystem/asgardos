"""Playtime log. run-game.sh writes it around every game launch (both frontends launch through it);
Thor Home reads totals, Thor Panel reads what's playing (screenshot names).

Usage from run-game.sh: python3 playlog.py start <rom> <system>  /  python3 playlog.py stop
"""
import json
import os
import sys
import time

LOG = "/storage/.config/thor/playtime.jsonl"  # one {"rom", "sys", "start", "secs"} per session
PLAYING = "/run/thor-playing.json"


def start(rom, system):
    with open(PLAYING, "w") as f:
        json.dump({"rom": rom, "sys": system, "start": int(time.time()), "mono": time.monotonic()}, f)


def stop():
    p = playing()
    if not p:
        return
    os.remove(PLAYING)
    secs = int(time.monotonic() - p.pop("mono"))  # CLOCK_MONOTONIC stops in suspend, so sleep isn't counted
    if secs >= 5:  # ponytail: a launch that died at once isn't a session
        with open(LOG, "a") as f:
            f.write(json.dumps({**p, "secs": secs}) + "\n")


def playing():
    try:
        with open(PLAYING) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def totals(log=None):
    """rom path -> {"secs", "sessions", "last"} (last = end of the latest session, epoch)."""
    out = {}
    try:
        with open(log or LOG) as f:
            lines = f.read().splitlines()
    except OSError:
        return out
    for ln in lines:
        try:
            e = json.loads(ln)
            t = out.setdefault(e["rom"], {"secs": 0, "sessions": 0, "last": 0})
            t["secs"] += e["secs"]
            t["sessions"] += 1
            t["last"] = max(t["last"], e["start"] + e["secs"])
        except (ValueError, KeyError, TypeError):
            continue  # a torn line (power loss mid-write) costs one session, not the whole log
    return out


if __name__ == "__main__":
    start(sys.argv[2], sys.argv[3]) if sys.argv[1] == "start" else stop()
