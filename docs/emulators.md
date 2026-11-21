# Emulators, ports and tools

The emulators in use on Asgard, their default per system, and how far each is checked (marks as in
[features.md](features.md)). Every system, with its ROM folder, extensions and cores, is in
[supported-emulators.md](supported-emulators.md), which the build generates.

Every ROCKNIX system is in the image; these are the ones in use and checked on Asgard. **Menu** is what Home opens
in a game.

| System | Default | Also available | Status | Menu | Notes |
|---|---|---|---|---|---|
| Game Boy / Color | RetroArch (Gambatte) | mednafen, SameBoy, mGBA, SkyEmu, ares... | ✅ | Full | |
| Game Boy Advance | RetroArch (mGBA) | NanoBoyAdvance, mednafen, gpSP, SkyEmu... | ✅ | Full | lowerdeck (bottom-screen companion) touch fix 🧪. |
| NES / SNES | RetroArch (Nestopia / Snes9x) | Mesen, FCEUmm, bsnes, mednafen, ares... | ✅ | Full | |
| Nintendo 64 | RetroArch (Mupen64Plus-Next) | gopher64 1.1.42, mupen64plus, ares | ✅ | Full | |
| Nintendo DS | melonDS | DraStic, DSperate 3.0.5, RetroArch cores | ✅ | Resume / Quit | One window per screen, no menu bar. RetroArch's DS cores span both screens ✅ (checked on a Thor 2026-11-14; more testing to come). DraStic and SkyEmu draw one window, on the top screen. DraStic's Start, Select, d-pad and touch press fixed for the virtual DualSense 🧪. |
| Nintendo 3DS | Azahar 2126.2 | | ⚠️ | Full | Screens, layout, HD textures, Force 60 Hz, gyro. Alpha Sapphire at auto resolution freezes the Thor (use 2×). Instant menu 🧪. No geometry shaders on Turnip, as on Android (lighter GPU load, lighting slightly less exact) 🧪. |
| GameCube / Wii | Dolphin 2609 | RetroArch (Dolphin) | ✅ | Resume / Quit | Wii remote motion from the game's Gyro override (DSU) 🧪. GameCube A on the Thor's A (east profile by default) 🧪. NoGUI on Wayland has no pause of its own: the in-game menu freezes it instead (GAME-5; not checked on a Thor yet). |
| Switch | Eden 0.2.1 | Eden Duo 1.3.2.2 | ✅ | Full | Docked toggle, speed, overlay, GPU options. Tested: TWEWY, Legends Arceus, Legends Z-A, Violet. `.nsz` unsupported. Eden Duo: live companion windows on the bottom screen; its pause under the in-game menu (F4, patch 0005) is built and host-tested, not checked on a Thor yet. Gyro from the game's Gyro override (DSU), in Eden and Eden Duo 🧪. Eden's thread priorities (GPU, CPU cores, audio) now take effect on Linux 🧪. A game's controller screen counts the handheld pad as one player, and with only that pad Eden's dialog for it doesn't show, so Echoes of Wisdom no longer asks forever, waits on a greyed-out OK or crashes 🧪. |
| PlayStation 2 | ARMSX2 2.8.4 | AetherSX2 | ✅ | Its own | |
| PSP | PPSSPP | RetroArch (PPSSPP) | 🧪 | Its own | |
| Dreamcast | Flycast | RetroArch (Flycast) | 🧪 | Its own | |
| **Steam** | Steam (ARM64 client) | | ✅ | Full | x86 games through FEX + Proton, in a window on the top screen. Pad settings survive reboots; covers and store details fetched. Tested: Baba Is You, Hollow Knight, Undertale. Can't be paused. |
| **PC** (`.desktop` apps) | | | 🧪 | Resume / Quit | Steam plus native apps. |
| Gen1 Recomp | | | ⚠️ | Resume / Quit | Pokémon Red/Blue/Yellow (LÖVE). No input on native Wayland; runs under XWayland. |
| Wind Waker HD | ZeldaWWHDRecomp 0.3.0 | | ✅ | Its own | Wii U GamePad window on the bottom screen. |
| Dusklight | Twilight Princess port (dual-screen fork) | | ✅ | Resume / Quit | Companion on the bottom screen. |
| Lumi-Dex | | | 🧪 | | Pokédex companion on the bottom screen while Brilliant Diamond runs in Eden. |
| **Tools:** Asgard Music | | gmu | ✅ | | Playlists, screens-off playback. |
| **Tools:** Firefox | Firefox ESR (Mozilla's aarch64 build) | | 🧪 | Resume / Quit | Restores its tabs after Quit. Asgard Keyboard on the bottom screen. Launches full screen on the right screens (checked 2026-10-28). |
| **Tools:** Terminal | QTerminal | | 🧪 | Resume / Quit | Asgard Keyboard (Ctrl, Alt, arrows, symbols) on the bottom screen. Launches full screen on the right screens (checked 2026-10-28). |
| **Tools:** Moonlight | moonlight-qt | | 🧪 | Resume / Quit | Game streaming from a PC. Launches full screen on the right screens (checked 2026-10-28). |
| **Tools:** Files | Asgard Files | | 🧪 | | Internal storage, ROMs, SD card: copy, move, rename, delete. Launches full screen on the right screens (checked 2026-10-28). |

