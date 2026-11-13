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
script = script.replace('POWER_SUPPLY_PATH="/sys/class/power_supply"', f'POWER_SUPPLY_PATH="{T}/power_supply"')
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

# Connect that fails ends on a line saying what to do; Settings shows the last line.
for name, body in (("bluetoothctl", 'case "$2" in info) echo "Connected: no" ;; connect) exit 1 ;; esac\n'),
                   ("rfkill", f'cat {T}/rfkill\n')):
    with open(f"{T}/bin/{name}", "w") as f:
        f.write("#!/bin/sh\n" + body)
    os.chmod(f"{T}/bin/{name}", 0o755)
MAC = "AA:BB:CC:DD:EE:FF"
with open(f"{T}/rfkill", "w") as f:
    f.write("Soft blocked: no\n")
res = bt("connect", MAC)
assert (res.stdout + res.stderr).strip().splitlines()[-1] == "ERROR: Couldn't connect. Is the device on and nearby?", res
with open(f"{T}/rfkill", "w") as f:
    f.write("Soft blocked: yes\n")
res = bt("connect", MAC)
assert res.stderr.strip().splitlines()[-1] == "ERROR: The Bluetooth radio is off", res

# list: each trusted device's battery while connected, from BlueZ (as bluetoothctl prints it), else from the kernel's
# power_supply entry named after its address (hid-playstation: lower case; hid-nintendo: upper case), else none.
DEVICES = {"11:22:33:44:55:66": ("Headphones", "yes", "\tBattery Percentage: 0x46 (70)\n"),
           "A0:AB:51:00:00:01": ("DualSense", "yes", ""),
           "98:B6:E9:00:00:02": ("Pro Controller", "yes", ""),
           "C0:FF:EE:00:00:03": ("Off pad", "no", ""),
           "C0:FF:EE:00:00:04": ("Plain pad", "yes", "")}
case = "".join(f'  {mac}) printf "\\tConnected: {conn}\\n{batt}" ;;\n' for mac, (_, conn, batt) in DEVICES.items())
with open(f"{T}/bin/bluetoothctl", "w") as f:
    f.write(f'#!/bin/sh\n[ "$2" = info ] || exit 1\ncase "$3" in\n{case}esac\n')
for mac, (name, _, _) in DEVICES.items():
    os.makedirs(f"{T}/storage/.cache/bluetooth/00:00:00:00:00:00/{mac}")
    with open(f"{T}/storage/.cache/bluetooth/00:00:00:00:00:00/{mac}/info", "w") as f:
        f.write(f"[General]\nName={name}\nTrusted=true\n")
for entry, capacity in (("ps-controller-battery-a0:ab:51:00:00:01", "55"),
                        ("nintendo_switch_controller_battery_98:B6:E9:00:00:02", "40"),
                        ("ps-controller-battery-c0:ff:ee:00:00:03", "90"),   # not connected: not shown
                        ("battery", "77")):                                   # the Thor's own
    os.makedirs(f"{T}/power_supply/{entry}")
    with open(f"{T}/power_supply/{entry}/capacity", "w") as f:
        f.write(capacity + "\n")
# No PipeWire (pactl fails): no codec, and the rest still listed
with open(f"{T}/bin/pactl", "w") as f:
    f.write('#!/bin/sh\nexit 1\n')
os.chmod(f"{T}/bin/pactl", 0o755)
listed = {m.group(1): m.group(2) for m in re.finditer(r'name="([^"]*)".*battery="([^"]*)"', bt("list").stdout)}
assert listed == {"Headphones": "70", "DualSense": "55", "Pro Controller": "40", "Off pad": "", "Plain pad": ""}, listed
assert set(re.findall(r'codec="([^"]*)"', bt("list").stdout)) == {""}

# codec: from the api.bluez5.* properties of the device's sink in pactl's listing (address in either case, codec
# before or after it), named the way it's known; a pad, the speaker sink and a disconnected device have none
SINK = 'Sink #{n}\n\tName: {name}\n\tProperties:\n{props}\tFormats:\n\t\tpcm\n\n'
sinks = (SINK.format(n=40, name="thor_dsp_speaker", props='\t\tnode.name = "thor_dsp_speaker"\n')
         + SINK.format(n=41, name="bluez_output.11_22_33_44_55_66.1",
                       props='\t\tapi.bluez5.codec = "ldac"\n\t\tapi.bluez5.address = "11:22:33:44:55:66"\n')
         + SINK.format(n=42, name="bluez_output.C0_FF_EE_00_00_03.1",
                       props='\t\tapi.bluez5.address = "c0:ff:ee:00:00:03"\n\t\tapi.bluez5.codec = "aac"\n'))
