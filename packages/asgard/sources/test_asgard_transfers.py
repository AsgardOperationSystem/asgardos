#!/usr/bin/env python3
# spec: XFER-1 XFER-3 XFER-4 XFER-5
"""Run: python -I test_asgard_transfers.py  (no Thor): asgard-transfers.py's queue against a fake Thor. XFER-1: one job at a
time, an update first, the same game not queued twice, waiting scrapes kept across a restart, cancel. XFER-3: a sleep while
busy is a standby (Home told, the screens off, no suspend), it suspends once the queue empties, and the power key / lid ends
it early. XFER-4: no internet pauses the queue and a sleep then suspends at once; the battery floor ends a standby; a wake
resumes it. XFER-5: the inhibitor is held exactly while busy, and an idle worker waits with no timeout. Over the real socket:
run, status and sleep with no service. The power key and lid reaching it is test_power_handler_standby.sh; a real standby on
a Thor is a device check."""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = tempfile.mkdtemp()
os.environ["ASGARD_ROOT"] = ROOT
# A socket path has to fit in 108 bytes, which test.sh's TMPDIR doesn't leave room for
os.environ["ASGARD_TRANSFERS_SOCK"] = f"/tmp/asgard-transfers-test-{os.getpid()}.sock"
for d in ("run", "storage/.config/asgard"):
    os.makedirs(f"{ROOT}/{d}", exist_ok=True)
spec = importlib.util.spec_from_file_location("transfers", os.path.join(HERE, "asgard-transfers.py"))
tr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tr)


class Proc:
    """A job's process: finishes when the test says, with the output it was given."""

    def __init__(self, out):
        self.out, self.done, self.returncode = out, threading.Event(), None

    def communicate(self, timeout=None):
        if not self.done.wait(timeout if timeout is not None else 10):
            if timeout is not None:
                raise subprocess.TimeoutExpired("job", timeout)
            raise AssertionError("job never finished")
        self.returncode = 0
        return self.out, ""

    def terminate(self):
        self.out = ""
        self.done.set()

    kill = terminate


class Fake:
    def __init__(self):
        self.log, self.procs, self.lid, self.bat = [], [], False, (80, False)
        self.answers = {}

    def inhibit(self, on):
        self.log.append(f"inhibit {on}")

    def lid_closed(self):
        return self.lid

    def battery(self):
        return self.bat

    def home(self, cmd):
        self.log.append(f"home {cmd}")

    def screens(self, verb):
        self.log.append(f"screens {verb}")

    def suspend(self):
        self.log.append("suspend")

    def start(self, job):
        self.log.append(f"start {job['kind']} {job['label']}")
        p = Proc(self.answers.get(job["label"], json.dumps({"source": "libretro", "media": ["covers"], "details": []})))
        self.procs.append(p)
        return p


def until(cond, what):
    end = time.monotonic() + 5
    while not cond():
        assert time.monotonic() < end, what
        time.sleep(0.01)


def game(stem, system="gba"):
    return [system, f"/storage/roms/{system}/{stem}.gba", stem]


def started(f):
    return [line for line in f.log if line.startswith("start")]


def new(queue_file=None):
    f = Fake()
    t = tr.Transfers(f, queue_file or tempfile.mktemp(dir=ROOT))
    threading.Thread(target=t.worker, daemon=True).start()
    return f, t


# XFER-1: one at a time, in order; the same game isn't queued twice; an update goes before waiting scrapes
f, t = new()
t.add_scrapes([game("Zelda"), game("Metroid"), game("Zelda")])
until(lambda: len(f.procs) == 1, "first job never started")
assert started(f) == ["start scrape Zelda"] and [j["label"] for j in t.queue] == ["Metroid"], (f.log, t.queue)
assert f.log[0] == "inhibit True", f.log                            # XFER-5: held as soon as there's work
t.add_update()
f.procs[0].done.set()
until(lambda: len(f.procs) == 2, "second job never started")
assert started(f)[1] == "start update Asgard update", f.log
f.procs[1].done.set()
until(lambda: len(f.procs) == 3, "third job never started")
f.procs[2].done.set()
until(lambda: not t.is_busy(), "never went idle")
assert started(f) == ["start scrape Zelda", "start update Asgard update", "start scrape Metroid"], f.log
assert f.log[-1] == "inhibit False" and f.log.count("inhibit True") == 1, f.log
assert t.status()["scrape"] == {"done": 2, "found": 2, "total": 2}, t.status()
assert f.log.count("home rescan") == 1, f.log                       # Home rescanned once the last game was in
assert not os.path.exists(tr.BUSY)
assert "suspend" not in f.log                                        # idle with the lid open: nothing to sleep for

