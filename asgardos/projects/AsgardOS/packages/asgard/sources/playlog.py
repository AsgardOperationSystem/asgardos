"""Playtime log. run-game.sh writes it around every game launch (both frontends launch through it);
Thor Home reads totals, Thor Panel reads what's playing (screenshot names).

Usage from run-game.sh: python3 playlog.py start <rom> <system> [emulator] [core]  /  python3 playlog.py stop
"""
import json
import os
import sys
import time

LOG = "/storage/.config/thor/playtime.jsonl"  # one {"rom", "sys", "start", "secs"} per session
PLAYING = "/run/thor-playing.json"
# The same for shell readers (battery-log.sh, the sleep hooks), one line, '|'-separated (not tabs: read collapses
# empty whitespace-separated fields), the game name last so a '|' in it is harmless:
# sys, emulator, core, pid of the launching shell (the game is its descendant), game name.
PLAYING_TXT = "/run/thor-playing.txt"


def game_name(rom):
    """A PC .desktop entry's Name=, else the ROM's file name without its extension."""
    if rom.endswith(".desktop"):
        try:
            with open(rom) as f:
                for ln in f:
                    if ln.startswith("Name="):
                        return ln[5:].strip()
        except OSError:
            pass
    return os.path.splitext(os.path.basename(rom))[0]


def start(rom, system, emu="", core=""):
    with open(PLAYING, "w") as f:
        json.dump({"rom": rom, "sys": system, "start": int(time.time()), "mono": time.monotonic()}, f)
    clean = lambda v: " ".join(v.split())   # no newlines in a field
    with open(PLAYING_TXT, "w") as f:
        f.write("|".join([clean(system), clean(emu), clean(core), str(os.getppid()), clean(game_name(rom))]) + "\n")


def stop():
    p = playing()
    try:
        os.remove(PLAYING_TXT)
    except OSError:
        pass
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
    start(*sys.argv[2:6]) if sys.argv[1] == "start" else stop()
