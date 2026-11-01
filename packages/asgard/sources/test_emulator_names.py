#!/usr/bin/env python3
# spec: EMU-3
# gap: dolphin-sa, heroic, hypseus-singe, mupen64plus-sa and openbor name or place their start script differently, and neocd_lr isn't neocd-lr.
# Tree check of the layout's names: packages/emulators/standalone/<name>/scripts/start_<name minus -sa>.sh, libretro/<name>-lr/.
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../.."))
bad = [name for name in sorted(os.listdir(f"{ROOT}/emulators/standalone"))
       if not os.path.exists(f"{ROOT}/emulators/standalone/{name}/scripts/start_{name.removesuffix('-sa')}.sh")]
# Beside the cores, libretro/ holds RetroArch itself and its data.
NOT_CORES = {"common-shaders", "core-info", "glsl-shaders", "libretro-database", "retroarch", "retropie-shaders", "slang-shaders"}
bad += [name for name in sorted(os.listdir(f"{ROOT}/emulators/libretro")) if name not in NOT_CORES and not name.endswith("-lr")]
assert not bad, bad
