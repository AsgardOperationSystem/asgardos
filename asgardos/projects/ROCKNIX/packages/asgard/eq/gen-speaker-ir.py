#!/usr/bin/env python3
# Development tool (desktop, numpy): Joey's Retro Handhelds JamesDSP speaker GraphicEQ for the AYN Thor (as shipped
# by ThorTune / AYN-Thor-Tweaks) -> a 48 kHz minimum-phase FIR for PipeWire's convolver, with JamesDSP's +15 dB
# output gain baked in (the limiter after it, asgard-limiter, keeps that from clipping).
#   python3 gen-speaker-ir.py joey-speaker.wav
import struct, sys
import numpy as np

NODES = [(70, -32), (110, -4.5), (120, -4), (200, -4), (300, -5), (444, -9), (600, -13.5), (700, -17), (850, -17),
         (1200, -18.5), (1860, -20), (2800, -19.5), (3800, -21.5), (5000, -13), (7000, -6), (9050, -0.5),
         (11000, 0.5), (12000, -0.5), (16000, -3)]
POSTGAIN = 15.0
RATE, NFFT, TAPS, FADE = 48000, 1 << 16, 4096, 512


def target_db(f):
    """GraphicEQ (Equalizer APO style): dB linear in log-frequency between nodes, flat past the ends."""
    lf = np.log10(np.maximum(f, 1.0))
    return np.interp(lf, np.log10([n[0] for n in NODES]), [n[1] for n in NODES]) + POSTGAIN


f = np.arange(NFFT // 2 + 1) * RATE / NFFT
mag = 10 ** (target_db(f) / 20)
# Minimum phase from the real cepstrum: fold the anticausal half onto the causal one.
cep = np.fft.irfft(np.log(mag), NFFT)
fold = np.zeros(NFFT)
fold[0], fold[NFFT // 2] = cep[0], cep[NFFT // 2]
fold[1:NFFT // 2] = 2 * cep[1:NFFT // 2]
h = np.fft.irfft(np.exp(np.fft.rfft(fold)), NFFT)[:TAPS]
h[-FADE:] *= np.cos(np.linspace(0, np.pi / 2, FADE)) ** 2

# Check: the truncated filter against the target, 60 Hz..18 kHz.
H = 20 * np.log10(np.abs(np.fft.rfft(h, NFFT)) + 1e-12)
band = (f > 60) & (f < 18000)
err = np.abs(H[band] - target_db(f[band]))
print(f"taps {TAPS}, peak {np.abs(h).max():.3f}, error max {err.max():.2f} dB, 95% {np.percentile(err, 95):.2f} dB")
assert np.percentile(err, 95) < 1.0, "FIR too short for this curve"

data = h.astype("<f4").tobytes()
with open(sys.argv[1], "wb") as w:   # 32-bit float WAV (format 3), mono
    w.write(b"RIFF" + struct.pack("<I", 36 + len(data)) + b"WAVEfmt " +
            struct.pack("<IHHIIHH", 16, 3, 1, RATE, RATE * 4, 4, 32) + b"data" + struct.pack("<I", len(data)) + data)
