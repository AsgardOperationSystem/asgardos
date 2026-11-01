#!/usr/bin/env python3
# spec: CFG-13
# gap: parse_yaml takes the inline wifi: {ssid: x} that CFG-13 writes as a plain value, so system.cfg gets wifi={ssid: x}
"""CFG-13's own example, written in the yml as SPEC writes it. The block form passes in test_asgard_yml.py."""
import importlib.util
import os

spec = importlib.util.spec_from_file_location("asgard_config", os.path.join(os.path.dirname(os.path.abspath(__file__)), "asgard_config.py"))
config = importlib.util.module_from_spec(spec)
spec.loader.exec_module(config)
got = config.flatten(config.parse_yaml("wifi: {ssid: x}\n"))
assert got == {"wifi.ssid": "x"}, got
