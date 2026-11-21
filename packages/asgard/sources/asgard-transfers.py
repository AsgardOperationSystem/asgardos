#!/usr/bin/env python3
"""asgard-transfers.py: one queue for everything the Thor fetches (XFER-1), and the sleep that waits for it (XFER-3).

Update downloads and scrapes (Select > Scrape this game, Settings > Library > Scrape missing, the Library Manager) all
go through this queue, one job at a time, so one place knows when the Thor still has work to finish. While it has, a
sleep (the lid, the power key, Home's Sleep) becomes a standby: the game pauses, the screens, touch, stick lights and
the mid and prime cores go off, and Wi-Fi and storage stay on. When the queue empties, or the battery reaches
BATTERY_FLOOR off the charger, the Thor suspends as it would have. The lid opening or the power key ends a standby
early; the work carries on with the Thor awake.

  asgard-transfers.py serve                          the service (asgard-transfers.service)
  asgard-transfers.py add scrape <system> <rom> <stem>...   queue scrapes (three arguments a game)
  asgard-transfers.py add update                     queue the update download (asgard-update.py download), first
  asgard-transfers.py run scrape <system> <rom> <stem>      scrape one game next and print its result (Select > Scrape)
  asgard-transfers.py status                         JSON: what runs, what waits, why it's paused
  asgard-transfers.py cancel <id>|scrape|update|all  drop jobs (the one running is stopped)
  asgard-transfers.py resume                         carry on after a pause (no internet, low battery)
  asgard-transfers.py hold <name> <seconds>          count as busy that long (the Library Manager's uploads)
  asgard-transfers.py sleep                          sleep: a standby while busy, else suspend now
  asgard-transfers.py wake                           end a standby (the lid opened, the power key)
  asgard-transfers.py woke                           after every wake (sleep.d): resume a queue paused for battery or network

Idle, the service waits on its socket and nothing else, so it never wakes a sleeping Thor (PWR-9).
"""
import json
import os
import socket
import subprocess
import sys
import threading
import time

ROOT = os.environ.get("ASGARD_ROOT", "")
SOCK = os.environ.get("ASGARD_TRANSFERS_SOCK", ROOT + "/run/asgard-transfers.sock")
BUSY = ROOT + "/run/asgard-transfers.busy"         # exists while busy: power-handler reads it
STANDBY = ROOT + "/run/asgard-standby"             # exists during a standby
QUEUE = ROOT + "/storage/.config/asgard/transfers.json"   # scrapes waiting, so a restart carries on (CFG-6)
BATTERY = ROOT + "/sys/class/power_supply/battery"
HOME_FIFO = ROOT + "/run/asgard-home.cmd"
SHARE = os.environ.get("ASGARD_SHARE", "/usr/share/asgard")
BATTERY_FLOOR = 15        # % off the charger: a standby suspends here, keeping enough to wake and play
BATTERY_POLL = 60         # s between battery reads, only during a standby
SCRAPE_TIMEOUT = 20 * 60  # Skyscraper reads a ROM whole (~20 s/GB): a 16 GB Switch game takes ~5 min
PAUSED = {"offline": "No internet connection: scraping needs it",
          "battery": "Battery low: scraping carries on once the Thor is on the charger"}
RECENT = 50               # finished jobs kept for status and run


def scrape_cmd(args):
    return ["python3", f"{SHARE}/asgard-scrape.py", *args]


def update_cmd():
    return ["python3", f"{SHARE}/asgard-update.py", "download"]


