"""Asgard UI sounds, synthesized (no samples, no licences): python3 gensounds.py <outdir>"""
import math, struct, sys, wave
RATE = 48000

def tone(parts, dur):
    """parts: [(start_s, freq_hz, length_s, gain)] sine blips with a quick attack and exponential decay."""
    n = int(dur * RATE); out = [0.0] * n
    for start, f, length, g in parts:
        s0 = int(start * RATE)
        for i in range(int(length * RATE)):
            if s0 + i >= n: break
            t = i / RATE
            env = min(1.0, t / 0.003) * math.exp(-t / (length / 4))
            # a touch of the octave above makes it glassy rather than beepy
            out[s0 + i] += g * env * (math.sin(2 * math.pi * f * t) + 0.25 * math.sin(4 * math.pi * f * t))
    return out

def save(path, samples):
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(RATE)
        w.writeframes(b"".join(struct.pack("<h", int(max(-1, min(1, s)) * 32767)) for s in samples))

d = sys.argv[1]
save(f"{d}/move.wav",   tone([(0, 1760, 0.035, 0.22)], 0.05))
save(f"{d}/select.wav", tone([(0, 1318.5, 0.06, 0.3), (0.045, 1975.5, 0.09, 0.3)], 0.15))
save(f"{d}/back.wav",   tone([(0, 1318.5, 0.06, 0.3), (0.045, 880, 0.09, 0.3)], 0.15))
save(f"{d}/open.wav",   tone([(0, 1046.5, 0.12, 0.22), (0.05, 1568, 0.14, 0.22), (0.1, 2093, 0.2, 0.2)], 0.32))
save(f"{d}/toggle.wav", tone([(0, 2349, 0.04, 0.25), (0.03, 2349, 0.04, 0.2)], 0.08))