with open(f"{T}/sinks", "w") as f:
    f.write(sinks)
with open(f"{T}/bin/pactl", "w") as f:
    f.write(f'#!/bin/sh\n[ "$*" = "list sinks" ] && cat {T}/sinks\n')
codecs = {m.group(1): m.group(2) for m in re.finditer(r'name="([^"]*)".*codec="([^"]*)"', bt("list").stdout)}
assert codecs == {"Headphones": "LDAC", "DualSense": "", "Pro Controller": "", "Off pad": "", "Plain pad": ""}, codecs
for pw, shown in (("sbc_xq", "SBC-XQ"), ("aptx_hd", "aptX HD"), ("aptx", "aptX"), ("msbc", "mSBC"), ("cvsd", "CVSD"),
                  ("aac", "AAC"), ("sbc", "SBC")):
    with open(f"{T}/sinks", "w") as f:
        f.write(sinks.replace('"ldac"', f'"{pw}"'))
    assert f'name="Headphones"' in bt("list").stdout and f'codec="{shown}"' in bt("list").stdout, (pw, bt("list").stdout)

# codecs: the A2DP profiles of the device's card that are available, PipeWire's preferred first, named as its
# description names them; the call profile, one not available and another device's card left out. codec switches to
# one through its profile, and refuses one not offered.
CARD = 'Card #{n}\n\tName: {name}\n\tProperties:\n\t\tapi.bluez5.address = "{addr}"\n\tProfiles:\n{profiles}\tActive Profile: a2dp-sink\n\n'
PROF = '\t\t{p}: {desc} (sinks: 1, sources: 0, priority: {prio}, available: {av})\n'
headphones = "".join(PROF.format(p=p, desc=d, prio=n, av=a) for p, d, n, a in (
    ("off", "Off", 0, "yes"),
    ("a2dp-sink-sbc", "High Fidelity Playback (A2DP Sink, codec SBC)", 18, "yes"),
    ("a2dp-sink-sbc_xq", "High Fidelity Playback (A2DP Sink, codec SBC-XQ)", 17, "yes"),
    ("a2dp-sink-aac", "High Fidelity Playback (A2DP Sink, codec AAC)", 19, "yes"),
    ("a2dp-sink-aptx_hd", "High Fidelity Playback (A2DP Sink, codec aptX HD)", 21, "no"),
    ("a2dp-sink", "High Fidelity Playback (A2DP Sink, codec LDAC)", 20, "yes"),
    ("headset-head-unit", "Headset Head Unit (HSP/HFP, codec mSBC)", 30, "yes")))
other = PROF.format(p="a2dp-sink-aac", desc="High Fidelity Playback (A2DP Sink, codec AAC)", prio=19, av="yes")
with open(f"{T}/cards", "w") as f:
    f.write(CARD.format(n=1, name="bluez_card.C0_FF_EE_00_00_03", addr="C0:FF:EE:00:00:03", profiles=other)
            + CARD.format(n=2, name="bluez_card.11_22_33_44_55_66", addr="11:22:33:44:55:66", profiles=headphones))
with open(f"{T}/sinks", "w") as f:
    f.write(sinks)
with open(f"{T}/bin/pactl", "w") as f:
    f.write(f'#!/bin/sh\ncase "$*" in\n  "list sinks") cat {T}/sinks ;;\n  "list cards") cat {T}/cards ;;\n'
            f'  set-card-profile*) echo "$*" >> {T}/pactl.log ;;\n  *) exit 1 ;;\nesac\n')
offered = {m.group(1): m.group(2) for m in re.finditer(r'name="([^"]*)".*codecs="([^"]*)"', bt("list").stdout)}
assert offered == {"Headphones": "LDAC,AAC,SBC,SBC-XQ", "DualSense": "", "Pro Controller": "", "Off pad": "", "Plain pad": ""}, offered
res = bt("codec", "11:22:33:44:55:66", "AAC")
assert read(f"{T}/pactl.log") == "set-card-profile bluez_card.11_22_33_44_55_66 a2dp-sink-aac\n", res
res = bt("codec", "11:22:33:44:55:66", "LDAC")
assert read(f"{T}/pactl.log").splitlines()[-1] == "set-card-profile bluez_card.11_22_33_44_55_66 a2dp-sink", res
res = bt("codec", "11:22:33:44:55:66", "aptX HD")                 # listed, but not available
assert res.stderr.strip().splitlines()[-1].startswith("ERROR: aptX HD isn't offered"), res
assert len(read(f"{T}/pactl.log").splitlines()) == 2
for mac in DEVICES:
    subprocess.run(["rm", "-r", f"{T}/storage/.cache/bluetooth/00:00:00:00:00:00/{mac}"], check=True)

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
