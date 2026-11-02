#!/usr/bin/env python3
# spec: NET-1
# requires: cmd:awk cmd:tar
"""Run: python -I test_bluetooth_pairing.py  (no Thor, no radio): asgardos-bluetooth with its paths moved to a temp dir and the
agent's decisions with dbussy and ravel stubbed. Whether a real device pairs is a human check (docs/human-checks.md)."""
import asyncio
import logging
import os
import re
import stat
import subprocess
import sys
import tempfile
import types

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(HERE, "../../asgardos/sources/scripts")

tmp = tempfile.TemporaryDirectory()
T = tmp.name
os.makedirs(f"{T}/run")
os.makedirs(f"{T}/storage/.cache/bluetooth")
os.makedirs(f"{T}/bin")

# ---- the script
script = open(f"{SCRIPTS}/asgardos-bluetooth").read()
assert ". /etc/profile\n" in script
script = script.replace(". /etc/profile\n", "").replace('"/run/', f'"{T}/run/').replace('STORAGE_PATH="/storage"', f'STORAGE_PATH="{T}/storage"')
with open(f"{T}/bin/bt", "w") as f:
    f.write(script)
# sleep records what the agent would see at that moment, and doesn't wait
with open(f"{T}/bin/sleep", "w") as f:
    f.write(f'#!/bin/sh\ncat {T}/run/bt_discovery_control >> {T}/seen 2>/dev/null\n')
for name in ("bt", "sleep"):
    os.chmod(f"{T}/bin/{name}", os.stat(f"{T}/bin/{name}").st_mode | stat.S_IEXEC)


def bt(*args):
    env = {**os.environ, "PATH": f"{T}/bin:{os.environ['PATH']}"}
    return subprocess.run([f"{T}/bin/bt", *args], env=env, capture_output=True, text=True, timeout=30)


def run_file(name):
    return f"{T}/run/{name}"


def read(path):
    with open(path) as f:
        return f.read()


# No agent: says so, rather than looking forever in silence.
res = bt("scan_start")
assert "agent is not running" in res.stderr, res
assert not os.path.exists(run_file("bt_discovery_control"))

with open(run_file("bt_agent_status"), "w") as f:
    f.write(str(os.getpid()))

assert bt("scan_start").returncode == 0
assert read(run_file("bt_discovery_control")).strip() == "start"
assert read(run_file("bt_listing")) == ""

# Latest line per device, in the order first seen; nameless and removed ones left out.
with open(run_file("bt_listing"), "w") as f:
    f.write('<device id="AA" name="None" status="added" type="unknown" />\n'
            '<device id="BB" name="Pad" status="added" type="joystick" />\n'
            '<device id="CC" name="None" status="added" type="unknown" />\n'
            '<device id="DD" name="Gone" status="added" type="audio" />\n'
            '<device id="DD" name="Gone" status="removed" type="audio" />\n'
            '<device id="CC" name="TV" status="added" type="audio" />\n')
assert re.findall(r'name="([^"]*)"', bt("scan_list").stdout) == ["Pad", "TV"]

bt("scan_stop")
assert read(run_file("bt_discovery_control")).strip() == "stop"
assert not os.path.exists(run_file("bt_listing"))
assert bt("scan_list").stdout == ""

# trust starts the scan the agent needs, and cleans up after itself. A stale message isn't this attempt's result.
with open(run_file("bt_status"), "w") as f:
    f.write("Connected successfully (Old)\n")
res = bt("trust", "input")
assert "start" in read(f"{T}/seen"), "trust never started discovery"
assert read(run_file("bt_discovery_control")).strip() == "stop"
assert not os.path.exists(run_file("bt_device"))
assert "Old" not in res.stdout and res.stdout.strip().splitlines()[-1] == "No device found", res.stdout

# ---- the agent
class Signature(str):
    pass


dbussy = types.ModuleType("dbussy")
dbussy.DBUS = types.SimpleNamespace(Signature=Signature)
ravel = types.ModuleType("ravel")
ravel.INTERFACE = types.SimpleNamespace(SERVER=0)
for deco in ("interface", "method", "signal"):
    setattr(ravel, deco, lambda *a, **k: (lambda x: x))
sys.modules["dbussy"], sys.modules["ravel"] = dbussy, ravel

source = read(f"{SCRIPTS}/asgardos-bluetooth-agent").replace('"/run/', f'"{T}/run/').replace('"/var/log/bluetooth-agent.log"', f'"{T}/agent.log"')
agent = {"__name__": "agent"}
exec(compile(source, "asgardos-bluetooth-agent", "exec"), agent)
logging.disable(logging.CRITICAL)


def var(sig, value):
    return (Signature(sig), value)


def device(addr="AA:BB", **extra):
    return {"Address": var("s", addr), "Paired": var("b", False), "Trusted": var("b", False), "Connected": var("b", False), **extra}


