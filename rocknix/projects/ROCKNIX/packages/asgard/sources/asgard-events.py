"""Event log: the journal's warnings and errors (kernel included) appended to /storage as they happen, so the run-up
to a freeze survives it while the journal itself stays in RAM. Writes only when something is logged, synced at most
every SYNC_SECS (a burst is one write), rotated to events.log.1 past MAX_BYTES.
Usage: asgard-events.py [log path]   (asgard-events.service)
"""
import codecs
import itertools
import os
import select
import subprocess
import sys
import time

LOG = sys.argv[1] if len(sys.argv) > 1 else "/storage/.config/thor/logs/events.log"
MAX_BYTES = 2 * 1024 * 1024
SYNC_SECS = 2


def open_log(path=None):
    path = path or LOG
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path) and os.path.getsize(path) > MAX_BYTES:
        os.replace(path, path + ".1")
    return open(path, "a", buffering=1)


def follow(lines, path=None, sync_secs=SYNC_SECS):
    """Copies lines (text; "" is a quiet tick, each next() may block) to the log, fsyncing pending lines at
    most every sync_secs and rotating it once it grows past MAX_BYTES. Returns when lines ends."""
    log = open_log(path)
    last_sync, pending = 0.0, False
    for line in lines:
        if line:
            log.write(line)
            pending = True
        if pending and time.monotonic() - last_sync >= sync_secs:
            os.fsync(log.fileno())
            last_sync, pending = time.monotonic(), False
            if log.tell() > MAX_BYTES:
                log.close()
                log = open_log(path)
    if pending:
        os.fsync(log.fileno())
    log.close()


def journal_chunks(*fds, sync_secs=SYNC_SECS):
    """What the journalctl processes write to fds, as it comes (raw reads: a buffered reader could sit on lines
    select() no longer sees), in whole lines so two streams never interleave mid-line, plus "" after sync_secs of
    quiet so follow() syncs a burst's tail. Ends when every fd is closed."""
    pending = {fd: ["", codecs.getincrementaldecoder("utf-8")(errors="replace")] for fd in fds}
    while pending:
        ready = select.select(list(pending), [], [], sync_secs)[0]
        if not ready:
            yield ""
            continue
        for fd in ready:
            data = os.read(fd, 65536)
            if not data:
                tail = pending.pop(fd)[0]
                if tail:
                    yield tail
                continue
            head, sep, pending[fd][0] = (pending[fd][0] + pending[fd][1].decode(data)).rpartition("\n")
            if sep:
                yield head + sep


# Info-level events the warnings miss, for "what happened before it went wrong": radios (rfkill, airplane mode,
# NetworkManager's Wi-Fi and connection states) and sleep (the kernel's suspend entry/exit).
INFO_EVENTS = r"rfkill|[Rr]adio|airplane|NetworkManager state is now|\(wlan0\): state change|PM: suspend (entry|exit)"


def main():
    boot = open("/proc/sys/kernel/random/boot_id").read().strip()
    # -b: this boot from its start (the boot's own warnings), then follow. Priority 4 = warning and worse; the
    # second stream takes INFO_EVENTS from the priorities below it, so no line is logged twice.
    # -n all: -f alone starts from the last 10 entries, not the boot's start.
    common = ["journalctl", "-b", "-f", "-n", "all", "-o", "short-iso", "--no-pager"]
    warnings = subprocess.Popen(common + ["-p", "warning"], stdout=subprocess.PIPE)
    info = subprocess.Popen(common + ["-p", "notice..debug", "-g", INFO_EVENTS], stdout=subprocess.PIPE)
    header = f"=== boot {boot} {time.strftime('%Y-%m-%d %H:%M:%S')} ===\n"
    follow(itertools.chain([header], journal_chunks(warnings.stdout.fileno(), info.stdout.fileno())))


if __name__ == "__main__":
    main()