class System:
    """What the queue does to the Thor. The tests replace it."""

    def __init__(self):
        self.inhibitor = None

    def inhibit(self, on):
        # handle-lid-switch: logind leaves the lid to power-handler, which turns a close into a standby.
        if on and not self.inhibitor:
            self.inhibitor = subprocess.Popen(
                ["systemd-inhibit", "--what=sleep:handle-lid-switch", "--who=Asgard", "--why=downloads and scrapes",
                 "--mode=block", "sleep", "infinity"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif not on and self.inhibitor:
            self.inhibitor.terminate()
            self.inhibitor.wait()
            self.inhibitor = None

    def lid_closed(self):
        r = subprocess.run(["busctl", "get-property", "org.freedesktop.login1", "/org/freedesktop/login1",
                            "org.freedesktop.login1.Manager", "LidClosed"], capture_output=True, text=True)
        return r.stdout.strip() == "b true"

    def battery(self):
        """(percent, on the charger)"""
        try:
            pct = int(open(BATTERY + "/capacity").read())
            status = open(BATTERY + "/status").read().strip()
        except (OSError, ValueError):
            return 100, True
        return pct, status in ("Charging", "Full") or self.cable()

    def cable(self):
        try:
            return open(ROOT + "/sys/class/power_supply/usb/online").read().strip() == "1"
        except OSError:
            return False

    def home(self, cmd):
        """A line to Asgard Home's command FIFO; never blocks when Home isn't reading it."""
        if os.path.exists(HOME_FIFO):
            subprocess.run(["timeout", "1", "sh", "-c", f"echo {cmd} > {HOME_FIFO}"])

    def screens(self, verb):
        subprocess.run([f"{SHARE}/asgard-screens-off.sh", verb])

    def suspend(self):
        subprocess.run(["systemctl", "suspend"])

    def start(self, job):
        cmd = scrape_cmd(job["args"]) if job["kind"] == "scrape" else update_cmd()
        return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)


class Transfers:
    def __init__(self, system=None, queue_file=QUEUE):
        self.sys = system or System()
        self.queue_file = queue_file
        self.lock = threading.Condition()
        self.queue = []          # jobs waiting: {"id", "kind", "args", "label"}
        self.current = None      # the job running
        self.proc = None
        self.recent = []         # finished: the job with its "result"
        self.paused = ""         # "offline", "battery" or "": why the queue doesn't run
        self.holds = {}          # name: monotonic time it ends
        self.standby = False
        self.next_id = 1
        self.batch = {"done": 0, "found": 0, "total": 0}   # scrapes since the queue last had none
        self.busy = False
        self.stopping = False
        self.load()

    # --- the queue ---------------------------------------------------------------------------------------------------

    def load(self):
        try:
            saved = json.load(open(self.queue_file))
        except (OSError, ValueError):
            return
        for job in saved.get("queue", []):
            if job.get("kind") == "scrape" and len(job.get("args", [])) == 3:
                self._push(job["args"])

    def save(self):
        jobs = [j for j in ([self.current] if self.current else []) + self.queue if j["kind"] == "scrape"]
        os.makedirs(os.path.dirname(self.queue_file), exist_ok=True)
        tmp = self.queue_file + ".tmp"
        with open(tmp, "w") as f:
            json.dump({"queue": [{"kind": j["kind"], "args": j["args"]} for j in jobs]}, f)
        os.replace(tmp, self.queue_file)

    def _push(self, args, front=False):
        job = {"id": self.next_id, "kind": "scrape", "args": list(args), "label": os.path.basename(args[2])}
        self.next_id += 1
        if not any(j["kind"] == "scrape" for j in self.queue + ([self.current] if self.current else [])):
            self.batch = {"done": 0, "found": 0, "total": 0}
        self.batch["total"] += 1
        self.queue.insert(self._front() if front else len(self.queue), job)
        return job

    def _front(self):
        """Where a job that goes first is put: behind an update waiting, which always goes first."""
        return sum(1 for j in self.queue[:1] if j["kind"] == "update")

    def add_scrapes(self, games, front=False):
        with self.lock:
            queued = {tuple(j["args"]) for j in self.queue}
            if self.current and self.current["kind"] == "scrape":
                queued.add(tuple(self.current["args"]))
            added = []
            for g in games:
                if tuple(g) not in queued:
                    queued.add(tuple(g))
                    added.append(self._push(g, front))
            if added:
                self.paused = ""   # the user asked for more: try again
            self.save()
            self.changed()
            return added

    def add_update(self):
        with self.lock:
            if not any(j["kind"] == "update" for j in self.queue + ([self.current] if self.current else [])):
                self.queue.insert(0, {"id": self.next_id, "kind": "update", "args": [], "label": "Asgard update"})
                self.next_id += 1
            self.paused = ""
            self.changed()
            return [j for j in self.queue if j["kind"] == "update"]

    def cancel(self, what):
        with self.lock:
            hit = lambda j: what == "all" or what == j["kind"] or str(j["id"]) == str(what)
            dropped = [j for j in self.queue if hit(j)]
            self.queue = [j for j in self.queue if not hit(j)]
            if self.current and hit(self.current) and self.proc:
                self.current["cancelled"] = True
                self.proc.terminate()
                dropped.append(self.current)
            for j in dropped:
                if j["kind"] == "scrape":
                    self.batch["total"] -= 1
            self.save()
            self.changed()
            return len(dropped)

    def resume(self, auto=False):
        with self.lock:
            if auto and self.paused == "battery":
                pct, charging = self.sys.battery()
                if not charging and pct <= BATTERY_FLOOR + 5:
                    return False   # woke on the same low battery: stay paused
            was = bool(self.paused)
            self.paused = ""
            self.changed()
            return was

    def hold(self, name, seconds):
        with self.lock:
            if seconds > 0:
                self.holds[name] = time.monotonic() + min(seconds, 600)
            else:
                self.holds.pop(name, None)
            self.changed()

    def finished(self, job, result):
        """The job ended: note it, and pause on no internet (the job goes back first, it wasn't done)."""
        job = dict(job, result=result)
        if job.pop("cancelled", False):
            job["result"] = {"error": "Cancelled"}
        elif job["kind"] == "scrape" and str(result.get("error", "")).startswith("No internet"):
            self.queue.insert(self._front(), {k: v for k, v in job.items() if k != "result"})
            self.paused = "offline"
            return
        if job["kind"] == "scrape":
            self.batch["done"] += 1
            self.batch["found"] += 0 if result.get("error") else 1
        self.recent = (self.recent + [job])[-RECENT:]

    # --- busy, standby and sleep -------------------------------------------------------------------------------------

    def _holding(self):
        now = time.monotonic()
        self.holds = {n: t for n, t in self.holds.items() if t > now}
        return bool(self.holds)

    def is_busy(self):
        return bool(self.current) or (bool(self.queue) and not self.paused) or self._holding()

    def changed(self):
        """After anything that may change busy (the lock held): the inhibitor, the flag, and a standby that's done."""
        busy = self.is_busy()
        became_busy, became_idle = busy and not self.busy, self.busy and not busy
        if busy != self.busy:
            self.busy = busy
            self.sys.inhibit(busy)
            if busy:
                open(BUSY, "w").close()
            elif os.path.exists(BUSY):
                os.remove(BUSY)
        if not busy and self.standby:
            self.finish_standby()
        elif became_idle and self.sys.lid_closed():
            self.sys.suspend()     # done with the lid shut and no standby (it was ended, or never began): logind's held off
        elif became_busy and not self.standby and self.sys.lid_closed():
            self.enter_standby()   # busy again with the lid shut (a wake on the charger, an upload): don't stay up lit
        self.lock.notify_all()

    def sleep(self):
        """Sleep as asked: suspend now if nothing's left, else a standby until it's done."""
        with self.lock:
            if not self.is_busy():
                self.sys.suspend()
                return "suspend"
            self.enter_standby()
            return "standby"

    def enter_standby(self):
        if self.standby:
            return
        self.standby = True
        open(STANDBY, "w").close()
        self.sys.home("standby")       # pause the game (Home's own pause or a freeze)
        self.sys.screens("standby")    # screens, touch, lights and the big cores off; Wi-Fi stays on
        self.lock.notify_all()         # the worker starts watching the battery

    def leave_standby(self, dark=False):
        if not self.standby:
            return
        self.standby = False
        self.sys.screens("standby-dark" if dark else "standby-end")
        if os.path.exists(STANDBY):
            os.remove(STANDBY)

    def finish_standby(self):
        """The work's done (or the battery's low): suspend, as the sleep that was asked for. The screens come back on
        dark so a resume finds them on (power-handler's release), and Home keeps the game paused: the sleep's own wake
        continues it."""
        self.leave_standby(dark=True)
        self.sys.suspend()

    def wake(self):
        """The lid opened or the power key: the user's back, the work carries on with the Thor awake."""
        with self.lock:
            if not self.standby:
                return False
            self.leave_standby()
            self.sys.home("standby-end")
            return True

    def check_battery(self):
        if not self.standby:
            return
        pct, charging = self.sys.battery()
        if pct <= BATTERY_FLOOR and not charging:
            self.paused = "battery"   # the job running finishes; nothing new starts
            if self.proc and self.current:
                self.current["cancelled"] = True
                self.queue.insert(self._front(), {k: v for k, v in self.current.items() if k != "cancelled"})
                self.proc.terminate()
            self.changed()

    # --- the worker --------------------------------------------------------------------------------------------------

    def wait_time(self):
        """How long the worker may sleep: forever when idle (PWR-9); until a hold ends; the battery poll in standby."""
        times = [t - time.monotonic() for t in self.holds.values()]
        if self.standby:
            times.append(BATTERY_POLL)
        return max(0.05, min(times)) if times else None

    def step(self):
        """Start the next job if one may run, else wait for a change. Returns the job started, or None."""
        with self.lock:
            self.check_battery()
            if self.current or not self.queue or self.paused:
                self.lock.wait(self.wait_time())
                self.changed()   # a hold may have run out
                return None
            self.current = self.queue.pop(0)
            self.proc = self.sys.start(self.current)
            return self.current

    def collect(self, job):
        """Wait for the job started by step(), then record it."""
        deadline = time.monotonic() + SCRAPE_TIMEOUT if job["kind"] == "scrape" else None
        while True:
            # A standby may begin while the job runs, so the battery is checked meanwhile too (an update download can
            # take a while). A job running means the Thor's awake, so this wakes nothing (PWR-9).
            waits = [BATTERY_POLL] + ([deadline - time.monotonic()] if deadline else [])
            try:
                out, _ = self.proc.communicate(timeout=max(0, min(waits)))
                break
            except subprocess.TimeoutExpired:
                if deadline and time.monotonic() >= deadline:
                    self.proc.kill()
                    self.proc.communicate()
                    out = json.dumps({"error": "The scraper took too long"})
                    break
                with self.lock:
                    self.check_battery()
        if job["kind"] == "scrape":
            try:
                result = json.loads((out or "").strip().splitlines()[-1])
            except (ValueError, IndexError):
                result = {"error": "The scraper failed"}
        else:
            result = {"rc": self.proc.returncode}
        with self.lock:
            self.current, self.proc = None, None
            self.finished(job, result)
            self.save()
            # Home shows the art as it comes: a rescan every 10 games, and after the last one.
            left = any(j["kind"] == "scrape" for j in self.queue)
            if job["kind"] == "scrape" and self.batch["found"] and (self.batch["done"] % 10 == 0 or not left):
                self.sys.home("rescan")
            self.changed()

    def worker(self):
        while not self.stopping:
            job = self.step()
            if job:
                self.collect(job)

    def wait_for(self, job_id):
        with self.lock:
            while True:
                for j in self.recent:
                    if j["id"] == job_id:
                        return j["result"]
                if not any(j["id"] == job_id for j in self.queue + ([self.current] if self.current else [])):
                    return {"error": "Stopped"}
                if self.paused and not (self.current and self.current["id"] == job_id):
                    return {"error": PAUSED[self.paused]}
                self.lock.wait()

    def status(self):
        with self.lock:
            self._holding()
            return {"busy": self.is_busy(), "paused": self.paused, "standby": self.standby,
                    "current": self.current and {k: self.current[k] for k in ("id", "kind", "label", "args")},
                    "queue": [{k: j[k] for k in ("id", "kind", "label", "args")} for j in self.queue],
                    "scrape": dict(self.batch), "holds": sorted(self.holds),
                    "recent": [{k: j[k] for k in ("id", "kind", "label", "args", "result")} for j in self.recent[-10:]]}

    # --- requests ----------------------------------------------------------------------------------------------------

    def handle(self, req):
        cmd, args = req.get("cmd"), req.get("args", [])
        if cmd == "add" and args[:1] == ["scrape"] and len(args) > 1 and (len(args) - 1) % 3 == 0:
            games = [args[i:i + 3] for i in range(1, len(args), 3)]
            return {"added": [j["id"] for j in self.add_scrapes(games)]}
        if cmd == "add" and args == ["update"]:
            return {"added": [j["id"] for j in self.add_update()]}
        if cmd == "run" and args[:1] == ["scrape"] and len(args) == 4:
            added = self.add_scrapes([args[1:]], front=True)
            if not added:   # already queued: wait for that one
                with self.lock:
                    added = [j for j in self.queue + ([self.current] if self.current else []) if j["args"] == args[1:]]
            with self.lock:
                if self.paused:
                    self.paused = ""
                    self.changed()
            return self.wait_for(added[0]["id"])
        if cmd == "status":
            return self.status()
        if cmd == "cancel" and len(args) == 1:
            return {"cancelled": self.cancel(args[0])}
        if cmd == "resume":
            return {"resumed": self.resume(auto=args == ["auto"])}
        if cmd == "hold" and len(args) == 2:
            self.hold(args[0], float(args[1]))
            return {"ok": True}
        if cmd == "sleep":
            return {"did": self.sleep()}
        if cmd == "wake":
            return {"woke": self.wake()}
        return {"error": "unknown request"}


def serve():
    t = Transfers()
    for f in (BUSY, STANDBY):   # left by a service that died: it didn't hold anything across a restart
        if os.path.exists(f):
            os.remove(f)
    with t.lock:
        t.changed()
    threading.Thread(target=t.worker, daemon=True).start()
    if os.path.exists(SOCK):
        os.remove(SOCK)
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(SOCK)
    os.chmod(SOCK, 0o600)
    srv.listen(16)

    def client(conn):
        with conn:
            try:
                req = json.loads(conn.makefile().readline())
                conn.sendall((json.dumps(t.handle(req)) + "\n").encode())
            except (ValueError, OSError, TypeError, IndexError) as e:
                try:
                    conn.sendall((json.dumps({"error": str(e)}) + "\n").encode())
                except OSError:
                    pass
    while True:
        conn, _ = srv.accept()
        threading.Thread(target=client, args=(conn,), daemon=True).start()


def request(cmd, args, timeout=None):
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(timeout)
    s.connect(SOCK)
    with s:
        s.sendall((json.dumps({"cmd": cmd, "args": args}) + "\n").encode())
        return json.loads(s.makefile().readline())


def main(argv):
    if argv[1:] == ["serve"]:
        serve()
        return 0
    if len(argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    cmd, args = argv[1], argv[2:]
    if cmd == "woke":
        cmd, args = "resume", ["auto"]
    try:
        out = request(cmd, args, timeout=None if cmd == "run" else 10)
    except OSError:
        # No service (stopped, crashed, an older image): sleep must still sleep, and a scrape still scrape.
        if cmd == "sleep":
            subprocess.run(["systemctl", "suspend"])
            out = {"did": "suspend"}
        elif cmd == "run" and args[:1] == ["scrape"] and len(args) == 4:
            r = subprocess.run(scrape_cmd(args[1:]), capture_output=True, text=True)
            print(r.stdout.strip() or json.dumps({"error": "The scraper failed"}))
            return 0
        elif cmd == "status":
            out = {"busy": False, "paused": "", "standby": False, "current": None, "queue": [], "error": "not running"}
        else:
            print(json.dumps({"error": "asgard-transfers isn't running"}))
            return 1
    print(json.dumps(out))
    return 0 if "error" not in out or cmd == "run" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
