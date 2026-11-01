#!/usr/bin/env python3
# spec: PORT-3 GPU-1 GPU-2 EMU-4 EMU-5
# requires: file:build/AsgardOS-SM8550.aarch64/image/system/usr/bin/runemu.sh
# Image check over the last build's tree (which can be older than the source): what these rules need really landed. PORT-3 the linker
# finds libtheoradec for LÖVE ports (that Gen1 Recomp runs under XWayland: human). GPU-2's Turnip with a library its icd.json can reach,
# and GPU-1's Mesa version for the unset row. EMU-4 the defaults' start_<name>.sh in /usr/bin, EMU-5 the catalogue with no EmulationStation.
import json
import os
import xml.etree.ElementTree as ET

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../.."))
IMAGE = f"{REPO}/build/AsgardOS-SM8550.aarch64/image/system"

# PORT-3
link = f"{IMAGE}/usr/lib/libtheoradec.so.1"
assert os.path.islink(link) and os.path.isfile(os.path.join(os.path.dirname(link), os.readlink(link))), link

# GPU-2, GPU-1
with open(f"{IMAGE}/usr/lib/gpu-drivers/mesa-25.3.6/icd.json") as f:
    library = json.load(f)["ICD"]["library_path"]
assert library == "/usr/lib/gpu-drivers/mesa-25.3.6/libvulkan_freedreno.so" and os.path.isfile(IMAGE + library), library
with open(f"{IMAGE}/usr/share/mesa/version") as f:
    assert f.read().startswith("mesa-")

# EMU-5
catalogue = ET.parse(f"{IMAGE}/usr/share/asgard/es_features.cfg").getroot()
assert catalogue.findall("emulator")
assert not os.path.exists(f"{IMAGE}/usr/bin/emulationstation")

# EMU-4: runemu.sh runs /usr/bin/start_<core minus -sa>.sh, for the defaults that are standalone.
for name in ("azahar", "eden", "melonds", "armsx2", "ppsspp", "flycast", "cemu", "rpcs3", "vita3k", "xemu"):
    assert os.path.isfile(f"{IMAGE}/usr/bin/start_{name}.sh"), name
print("ok")