# XFER-5: idle, the worker waits with no timeout (wakes nothing in sleep); with a hold, until the hold ends
assert t.wait_time() is None
t.hold("upload", 0.2)
assert 0 < t.wait_time() <= 0.2 and t.is_busy() and os.path.exists(tr.BUSY)
until(lambda: not t.busy, "a hold never ran out")
assert t.wait_time() is None and not os.path.exists(tr.BUSY)

# waiting scrapes survive a restart (the one running too: it wasn't done); updates don't (their check is in /run)
q = tempfile.mktemp(dir=ROOT)
f, t = new(q)
t.add_scrapes([game("A"), game("B")])
t.add_update()
until(lambda: f.procs, "nothing started")
saved = json.load(open(q))["queue"]
assert [j["args"][2] for j in saved] == ["A", "B"], saved
f2 = Fake()
t2 = tr.Transfers(f2, q)
assert [j["label"] for j in t2.queue] == ["A", "B"], t2.queue

# cancel: a waiting job, and the running one (its process stopped)
t.cancel("all")
until(lambda: not t.is_busy(), "cancel left it busy")
assert t.queue == [] and json.load(open(q))["queue"] == [], t.queue

# XFER-3: a sleep while busy is a standby: Home pauses the game, the screens go off, no suspend; the queue empties: suspend
f, t = new()
assert t.sleep() == "suspend" and f.log == ["suspend"], f.log      # nothing to do: suspends at once
f.log.clear()
t.add_scrapes([game("Zelda"), game("Metroid")])
until(lambda: f.procs, "nothing started")
assert t.sleep() == "standby", f.log
assert "home standby" in f.log and "screens standby" in f.log and "suspend" not in f.log, f.log
assert os.path.exists(tr.STANDBY)
assert 0 < t.wait_time() <= tr.BATTERY_POLL                          # watching the battery while standing by
f.procs[0].done.set()
until(lambda: len(f.procs) == 2, "standby stopped the queue")
f.procs[1].done.set()
until(lambda: "suspend" in f.log, "never suspended once done")
i = f.log.index("suspend")
assert f.log[i - 2:i] == ["inhibit False", "screens standby-dark"], f.log   # inhibitor gone, screens back dark, then suspend
assert "home standby-end" not in f.log                              # the game stays paused through the sleep
assert not os.path.exists(tr.STANDBY) and not t.standby

# the power key or the lid ends a standby early: screens and game back, the work carries on awake
f, t = new()
t.add_scrapes([game("Zelda")])
until(lambda: f.procs, "nothing started")
t.sleep()
assert t.wake() and f.log[-2:] == ["screens standby-end", "home standby-end"], f.log
f.procs[0].done.set()
until(lambda: not t.is_busy(), "never finished")
assert "suspend" not in f.log, f.log
assert not t.wake()                                                 # no standby: nothing to end

# done with the lid shut and no standby running (it was ended, then the lid shut while logind was held off): suspend
f, t = new()
t.add_scrapes([game("Zelda")])
until(lambda: f.procs, "nothing started")
f.lid = True
f.procs[0].done.set()
until(lambda: "suspend" in f.log, "stayed up with the lid shut")

# busy again with the lid shut (a wake on the charger resumed it): a standby, not lit screens
f, t = new()
f.lid = True
t.add_scrapes([game("Zelda")])
assert "screens standby" in f.log and t.standby, f.log
t.cancel("all")
until(lambda: "suspend" in f.log, "never suspended")

# XFER-4: no internet pauses the queue, the game goes back first; a paused queue isn't work, so a sleep suspends at once
f, t = new()
f.answers["Zelda"] = json.dumps({"error": "No internet connection: scraping needs it"})
t.add_scrapes([game("Zelda"), game("Metroid")])
until(lambda: f.procs, "nothing started")
f.procs[0].done.set()
until(lambda: t.paused == "offline" and not t.busy, "no internet didn't pause it")
assert [j["label"] for j in t.queue] == ["Zelda", "Metroid"] and len(f.procs) == 1, (t.queue, f.log)
assert t.sleep() == "suspend"
f.answers.clear()
assert t.resume(auto=True)                                           # after a wake: tries again
until(lambda: len(f.procs) == 2, "resume didn't start it")
f.procs[1].done.set()
until(lambda: len(f.procs) == 3, "")
f.procs[2].done.set()
until(lambda: not t.is_busy(), "")

