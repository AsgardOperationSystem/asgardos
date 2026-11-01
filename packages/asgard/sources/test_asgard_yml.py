#!/usr/bin/env python3
# spec: CFG-2 CFG-13
"""asgard_config.py's main(): which yml it reads, and what nesting becomes in system.cfg. Block mappings and a dotted,
quoted key here; the inline form SPEC's CFG-13 writes is test_asgard_yml_inline.py. Precedence and the SSH keys are its
own --test (CFG-1, CFG-3)."""
import contextlib
import importlib.util
import io
import os
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("asgard_config", os.path.join(HERE, "asgard_config.py"))
config = importlib.util.module_from_spec(spec)
spec.loader.exec_module(config)

# CFG-2: the real paths, in this order.
assert config.SOURCES == ["/flash/asgard.yml", "/storage/.config/asgard/asgard.yml"], config.SOURCES


def boot(flash, storage):
    """main() in a temp root with these yml files (None: absent): what system.cfg ends up with."""
    with tempfile.TemporaryDirectory() as d:
        config.SOURCES = [f"{d}/flash.yml", f"{d}/storage.yml"]
        config.APPLIED, config.SYS_CFG = f"{d}/applied.json", f"{d}/user/system.cfg"
        config.SYS_DEFAULT, config.AUTH_KEYS = f"{d}/default.cfg", f"{d}/ssh/authorized_keys"
        with open(config.SYS_DEFAULT, "w") as f:
            f.write("wifi.enabled=0\n")
        for path, text in zip(config.SOURCES, (flash, storage)):
            if text is not None:
                with open(path, "w") as f:
                    f.write(text)
        with contextlib.redirect_stdout(io.StringIO()):
            config.main()
        return config.read_cfg(config.SYS_CFG)


FLASH = "wifi:\n  ssid: from-flash\nonly:\n  flash: 1\n"
STORAGE = "wifi:\n  ssid: from-storage\nonly:\n  storage: 1\n"
# CFG-2: /flash wins, and the other file's keys don't come along.
cfg = boot(FLASH, STORAGE)
assert cfg["wifi.ssid"] == "from-flash" and cfg["only.flash"] == "1" and "only.storage" not in cfg, cfg
# The other file is the fallback.
cfg = boot(None, STORAGE)
assert cfg["wifi.ssid"] == "from-storage" and cfg["only.storage"] == "1", cfg
assert boot(None, None) == {}
# A broken first file is still the first found: it doesn't fall through to the other one.
cfg = boot("wifi:\n\tssid: tab\n", STORAGE)
assert "only.storage" not in cfg, cfg

# CFG-13: nesting flattens with dots, and a key with a value and children is written dotted and quoted.
cfg = boot("""
wifi:
  ssid: x
  nested:
    deeper: y
"global.retroachievements": 1
global:
  retroachievements:
    username: me
""", None)
assert cfg["wifi.ssid"] == "x" and cfg["wifi.nested.deeper"] == "y", cfg
assert cfg["global.retroachievements"] == "1" and cfg["global.retroachievements.username"] == "me", cfg
assert "wifi" not in cfg and "global" not in cfg, cfg
print("asgard yml: ok")
