#!/usr/bin/env python3
# spec: KERN-1
# requires: file:packages/linux/src/Makefile
# gap: no Thor device tree has an SY7758 node (only the Ayaneo Pocket trees): the driver is built, but nothing on a Thor binds it, though KERN-1 names it.
import os
import re

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
DTS = os.path.join(ROOT, "packages/linux/src/arch/arm64/boot/dts/qcom")
text = "".join(open(os.path.join(DTS, f)).read() for f in ("qcs8550-ayn-thor.dts", "qcs8550-ayn-common.dtsi"))
assert re.search(r'compatible = "silergy,sy7758"', text), "the Thor's device tree doesn't use the SY7758"
print("ok")
