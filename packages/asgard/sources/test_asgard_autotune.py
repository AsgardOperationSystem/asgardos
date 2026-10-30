#!/usr/bin/env python3
# python3 test_asgard_autotune.py: the autotune controller against simulated games, trans_stat parsing (offline).
import importlib.util, os

spec = importlib.util.spec_from_file_location("at", os.path.join(os.path.dirname(os.path.abspath(__file__)), "asgard-autotune.py"))
at = importlib.util.module_from_spec(spec)
spec.loader.exec_module(at)

MID = [307200, 614400, 902400, 1209600, 1516800, 1824000, 2131200, 2438400, 2803200]
GPU = [220, 295, 348, 401, 475, 550, 615, 680]


def setup(gpu=True):
    mid = at.Domain("mid", MID, lambda v: None, MID[-1] * at.FLOOR)
    gpu = at.Domain("gpu", GPU, lambda v: None, 348, at.GPU_GAP)
    return mid, gpu, at.Tuner([mid, gpu])


def run(tuner, fps_of, seconds, target=60, t=0):
    for s in range(t, t + seconds):
        tuner.step(float(s), fps_of(), target)
    return t + seconds


# Light game: holds 60 whatever the clocks: both go down to their floors (mid 25 % = 902400, GPU 348).
mid, gpu, t = setup()
run(t, lambda: 60, 400)
assert (mid.steps[mid.i], gpu.steps[gpu.i]) == (902400, 348), (mid.steps[mid.i], gpu.steps[gpu.i])

# Needs mid >= 1824000 and GPU >= 475 for 60 (52 under): settles there, and never stays below for long.
mid, gpu, t = setup()
fps = lambda: 60 if MID[mid.i] >= 1824000 and GPU[gpu.i] >= 475 else 52
short, s = 0, 0
for s in range(600):
    f = fps()
    short += f < 58
    t.step(float(s), f, 60)
assert (MID[mid.i], GPU[gpu.i]) == (1824000, 475), (MID[mid.i], GPU[gpu.i])
assert short < 12, short   # a lost second per failed probe, BACKOFF doubling per domain

# Short of target with headroom left: the busiest domain goes up 2 steps after 2 short samples.
mid, gpu, t = setup()
mid.i, gpu.i, mid.busy, gpu.busy = 3, 3, 0.4, 0.95
run(t, lambda: 45, 2)
assert (mid.i, gpu.i) == (3, 5), (mid.i, gpu.i)

# A 30 fps game on a 60 Hz screen: learns the plateau at full clocks, then lowers.
mid, gpu, t = setup()
n = run(t, lambda: 30, 7)
assert t.plateau == 30, t.plateau
run(t, lambda: 30, 40, t=n)
assert mid.i < len(MID) - 1 or gpu.i < len(GPU) - 1
# ...and forgets it when the game runs faster again.
t.step(100.0, 60, 60)
assert t.plateau is None

# Paused / screens off: nothing moves.
mid, gpu, t = setup()
run(t, lambda: None, 50)
run(t, lambda: 2, 50, t=50)
assert mid.top() and gpu.top()

# GPU changes keep GPU_GAP apart.
mid, gpu, t = setup()
gpu.set(5, 0.0)
assert not gpu.ready(at.GPU_GAP - 1) and gpu.ready(at.GPU_GAP)

ts = """     From  :   To
           : 220000000 295000000   time(ms)
*  220000000:         0         5      1200
   295000000:         5         0       300
Total transition : 10
"""
assert at.gpu_times(ts) == {220000000: 1200, 295000000: 300}, at.gpu_times(ts)
print("ok")
