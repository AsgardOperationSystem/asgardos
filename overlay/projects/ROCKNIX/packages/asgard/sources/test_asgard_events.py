"""asgard-events.py: lines reach the log, a burst is one fsync, a quiet tick syncs its tail, the log rotates."""
import importlib.util
import os
import tempfile
from unittest import mock

spec = importlib.util.spec_from_file_location("events", os.path.join(os.path.dirname(__file__), "asgard-events.py"))
events = importlib.util.module_from_spec(spec)
spec.loader.exec_module(events)


def test_burst_then_quiet():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "logs", "events.log")
        clock = iter([100.0] + [100.5] * 50 + [103.0] * 10)
        with mock.patch.object(events.os, "fsync") as fsync, mock.patch.object(events.time, "monotonic", lambda: next(clock)):
            # a burst of 3 lines inside one sync window, then a quiet tick past it
            events.follow(iter(["a\n", "b\n", "c\n", ""]), path, sync_secs=2)
        assert open(path).read() == "a\nb\nc\n"
        assert fsync.call_count == 2, fsync.call_count   # first line, then the burst's tail on the quiet tick


def test_rotation():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "events.log")
        with mock.patch.object(events, "MAX_BYTES", 10):
            events.follow(iter(["0123456789AB\n", "next\n"]), path, sync_secs=0)
        assert open(path + ".1").read() == "0123456789AB\n"
        assert open(path).read() == "next\n"


def test_chunks():
    r, w = os.pipe()
    os.write(w, "kernel: é\n".encode()[:9])   # split inside the é
    gen = events.journal_chunks(r, sync_secs=0.05)
    first = next(gen)
    os.write(w, "kernel: é\n".encode()[9:])
    os.close(w)
    rest = "".join(gen)
    assert first + rest == "kernel: é\n", (first, rest)


if __name__ == "__main__":
    for t in (test_burst_then_quiet, test_rotation, test_chunks):
        t()
    print("ok")