def actions(call):
    """What the agent does for a coroutine call: the names of the steps it took."""
    done = []

    def step(name):
        async def run(*a):
            done.append(name)
        return run
    # Only these three: patch.dict would also undo what the agent remembers between calls, such as the last pick
    real = {name: agent[name] for name in ("doPairing", "doTrusting", "doConnect")}
    agent.update(doPairing=step("pair"), doTrusting=step("trust"), doConnect=step("connect"))
    try:
        asyncio.run(call())
    finally:
        agent.update(real)
    return done


agent["gdiscovering"] = True
connect = agent["connect_device"]

# Picked by address: pairs even with no type. "input" still takes only controllers.
assert actions(lambda: connect("/d", "AA:BB", device(), False, "AA:BB")) == ["pair", "trust", "connect"]
assert actions(lambda: connect("/d", "AA:BB", device(), False, "input")) == []
assert actions(lambda: connect("/d", "AA:BB", device(Icon=var("s", "audio-card")), False, "input")) == []
assert actions(lambda: connect("/d", "AA:BB", device(Icon=var("s", "input-gaming")), False, "input")) == ["pair", "trust", "connect"]

with open(run_file("bt_device"), "w") as f:
    f.write("AA:BB\n")
changed = agent["properties_changed"]

# A pad that drops doesn't get reconnected by the pairing flow: the variant has to be unwrapped to see False.
agent["gdevices"]["/d"] = device(Paired=var("b", True), Trusted=var("b", True), Connected=var("b", True))
assert actions(lambda: changed("org.bluez.Device1", {"Connected": var("b", False)}, [], "/d")) == []
# Paired arriving forces the connect, even with discovery off by then.
agent["gdiscovering"] = False
agent["gdevices"]["/d"] = device(Paired=var("b", True), Trusted=var("b", True))
assert actions(lambda: changed("org.bluez.Device1", {"Paired": var("b", True)}, [], "/d")) == ["connect"]

# A name that arrives after the device was listed reaches the list; other changes don't add lines.
os.remove(run_file("bt_device"))
agent["glisting_mode"] = True
agent["gdevices"]["/e"] = device("EE:FF")
listing = run_file("bt_listing")
agent["listing_dev_event"]("/e", agent["gdevices"]["/e"], True)
assert actions(lambda: changed("org.bluez.Device1", {"RSSI": var("n", -40)}, [], "/e")) == []
assert read(listing).count("EE:FF") == 1
assert actions(lambda: changed("org.bluez.Device1", {"Name": var("s", "TV")}, [], "/e")) == []
assert read(listing).splitlines()[-1].startswith('<device id="EE:FF" name="TV"')
assert re.findall(r'name="([^"]*)"', bt("scan_list").stdout) == ["TV"]

# bluez drops its devices when the scan ends: that mustn't leave a listing behind.
os.remove(listing)
agent["glisting_mode"] = False
agent["interfaces_removed"]("/e", ["org.bluez.Device1"])
assert not os.path.exists(listing)


# A picked device the scan already found gets no further event if it sits still (a real WH-1000XM4 never paired this
# way, 2026-11-02): the agent's own loop has to act on the pick, with no event arriving.
def pick(addr):
    if addr:
        with open(run_file("bt_device"), "w") as f:
            f.write(addr + "\n")
    elif os.path.exists(run_file("bt_device")):
        os.remove(run_file("bt_device"))


def loop_turn():
    """One pass of the agent's control loop, and whatever it set going."""
    async def run():
        turn = asyncio.create_task(agent["discovery_control_loop"]())
        await asyncio.sleep(0.05)
        turn.cancel()
        if agent["gpick_task"]:
            await agent["gpick_task"]
    return actions(run)


os.remove(run_file("bt_discovery_control"))                            # the "stop" trust left: the loop would obey it
agent["gdevices"] = {"/x": device("XM:4M"), "/y": device("OT:HR")}
agent["gdiscovering"] = True
pick("XM:4M")
assert loop_turn() == ["pair", "trust", "connect"]
agent["gpick_task"] = None
assert loop_turn() == [], "acted on the same pick twice"

# Not before the scan is on (the pairing step needs it), and a new pick after the last one ended counts again.
pick(None)
assert loop_turn() == []
agent["gdiscovering"] = False
pick("XM:4M")
assert loop_turn() == []
agent["gdiscovering"] = True
assert loop_turn() == ["pair", "trust", "connect"]
agent["gpick_task"] = None

# Pairing makes the device report changes: those don't start a second pairing while the first runs.
agent["gpairing"].add("/x")
assert actions(lambda: connect("/x", "XM:4M", device("XM:4M"), False, "XM:4M")) == []
agent["gpairing"].discard("/x")