# the battery floor ends a standby: the job running goes back in the queue, and the Thor suspends
tr.BATTERY_POLL = 0.05
f, t = new()
t.add_scrapes([game("Zelda")])
until(lambda: f.procs, "nothing started")
t.sleep()
f.bat = (tr.BATTERY_FLOOR, False)
until(lambda: "suspend" in f.log, "low battery didn't end the standby")
assert t.paused == "battery" and [j["label"] for j in t.queue] == ["Zelda"], (t.paused, t.queue)
assert not t.resume(auto=True)                                       # woke on the same low battery: stays paused
f.bat = (tr.BATTERY_FLOOR, True)
assert t.resume(auto=True)                                           # on the charger: carries on
until(lambda: len(f.procs) == 2, "")
f.procs[1].done.set()
until(lambda: not t.is_busy(), "")
# on the charger the floor doesn't apply
f, t = new()
f.bat = (5, True)
t.add_scrapes([game("Zelda")])
until(lambda: f.procs, "")
t.sleep()
time.sleep(0.2)
assert "suspend" not in f.log and t.standby, f.log
t.cancel("all")
until(lambda: "suspend" in f.log, "")

# over the socket: the real CLI against the real service, scraping with a stand-in asgard-scrape.py
share = tempfile.mkdtemp(dir=ROOT)
open(f"{share}/asgard-scrape.py", "w").write(
    "import json,sys,time\ntime.sleep(0.2)\nprint(json.dumps({'source':'libretro','matched':sys.argv[3],'media':['covers'],'details':[]}))\n")
env = dict(os.environ, ASGARD_ROOT=ROOT, ASGARD_SHARE=share, PATH=f"{share}:{os.environ['PATH']}")
for tool in ("systemd-inhibit", "busctl", "systemctl"):
    open(f"{share}/{tool}", "w").write(f"#!/bin/sh\necho {tool} \"$@\" >> {share}/calls\n[ {tool} = systemd-inhibit ] && exec sleep 1000\n")
    os.chmod(f"{share}/{tool}", 0o755)
cli = [sys.executable, "-I", os.path.join(HERE, "asgard-transfers.py")]
# no service: sleep still suspends, a scrape still scrapes, status says so
r = subprocess.run(cli + ["sleep"], env=env, capture_output=True, text=True)
assert "systemctl suspend" in open(f"{share}/calls").read(), r
r = subprocess.run(cli + ["run", "scrape", *game("Zelda")], env=env, capture_output=True, text=True)
assert json.loads(r.stdout)["matched"] == "Zelda", r
svc = subprocess.Popen(cli + ["serve"], env=env)
try:
    until(lambda: os.path.exists(tr.SOCK), "the service never listened")
    r = subprocess.run(cli + ["add", "scrape", *game("A"), *game("B")], env=env, capture_output=True, text=True)
    assert json.loads(r.stdout)["added"] == [1, 2], r
    r = subprocess.run(cli + ["run", "scrape", *game("C")], env=env, capture_output=True, text=True, timeout=10)
    assert json.loads(r.stdout)["matched"] == "C", r                 # ran next, its result printed
    st = json.loads(subprocess.run(cli + ["status"], env=env, capture_output=True, text=True).stdout)
    assert st["scrape"]["total"] == 3 and st["busy"] in (True, False), st
    until(lambda: not json.loads(subprocess.run(cli + ["status"], env=env, capture_output=True, text=True).stdout)["busy"],
          "the service never finished")
    calls = open(f"{share}/calls").read()
    assert "systemd-inhibit --what=sleep:handle-lid-switch" in calls, calls
    assert oct(os.stat(tr.SOCK).st_mode & 0o777) == "0o600"          # root's only: it can stop and start work
finally:
    svc.terminate()
    svc.wait()
    if os.path.exists(tr.SOCK):
        os.remove(tr.SOCK)
print("ok")
