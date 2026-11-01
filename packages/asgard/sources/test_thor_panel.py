# spec: PANEL-3
# requires: lib:libSDL2-2.0.so.0 lib:libSDL2_ttf-2.0.so.0 lib:libSDL2_image-2.0.so.0
"""Run: python -I test_thor_panel.py  (no Thor needed): thor_panel.py --serve's line protocol, with fake hardware."""
import io
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import thor_panel as tp  # noqa: E402

applied = []
tp.STATE = os.path.join(tempfile.mkdtemp(), "panel.json")
tp.status = lambda st: {"bat": "87"}
tp.activate = lambda key, st: {"wifi": "Wi-Fi off", "task": "close"}.get(key) or 1 / 0  # anything else breaks
tp.set_slider = lambda key, v: applied.append((key, v))

out = io.StringIO()
tp.serve(io.StringIO("1\tstatus\n2\twifi\n3\tvol\t140\n4\tbogus\n5\ttask\n"), out)
replies = dict(line.split("\t", 1) for line in out.getvalue().splitlines())
assert replies["1"] == '{"bat": "87"}'
assert replies["2"] == '"Wi-Fi off"' and replies["5"] == '"close"'
assert replies["3"] == "null" and applied == [("vol", 100)]         # clamped, applied before serve() returns
assert replies["4"].startswith('{"error"')                           # a failing tile still answers
print("ok")
