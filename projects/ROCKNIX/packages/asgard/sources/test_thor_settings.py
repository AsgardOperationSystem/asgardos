"""Run: python -I test_thor_settings.py  (no Thor needed; SDL is never initialised)."""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import thor_settings as ts  # noqa: E402

with tempfile.TemporaryDirectory() as d:
    p = os.path.join(d, "system.cfg")
    open(p, "w").write('3ds.resolution_scale=0\n# comment kept\nwifi.key=a=b=c\n')
    c = ts.Conf(p)
    game = '3ds["Pokemon Alpha Sapphire (USA) (Rev 2).3ds"]'
    assert c.get("wifi.key") == "a=b=c"                       # '=' inside values survives
    c.set(f"{game}.resolution_scale", "2")
    assert c.get(f"{game}.resolution_scale") == "2"
    assert c.get("3ds.resolution_scale") == "0"                # per-game key doesn't touch the system key
    c.set(f"{game}.resolution_scale", "3")
    assert open(p).read().count("resolution_scale") == 2       # replaced in place, not duplicated
    c.set(f"{game}.resolution_scale", None)
    assert c.get(f"{game}.resolution_scale") == "" and "# comment kept" in open(p).read()
    assert not os.path.exists(p + ".thor-tmp")                  # atomic write cleaned up
    c.set('3ds["A b (USA).3ds"].cpu_speed', "1")
    c.set('3ds["A b (USA).3ds"].rewind', "0")
    c.set('gb["Tetris.gb"].ratio', "4/3")
    ts.conf = c
    assert ts.overridden_games() == [("3ds", "A b (USA).3ds"), ("gb", "Tetris.gb")]  # listed once each

assert ts.sh("it's") == "'it'\\''s'"

import playlog  # noqa: E402
with tempfile.TemporaryDirectory() as d:
    log = os.path.join(d, "playtime.jsonl")
    open(log, "w").write('{"rom": "/r/a.gba", "sys": "gba", "start": 100, "secs": 60}\n'
                         '{"rom": "/r/a.gba", "sys": "gba", "st\n'     # torn line from a power loss
                         '{"rom": "/r/a.gba", "sys": "gba", "start": 500, "secs": 30}\n')
    assert playlog.totals(log) == {"/r/a.gba": {"secs": 90, "sessions": 2, "last": 530}}
print("ok")
