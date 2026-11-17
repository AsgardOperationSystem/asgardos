#!/usr/bin/env python3
# spec: AUD-3
# requires: file:build/AsgardOS-SM8550.aarch64/toolchain/bin/luajit
"""Run: python -I test_one_volume.py  (no Thor): asgard-one-volume.lua, under luajit with WirePlumber's API stubbed,
puts `volume`'s level on every output route WirePlumber selects (Bluetooth connecting, the jack, boot) in place of the
level it saved for it, leaves inputs alone, falls back to its own state before `volume` has run, and is installed and
loaded; `volume` publishes the level. That a pair or the jack really comes up at it is a human check."""
import os
import re
import subprocess
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..", "..", "..")
LUAJIT = os.path.join(ROOT, "build/AsgardOS-SM8550.aarch64/toolchain/bin/luajit")
SCRIPT = os.path.join(HERE, "..", "wireplumber", "asgard-one-volume.lua")
read = lambda *p: open(os.path.join(*p)).read()

# One case per run: metadata percent (nil = `volume` hasn't run), the saved state, routes as apply-route-props leaves them.
HARNESS = r"""
local meta_percent, state_percent = %s, %s
local saved = {}
local function copy (t) if type (t) ~= "table" then return t end local c = {} for k, v in pairs (t) do c[k] = copy (v) end return c end
package.preload["common-utils"] = function () return { get_default_metadata_object = function ()
  return { find = function (_, subject, key) assert (subject == 0 and key == "asgard.volume") return meta_percent end } end } end
package.preload["device-info-cache"] = function () return {
  get_device_info = function () return { name = "bluez_card.X" } end,
  find_route_info = function (_, route) return ({ [1] = { name = "headset-output", direction = "Output" },
                                                  [2] = { name = "headset-input", direction = "Input" } })[route.index] end } end
Log = { open_topic = function () return { info = function () end } end }
State = function () return { load = function () return { percent = state_percent } end,
                             save_after_timeout = function (_, t) saved = copy (t) end } end
Constraint = function (t) return t end
EventInterest = function (t) return t end
local hook
SimpleEventHook = function (t) hook = t return { register = function () end } end
local function wrap (kind) return function (v) return { kind = kind, v = v, to_string = function (self) return self end } end end
Json = { Array = wrap ("array"), Object = wrap ("object"), Raw = function (r) return { parse = function () return copy (r) end } end }
dofile (arg[1])
assert (hook.after == "device/apply-route-props" and hook.before == "device/apply-routes")
local data = { ["selected-routes"] = {
  ["0"] = { index = 1, props = { channelVolumes = { 0.729, 0.729 }, channelMap = { "FL", "FR" }, mute = false } },
  ["1"] = { index = 2, props = { channelVolumes = { 0.5 } } },
  ["2"] = { index = 1 } } }
hook.execute ({ get_subject = function () return {} end, get_data = function (_, k) return data[k] end,
                set_data = function (_, k, v) data[k] = v end })
for _, id in ipairs ({ "0", "1", "2" }) do
  local r = data["selected-routes"][id]
  local p = r.v and r.v.props and r.v.props.v or r.props or {}
  local cv = p.channelVolumes and (p.channelVolumes.v or p.channelVolumes) or {}
  local out = {}
  for i, x in ipairs (cv) do out[i] = string.format ("%%.6f", x) end
  print (id .. " " .. table.concat (out, ","))
end
print ("saved " .. tostring (saved.percent))
"""


def run(meta, state):
    lua = lambda v: "nil" if v is None else f'"{v}"'
    with tempfile.TemporaryDirectory() as t:
        with open(f"{t}/h.lua", "w") as f:
            f.write(HARNESS % (lua(meta), lua(state)))
        r = subprocess.run([LUAJIT, f"{t}/h.lua", SCRIPT], capture_output=True, text=True, timeout=30)
        assert r.returncode == 0, r.stderr
        return dict(line.split(" ", 1) for line in r.stdout.splitlines())


# `volume` ran (45 %): both output routes at 0.45^3, whatever was saved for them; the input keeps its own; it's kept.
out = run("45", None)
assert out["0"] == "0.091125,0.091125" and out["2"] == "0.091125", out
assert out["1"] == "0.500000", out
assert out["saved"] == "45", out
# Before `volume` runs (boot, a WirePlumber restart): the last level it saw.
out = run(None, "60")
assert out["0"] == "0.216000,0.216000" and out["saved"] == "nil", out
# Nothing known yet: WirePlumber's own levels stay.
out = run(None, None)
assert out["0"] == "0.729000,0.729000" and out["1"] == "0.500000" and out["2"] == "", out

# Installed and loaded in the profile the service runs (main-systemwide inherits main), after the routes' own state.
conf = read(HERE, "..", "wireplumber", "63-asgard-one-volume.conf")
assert "name = asgard-one-volume.lua, type = script/lua" in conf and re.search(r"main = \{\s*asgard\.one-volume = required", conf)
assert "cp ${PKG_DIR}/wireplumber/asgard-one-volume.lua ${INSTALL}/usr/share/wireplumber/scripts/" in read(HERE, "..", "package.mk")
# `volume` publishes the level before it may stop waiting for the device sink.
vol = read(ROOT, "packages/asgardos/sources/scripts/volume")
assert re.search(r"^pw-metadata 0 asgard\.volume \$\{VOLUME\}", vol, re.M), vol
assert vol.index("pw-metadata 0 asgard.volume") < vol.index("pactl get-default-sink")
print("one volume: ok")
