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


def journal_chunks(fd, sync_secs=SYNC_SECS):
    """What journalctl writes to fd, as it comes (raw reads: a buffered reader could sit on lines select() no longer
    sees), plus "" after sync_secs of quiet so follow() syncs a burst's tail."""
    decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
    while True:
        if not select.select([fd], [], [], sync_secs)[0]:
            yield ""
            continue
        data = os.read(fd, 65536)
        if not data:
            return
        yield decoder.decode(data)


def main():
    boot = open("/proc/sys/kernel/random/boot_id").read().strip()
    # -b: this boot from its start (the boot's own warnings), then follow. Priority 4 = warning and worse.
    proc = subprocess.Popen(["journalctl", "-b", "-f", "-p", "warning", "-o", "short-iso", "--no-pager"],
                            stdout=subprocess.PIPE)
    header = f"=== boot {boot} {time.strftime('%Y-%m-%d %H:%M:%S')} ===\n"
    follow(itertools.chain([header], journal_chunks(proc.stdout.fileno())))


if __name__ == "__main__":
    main()
