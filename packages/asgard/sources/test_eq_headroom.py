#!/usr/bin/env python3
# spec: AUD-2
"""Every EQ chain, shipped (50-thor-dsp.conf) or generated (each profile, with tone), ends in the limiter, so no preset's
boost, nor bass, mid and treble on top of it, can clip. The Thor headphone preset's +4 dB shelf used to outrun its mixer's
-2.7 dB with no limiter in its chain."""
import importlib.util
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("eq", os.path.join(HERE, "asgard-eq.py"))
eq = importlib.util.module_from_spec(spec)
spec.loader.exec_module(eq)

PEQ = "Preamp: -3 dB\nFilter 1: ON PK Fc 100 Hz Gain 3 dB Q 1\n"
CONFS = {"shipped": open(os.path.join(HERE, "../pipewire/50-thor-dsp.conf")).read()}
for name, st in {"joey": {"speaker": "joey"}, "off": {"speaker": "off", "headphones": "off"},
                 "autoeq": {"headphones": "autoeq", "headphones_name": "X", "peq": PEQ},
                 "tone": {"tone": {"speaker": [6, 6, 6], "headphones": [6, 6, 6]}}}.items():
    CONFS[name] = eq.conf_text(st)
for name, text in CONFS.items():
    chains = text.split("libpipewire-module-filter-chain")[1:]
    assert chains, name
    for chain in chains:
        desc = re.search(r'node\.description = "([^"]*)"', chain).group(1)
        assert 'outputs = [ "lim:Out L" "lim:Out R" ]' in chain and "asgard-limiter.so" in chain, f"{name}: {desc} has no limiter"
print("ok")
