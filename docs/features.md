# Features: what works today

Every feature of Asgard OS and how far it is checked. A feature is ✅ only after it was checked on a real Thor;
built, or tested on a computer or against a fake, is 🧪. Emulators, ports and tools are in [emulators.md](emulators.md).
User guides for each feature are in the [wiki](https://github.com/AsgardOperationSystem/asgardos/wiki).

✅ works · 🧪 built, not yet tested on the device · ⚠️ partial or with a workaround · ❌ missing or broken ·
⏸️ deferred · 👀 works, being watched

| Feature | Status | Notes |
|---|---|---|
| **Frontend** | | |
| Asgard Home | ✅ | Dual-screen frontend in iiSU's style: grid on top, detail card below, L+R swaps them. Replaces EmulationStation. |
| Settings button | 🧪 | A gear beside the power button in the top bar opens Settings by touch (HOME-6). Host-tested; not checked on a Thor yet. |
| Library and art | ✅ | System art, backdrops, covers, screenshots, play time, Recently played tile. |
| Tile reordering | ✅ | Y or a long press, for consoles and games (saved per console). |
| Left stick, back button and Home in menus | 🧪 | The left stick moves like the d-pad (held, it repeats), the back button is B, and Home returns to the start from anywhere in Home, Settings included (HOME-1). In the in-game menu the stick and back button work too. Host-tested against a fake pad; not checked on a Thor yet, so how far the stick must go is unchecked. |
| Trophies (RetroAchievements) | ✅ | Progress per game; ROMs hashed like RA does. Sign-in in Settings. |
| Scraping | 🧪 | Select → Scrape this game, or Settings → Library → Scrape missing for every game without a cover (both through the transfers queue, so they finish before a sleep): cover, screenshot and details (developer, publisher, genre, year, players; descriptions for PS1/PS2) from libretro, with no account. Games are found by checksum or name in an index of libretro-database built into the image; 374 of 395 names on a real library matched. Sign in to ScreenScraper (Settings → Library → ScreenScraper account; a free account) for descriptions on every system and Switch art, through Skyscraper. On a Thor (2026-11-21, build `4a0d374`): Home's scrape command brought ScreenScraper's description, details and art for Tetris in 33 s with the gamelist's other 149 games kept; libretro matched by checksum and name with no account; Switch `.nsp` files, one in a subfolder, got description and art. Skyscraper reads every ROM whole: about 20 s per GB. Not yet pressed on the device: the Scrape this game, Scrape missing and sign-in buttons themselves. |
| Cheats | 🧪 | Select → Cheats (or the game's settings page): the game's cheats, on or off per game, applied at its next launch. RetroArch games, from libretro's cheat database in the image; 3DS (Azahar) from Sharkive; PSP (PPSSPP) from its CWCheat database, `.iso`/`.cso`/`.pbp` (not `.chd` yet); DS (melonDS, DraStic, SkyEmu) from libretro's; SkyEmu's GB/GBC from libretro's GameShark codes (none for its GBA). NanoBoyAdvance has no cheats (use RetroArch's mGBA), and the page says the same, with what to use instead, for every other emulator without cheats Asgard can drive; Mednafen (GB/GBC, GBA, NES, SNES, Mega Drive, Master System, Game Gear, PC Engine) from libretro's, decoded; Dreamcast (Flycast) from libretro's; N64 (mupen64plus) from its own database, else libretro's; PS1 (DuckStation) from libretro's, `.bin`/`.cue`/`.iso`/`.m3u` (not `.chd`); Switch (Eden, Eden Duo) from switch-cheats-db, for games whose title ID is in the file name or an NSP's ticket; GameCube/Wii (Dolphin) from Dolphin's own game inis; PS2 (ARMSX2, AetherSX2) from pcsx2_cheats_collection, `.iso`/`.bin`/`.cso` (not `.chd` yet). |
| Back to Home | ✅ | Leave a game without quitting it (frozen, hidden); the first tile returns to it. |
| In-game menu (Home) | ✅ | On the bottom screen: quick save/load, screenshot, restart, quit, plus each emulator's own items (see the emulator table). |
| Every game paused under the in-game menu | 🧪 | Emulators Home can't pause through their own keys (melonDS, Dolphin, ports, Steam and PC games...) are frozen while the menu is open, with every process they started, and continue when it closes; RetroArch, Azahar and Eden keep their own pause (GAME-5). The Thor Panel leaves a game the menu froze frozen. Host-tested with a fake emulator; not checked on a Thor yet (sound and Steam's connection after a long pause are the things to watch). |
| In-game Wi-Fi and Bluetooth | 🧪 | The menu's Wi-Fi and Bluetooth tile opens Settings' pages drawn as the menu: its header, big tiles, B back (MENU-6). Built, host-tested (offscreen screenshots); not checked on a Thor. |
| In-game Performance tile | ✅ | A game's CPU cap per core type and GPU cap from its in-game menu, saved to the game and applied on leaving the page. Checked on a Thor with the GPU cap in Brilliant Diamond (Eden): raised in game, applied without a restart, and kept in the game's overrides. The CPU rows use the same path but weren't tried there. PPSSPP, ARMSX2, AetherSX2 and Flycast use their own menus, so they don't have it yet. |
| Start on Recently played → Settings | 🧪 | |
| Language | ❌ | English only: Asgard Home has no translations. Since 2026-10-28 Home and everything it starts run in a UTF-8 locale (C.UTF-8). |
| **Settings** | | |
| Wi-Fi | ✅ | Scan, join, on-screen keyboard. |
| Bluetooth | ✅ | Pair a new device scans and lists what's nearby. Checked on a Thor (2026-11-02) with a WH-1000XM4: forgotten, paired again from the page, connected over LDAC, and sound heard after an earlier pairing of it. Pairing a controller from the page hasn't been tried. With the lid closed, music stayed in the headphones without stutter when set to keep Bluetooth on; set off, Bluetooth comes back with the lid and the headphones reconnect with no press (checked by the user, 2026-11-13). After headphones drop during a game, its sound moves to the speaker (checked by the user in Eden, 2026-11-13). |
| Bluetooth device battery | ✅ | Settings > Network > Bluetooth (and the in-game menu's) shows a connected device's battery: BlueZ's for headphones (over HFP: PipeWire's native backend and the kernel's RFCOMM) and BLE pads, the kernel's for DualSense, DualShock 4 and Switch Pro pads (NET-1). Checked on a Thor (2026-11-13) with a WH-1000XM4; pads haven't been tried. |
| Bluetooth audio codec | ✅ | Settings > Network > Bluetooth (and the in-game menu's) shows the codec connected headphones or speakers play over (LDAC, aptX HD, AAC, SBC, or mSBC/CVSD for calls), read from PipeWire, and the device's page switches it with ‹ › between the ones it offers (NET-1). Checked on a Thor (2026-11-13) with a WH-1000XM4: LDAC shown, switching changed the codec and the sound came back on it, the row stays put during a switch, and the choice is kept after the headphones reconnect. |
| VPN | 🧪 | Tailscale (sign-in link on screen), ZeroTier (join by network ID), WireGuard (`.conf` files from the Samba "config" share). Back ends checked 2026-10-28 (tailscaled up and asking for a login, ZeroTier online, a `.conf` imported); the sign-in and join flows from Settings are untested. A split WireGuard tunnel no longer takes all DNS (NET-3): a tunnel whose endpoint is a hostname comes up at boot with DNS working, checked on a Thor 2026-11-21 by a reboot and by a dead tunnel. |
| USB mode, SSH, Samba, Syncthing | ✅ | |
| Date and time, device name | ✅ | |
| Per-emulator settings | ✅ | Default emulator and core per console, ROCKNIX's emulator options (shaders, aspect ratio, Azahar's resolution and layouts...) as settings rows. |
| Per-game settings | ✅ | Emulator, core, the same options, CPU/fan profile and gyro, per game. |
| GPU driver | ✅ | Turnip version selector. The image's Mesa 26.2.6 carries two upstream Turnip fixes from Mesa main: a GPU-hang register value for the A740 and flushes lost across split render passes 🧪. |
| Calibration | ✅ | Touch and sticks. |
| Stick and trigger calibration in Settings | 🧪 | Settings > Hardware > Calibration measures each stick and trigger in Asgard Home itself, then tests it before keeping it; Home exits from any step (CAL-4). GPcal is gone. A trigger's steps follow its own travel (a press no longer has to go a stick's distance). Settings answers the pad straight after closing it (no dead seconds while InputPlumber restarts). Host-tested; not checked on a Thor yet. |
| Stick calibration from `asgard.yml` | 🧪 | `asgard.stick_calibration` puts a unit's stick calibration on a fresh install from the first boot; one made on the device wins (CAL-3). Host-tested; not checked on a Thor yet. |
| `asgard.yml` | ✅ | Personal config outside the image (see below). Applied on a real boot 2026-10-28. |
| **Thor Panel and overlays** | | |
| Thor Panel (AYN button) | 🧪 | Status tiles, quick toggles, fan modes, gauges; volume and per-screen brightness with a link lock. The game is frozen while it's open. Rebuilt in Asgard Home's style (`asgard-panel`, 2026-10-28); touch and live toggles not yet checked on the device. |
| Volume/brightness overlay | ✅ | Drawn above games in Asgard Home's style. |
| **Screens and input** | | |
| Dual screens | ✅ | Landscape bottom screen, games placed on the right screen, quiet boot, "ASGARD OS" splash on the top screen. |
| 120 Hz on both screens | ⚠️ | Settings > Display, per screen. The top is fine. The bottom's colours wash out at 120 Hz (about 1.8× brighter, roughly half the saturation) until its panel commands are known, so it defaults to 60. Switch games default to 60 Hz on the top too (no Switch game runs faster, and it halves the top's redraws) 🧪. |
| Full top brightness range | ✅ | The top panel goes to its 12-bit maximum (ROCKNIX stopped ~40 % short). |
| Matched screen colours | ✅ | Per-screen white balance in the display hardware (`asgard-gamma`); the bottom defaults to tint +3, contrast +3, chosen by eye to sit close to the top while keeping shadow detail. It isn't an exact match: matching the top's white measured at tint +10. Adjustable per screen in Settings > Display. |
| OLED Ultra Black, idle blank | ✅ | Ultra Black is on the top panel only and applies after the screen cycles. Burn-in protection: screens off after a timeout, and X turns both off. |
| Touch on both screens | ✅ | Calibrated for the rotated panels. |
| Top screen hang at game launch | ⚠️ | Intermittent. Fewer modesets at launch make it rarer, not proven gone. |
| Bottom screen flicker | ⚠️ | Android's panel timings (`9046`) didn't cure it. |
| Stick lights, fan | ✅ | Fan modes and fixed speeds survive game launches. |
| Gyro (DSU / cemuhook) | ✅ | From the ADSP sensor core; Azahar uses it (aiming in Ocarina of Time 3D works). On per game: it keeps the DSP awake. |
| Gyro set up with no copying | ✅ | Its files are built at first boot from the Thor's own Android partitions. Checked 2026-11-21 on 0.0.1: with no `sensors-root/`, one boot built it and Ocarina of Time 3D's gyro aiming worked from it. |
| Gyro for Steam and SDL games | 🧪 | On InputPlumber's virtual DualSense; only tested against a fake InputPlumber. Until 2026-11-21 a ROCKNIX udev rule deleted the pad's motion node, so SDL couldn't read it; the node is kept now (built, not checked on a Thor). |
| **Power** | | |
| Sleep (s2idle) | ✅ | Full SoC sleep (CX, AOSS, DDR), 20–30 mA (~0.3 %/h). Pad, Wi-Fi, audio and storage resume. Emulators don't replay the time asleep. A lid opened again while it's going down cancels the sleep (checked 2026-11-06). 🧪 The game stays silent through every lid-shut wake, aborted sleeps included (host-tested; not yet checked on a Thor). |
| Downloads and scrapes finish before sleep | 🧪 | Update downloads and scrapes (Scrape this game, Scrape missing) share one queue, `asgard-transfers.service` (XFER-1). Sleeping while it has work (the lid, the power key, Sleep in Home) is a standby: the game pauses, screens, touch, lights and the big cores go off, Wi-Fi and storage stay on, and the Thor suspends once the queue is empty, or at 15 % battery off the charger. Opening the lid or the power key ends it early (XFER-3, XFER-4). Host-tested against a fake Thor and the real power-handler and screens-off scripts; not yet run on a Thor. |
| Sleep drain below ~23 mA | ⏸️ | Same ~22 mA floor on 7.2 and 7.3. Suspects: audio codec rails, devices on vph_pwr. See [docs/sleep.md](sleep.md). |
| Charge limit | ✅ | Stops at the limit, starts again 5 % below. Bypass charging. |
| Charge limit recalibration | 🧪 | Under the limit the gauge drifts (its full capacity up about 50 mAh a day, so 80 % holds more each day); once it's 5 % past the last full charge, the next charge goes to 100 % once, and Settings' Charge limit row says so (PWR-5). Host-tested; not checked on a Thor yet. |
| Battery report | ✅ | What used the battery since the last unplug (sleep, Home, each emulator), time left. |
| CPU cap, performance profiles | ✅ | Per core type, 25–100 %; per-game profiles. |
| **Audio** | | |
| Output follows the headphone jack | ✅ | |
| One volume on every output | 🧪 | Bluetooth headphones, the jack and boot come up at the volume the keys step from, not a level saved for that output (AUD-3, 2026-11-17). Host-tested; not checked on a Thor. |
| Speaker EQ | ✅ | Thor tuning (Android's preset), Joey's preset, or off. |
| Headphone EQ (AutoEQ) | ✅ | Pick a profile by headphone model (~8,850); saved per headphone. |
| Sound in the game menu, bass / mid / treble | 🧪 | EQ profile and ±6 dB tone per output, changed live from the menu or Settings with no gap (SND-7). Built, host-tested; not checked on a Thor. |
| Menu sounds, charger chimes | ✅ | No lag after a pause: outputs stay open 60 s after a sound (checked 2026-11-06). |
| **Storage** | | |
| SD card (UHS-I SDR104, 76 MB/s) | 👀 | Android keeps UHS off as unstable; watch for mmc errors after sleep. |
| UFS (HS-G5, 2.6–2.8 GB/s) | ✅ | |
| SD card next to an internal install | 🧪 | A card boots its own partitions (`ASGARDSD`, `STORAGESD`), not the internal install's, and internal doesn't pick up the card's; neither takes the other's (or ROCKNIX's) partitions as its games card; updates keep each one's labels (UPD-8). Host-tested; not checked on a Thor yet. |
| About page in Settings | 🧪 | Settings > About: the Asgard version, commit and build date, the Linux kernel's version, and Emulators, each shipped emulator's version taken from its package when the image is built (SET-6). Host-tested; not checked on a Thor yet. |
| Updates from GitHub (OTA) | ✅ | At startup the Thor asks GitHub whether a newer release is out, and Home offers it once (Download, Later, Skip this version). Settings > About > Updates checks, downloads with progress and Cancel, and shows what's new. A download is staged only when its signature matches the release key and its checksum matches; a cut connection resumes. Restart to install is offered on the charger or at 30% or more (SET-3, UPD-9, UPD-10). Checked 2026-11-21 on 0.0.2 (`45ff0da`): the check at startup asked the real GitHub and found nothing newer; pointed at a signed fake 0.0.3 on the LAN, it downloaded 1.7 GB, verified it, staged it, and Home asked to restart; one signed with another key was refused and nothing staged; a killed download read as stopped and started again; Cancel removed it. Not yet on a Thor: installing from a real OTA release (the installer is the one every update uses), resuming by Range against GitHub, and pressing through the prompt and the Updates page by hand. |
| Storage page in Settings | 🧪 | Hardware > Storage: free, total and used space inside and on the SD card, where the games folder is, the system partition (SET-5). Built, host-tested; not checked on a Thor yet. |
| **Logs** | | |
| Event log, freeze reports, crash logs | ✅ | In `/storage/.config/thor/`: warnings, errors, kernel oopses, Wi-Fi and sleep events; a report for any boot that never shut down. Sway seat changes aren't logged. |
| GPU `fenced register write` | 👀 | Occasional; no hang seen. |

