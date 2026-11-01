# spec: OLED-3
# requires: cmd:python3
"""Run: python -I test_idle_blank.py  (no Thor): thor-idle-blank.py's setting and loop, from a temp copy reading a temp
system.cfg, on a fake clock with input events and sway calls faked. That it runs and darkens real panels: device and human checks."""
import importlib.util
import json
import os
import struct
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
EV_KEY, EV_ABS = 1, 3
sys.dont_write_bytecode = True


def load(cfg):
    """A copy of the daemon whose system.cfg is `cfg` (None: no file), with no IDLE_SECONDS in the way."""
    os.environ.pop("IDLE_SECONDS", None)
    with tempfile.TemporaryDirectory() as d:
        conf = f"{d}/system.cfg"
        if cfg is not None:
            open(conf, "w").write(cfg)
        text = open(os.path.join(HERE, "thor-idle-blank.py")).read()
        assert "/storage/.config/system/configs/system.cfg" in text
        open(f"{d}/blank.py", "w").write(text.replace("/storage/.config/system/configs/system.cfg", conf))
        spec = importlib.util.spec_from_file_location("blank", f"{d}/blank.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    return mod


class Done(Exception):
    pass


def simulate(mod, events, until):
    """Runs main() on a fake clock, 5 s a turn (its select timeout). events: {time: (type, code, value)}. What it told sway."""
    now = [0.0]
    pending = dict(events)
    sent = []
    fd = 7

    def select_(fds, *_):
        now[0] += 5
        if now[0] > until:
            raise Done
        return ([fd], [], []) if now[0] in pending else ([], [], [])

    mod.time.monotonic = lambda: now[0]
    mod.select.select = select_
    mod.os.read = lambda _fd, _n: mod.EVENT.pack(0, 0, *pending[now[0]])
    device = {"/dev/input/event0": {"fd": fd, "last": {0: 0}, "range": {0: 1000}}}
    mod.open_devices = lambda old: device

    def sway(*args):
        if args[0] == "-t":
            return json.dumps([{"name": "DSI-2", "power": True, "dpms": True}, {"name": "DSI-1", "power": False, "dpms": True}])
        sent.append((now[0], args[0]))
        return ""
    mod.sway = sway
    try:
        mod.main()
    except Done:
        pass
    return sent


assert load(None).IDLE == 300                                     # the default
assert load("other=1\nasgard.idle_blank=120\n").IDLE == 120
assert load("asgard.idle_blank=0\n").IDLE == 0

# Off after IDLE seconds, only what was lit; any input brings it back, and the count starts over
sent = simulate(load("asgard.idle_blank=100\n"), {150: (EV_KEY, 304, 1)}, 400)
assert sent == [(100, "output DSI-2 dpms off"), (150, "output DSI-2 dpms on"), (250, "output DSI-2 dpms off")]

# A stick moved far enough counts as input, and turns the screens on; its jitter doesn't
sent = simulate(load("asgard.idle_blank=100\n"), {150: (EV_ABS, 0, 500), 250: (EV_ABS, 0, 501)}, 300)
assert sent == [(100, "output DSI-2 dpms off"), (150, "output DSI-2 dpms on"), (250, "output DSI-2 dpms off")]

# 0 = never
assert simulate(load("asgard.idle_blank=0\n"), {}, 3000) == []
print("ok")
