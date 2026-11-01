# spec: OLED-2
# requires: file:packages/linux/src/drivers/gpu/drm/panel/panel-chipone-icna35xx.c cmd:python3
"""Run: python -I test_ultra_black_driver.py  (no Thor): OLED-2's "sent at each panel power-on": the kernel's panel driver reads the
parameter while it brings the panel up. Its own file, because the kernel submodule may not be checked out."""
import os
import re

DRIVER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../linux/src/drivers/gpu/drm/panel/panel-chipone-icna35xx.c")
text = open(DRIVER).read()
assert "module_param(ultra_black, bool, 0644);" in text
init = re.search(r"^static int icna3520_init_sequence\(.*?^}", text, re.M | re.S).group(0)
assert re.search(r"if \(ultra_black\) \{", init)
prepare = re.search(r"^static int icna35xx_prepare\(.*?^}", text, re.M | re.S).group(0)
assert "init_sequence" in prepare
print("ok")
