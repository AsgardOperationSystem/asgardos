#!/usr/bin/env python3
"""python3 test_thor_touchcal.py: the touch calibration maths (fit + compose), no SDL needed."""
from thor_touchcal import DEFAULT, TARGETS, compose, fit_affine


def apply(m, p):
    return (m[0] * p[0] + m[1] * p[1] + m[2], m[3] * p[0] + m[4] * p[1] + m[5])


# Taps off by a known scale + offset: the fit undoes it exactly.
skew = [1.05, 0.0, -0.03, 0.02, 0.97, 0.04]
fix, rms = fit_affine([apply(skew, t) for t in TARGETS], TARGETS)
assert rms < 1e-9, rms
for t in TARGETS:
    assert all(abs(a - b) < 1e-9 for a, b in zip(apply(fix, apply(skew, t)), t))
# Composing into the rotation: raw point -> (old matrix, then the fix) == raw point -> new matrix.
raw = (0.3, 0.7)
new = compose(fix, DEFAULT)
assert all(abs(a - b) < 1e-9 for a, b in zip(apply(new, raw), apply(fix, apply(DEFAULT, raw))))
# One wild tap shows up as a large RMS (rejected by MAX_RMS).
taps = list(TARGETS)
taps[2] = (0.2, 0.3)
assert fit_affine(taps, TARGETS)[1] > 0.04
print("ok")
