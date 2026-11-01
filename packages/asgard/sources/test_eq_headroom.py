#!/usr/bin/env python3
# spec: AUD-2
# gap: the Thor headphone preset's +4 dB shelf outruns its mixer's -2.7 dB, with no limiter in the chain
"""A shipped preset's largest boost plus its output gain stays at or under 0 dB, or the chain has the limiter. The largest
single filter, not the sum of neighbours: a floor, not a measurement. The speaker's passes at exactly 0."""
import math
import os
import re

CONF = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../pipewire/50-thor-dsp.conf")).read()
for chain in CONF.split("libpipewire-module-filter-chain")[1:]:
    name = re.search(r'node\.description = "([^"]*)"', chain).group(1)
    boost = max(float(g) for g in re.findall(r'"Gain" = (-?[\d.]+)', chain))
    mix = re.search(r'name = \w*L label = mixer control = \{ "Gain 1" = ([\d.]+)(?: "Gain 2" = (-?[\d.]+))? \}', chain)
    output = abs(float(mix.group(1))) + abs(float(mix.group(2) or 0))
    net = boost + 20 * math.log10(output)
    assert net <= 0.01 or "limiter" in chain, f"{name}: {net:+.2f} dB"
