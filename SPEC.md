# Asgard OS specification

What Asgard OS is, what it does, what it ships, and the constraints it's developed under. What works today is in the
`README.md`, and the reason behind each past change is in `docs/changes.md`. Rule IDs are stable, so tests and commits
can cite them.

## 1. What Asgard OS is

Asgard OS is a Linux gaming OS for one device, the **AYN Thor**, a dual-screen handheld. It's a fork of
[ROCKNIX](https://rocknix.org), forked at `7cffc96` with its full history, and it ships as a single image for the Thor.

It adds three things to ROCKNIX:

- **Asgard Home**, its own dual-screen frontend, in place of EmulationStation.
- **Thor hardware support** that ROCKNIX lacks: deep sleep, both screens, touch, gyro, charge limit and audio tuning.
- **Native settings, an in-game menu and tools**, so the whole device can be used with no keyboard, SSH or PC.

### Goals, in priority order when they conflict

1. **Don't lose the device or the user's data.** Nothing may risk an unbootable Thor or lost saves, ROMs or settings.
2. **A game in progress is safe.** Sleep, Back to Home and overlays must not lose or corrupt it.
3. **Works on the device, with no PC.** Everything a user does, they can do on the Thor itself.
4. **Games run well.** While a game plays, its speed and compatibility come before saving power, unless the user chose a cap or profile.
5. **Battery and heat.** Sleep drain and idle power are product features, not afterthoughts.
6. **Stays maintainable by one owner.** Fewer mechanisms, each understandable, each with its reason written down.

### Non-goals

- Other devices or SoCs, including handhelds on the same SoC such as the Odin 2 family.
- EmulationStation or another frontend, or a dual-boot setup.
- Staying in sync with ROCKNIX `next`.

### The system

| Layer | What it is |
|---|---|
| Hardware | AYN Thor: Snapdragon 8 Gen 2 (SM8550), Adreno 740, top screen 1920×1080 (`DSI-2`), bottom touch screen 1240×1080 (`DSI-1`), UFS 4.0, microSD |
| Boot | OpenABL through Boot Loader Spec: `/flash/loader/entries/asgardos.conf` boots `/flash/KERNEL`, an EFI kernel with a built-in initramfs, and the device tree |
| Kernel | Linux stable plus Asgard's patches and device trees, 7.3.5 as of 2026-11-17 |
| Root filesystem | Read-only. User state lives in `/storage`, boot files in `/flash` |
| Display | sway 1.11, patched to count frames per window, with Mesa 26.2.6 (Turnip and freedreno) |
| Input | InputPlumber presents the pad to games as a virtual DualSense |
| Audio | PipeWire 1.2.6 and WirePlumber |
| Frontend | Asgard Home: Qt 6.10 Quick, one process with two windows |
| Asgard's services | Python and shell in `/usr/share/asgard`, as systemd units and sleep hooks |
| Games | Standalone emulators and RetroArch cores, started through `runemu.sh` |

The versions above are as of 2026-11-01. Each package's `package.mk` has the current one.

## 2. Asgard Home

Where the user browses their library and starts games. It's built for the Thor's two screens and feels like a console's home screen, which is why it replaced EmulationStation.

Two windows: the top screen shows the grid and dock, the bottom shows the detail card and hints. L+R swaps them, and
the swap is saved. It's the only frontend: it's what boots and where games start.

- **HOME-1** Buttons: A selects, B goes back, X turns the screens off, Y reorders, Start opens settings (the game's in a game list), Select opens the game's actions (scrape, cheats, its settings and overrides, details), LB/RB change tab, L+R swaps the screens. The pad uses the Thor's Nintendo layout: A east, B south.
- **HOME-2** Tabs are home (with the return tile and Recently played), consoles and trophies. Only systems with games are listed.
- **HOME-3** The library comes from `es_systems.cfg`, the ROM directories and ES-DE-format media. Tiles show art, and game cards show details and play time.
- **HOME-4** Tile order can be changed, for consoles and per console for games, and it's saved. B cancels a reorder.
- **HOME-5** Starting another game while one waits in the background asks first and warns that unsaved progress is lost.
- **HOME-6** The on-screen power button opens a menu with Sleep, Restart and Power off. A settings button of the same size sits beside it and opens Settings.
- **HOME-7** Home and everything it starts run in a UTF-8 locale. The interface is English only.
- **TRO-1** Trophies show RetroAchievements progress per game, with ROMs hashed as RetroAchievements does.
- **SCRAPE-1** Select → Scrape this game uses ScreenScraper when a developer ID is set, and otherwise libretro thumbnails with no account. Results go in ES-DE's layout.
- **CHEAT-1** Select → Cheats, also on the game's settings page, lists that game's cheats from databases shipped in the image (offline), one on/off row each. The choice is saved per game by cheat name in `/storage/.config/asgard/cheats`. Before each launch `runemu.sh` writes the cheats that are on into the game's emulator's own cheat file, so a change applies at the next start. A cheat file the user made in the emulator itself is never overwritten. RetroArch reads libretro-database's `.cht` files, Azahar FlagBrew's Sharkive (`asgard-cheats-db`), PPSSPP the image's CWCheat database, melonDS, DraStic and SkyEmu libretro-database's DS `.cht` files (SkyEmu also its GB ones), Eden and Eden Duo switch-cheats-db (`switch-cheats-db`), as their own mod folder, and Dolphin the codes in its own game inis, switched on in the user's game ini (only the cheats' enable lines; the user's other settings and the cheats they switched on in Dolphin stay), Flycast libretro-database's Dreamcast `.cht` files, DuckStation libretro-database's PlayStation `.cht` files, switched on in the game's settings ini (only the cheats' lines), mupen64plus its own `mupencheat.txt` (else libretro-database's N64 files) as a one-game copy its start script passes on, in a folder of Asgard's on its cheat path, Mednafen libretro-database's `.cht` files, decoded into its own cheat file (a section per game; one the user made in Mednafen stays), and ARMSX2 and AetherSX2 pcsx2_cheats_collection (`ps2-cheats-db`), as a pnach of their own. An emulator whose cheats Asgard can't drive (no cheat engine, like NanoBoyAdvance, or one kept in the emulator's own menu) says so and names one that has them.

### Look and feel

One consistent look across everything on the device, so Home, Settings, the panel and the tools feel like one product.

- **LOOK-1** `Theme.qml` is the single source of the look: dark translucent pills with a light rim, lavender glass panels, a selection glow, and one rounded heavy typeface (Nunito). New UI takes its colours, font and timing from it.
- **LOOK-2** Accents are aurora (default), sunset, mint and gold.
- **LOOK-3** Selection moves take 180 ms and art crossfades 320 ms. The Animations setting turns both off.
- **LOOK-4** New on-device UI is built in Asgard Home's style and works with the pad. `docs/screenshots/` shows the intended look.

## 3. Running games

A game behaves the same whichever emulator runs it: the same launch, quit, crash handling and sleep. The user shouldn't need to know how each emulator differs.

- **GAME-1** Home starts every game as `runemu.sh <rom> -P<system> --core=<core> --emulator=<emulator>`, which gives it per-game options, its CPU and fan profile, display pre-rotation, crash logs and play time. Only `.desktop` apps skip it, and those still get play time, crash logs, overrides and the in-game menu.
- **GAME-2** A launcher declares its process with `set_kill set "<signal> <name>"`, so Home can find and stop the game.
- **GAME-3** Exit codes 0, 137 and 143 are a clean quit. Anything else keeps that launch's log in `/storage/.config/thor/crashes/` (newest 20).
- **GAME-4** While a game runs, `/run/thor-playing.txt` names the game, emulator and core.
- **GAME-6** Back to Home freezes the game (SIGSTOP, windows in sway's scratchpad). Returning continues it (SIGCONT, windows restored), and audio and input come back.
- **GAME-7** After a sleep the game carries on from where it was within a couple of seconds and doesn't replay the time asleep. Home only unpauses what it paused itself.
- **GAME-9** Games see InputPlumber's virtual DualSense. The raw Thor pad is hidden from them.
- **GAME-10** The main window is full screen on the top screen. With nothing to show on the bottom screen, it goes off shortly after launch. A window that reaches into the bottom panel counts as something to show, such as RetroArch spanning both screens for a DS game (COMP-5).

### Home button and in-game menu

Controls the running game without leaving it, with the same button in every emulator, so nobody has to learn each emulator's hotkeys. The AYN button's panel (section 5) controls the device instead.

- **MENU-1** Home tapped alone opens the in-game menu on the bottom screen. Held with other buttons, it stays the hotkey modifier.
- **GAME-5** Every game gets Resume and Quit game, and a game with kill data also gets Back to Home and Quit and save log. The game pauses while the menu is open if the emulator can pause.
- **MENU-2** These get their own items too: RetroArch (its menu, quick save and load, screenshot, restart), Azahar (quick save and load, screen controls, screenshot, restart), Eden (docked mode, speed limit, overlay, screenshot, restart), Steam (overlay, Quick Access) and Wind Waker HD (its settings).
- **MENU-3** PPSSPP, ARMSX2, AetherSX2 and Flycast open their own menus instead.
- **MENU-4** Rarer and riskier actions sit in sub-grids, so a menu fits the bottom screen's 5 rows.
- **MENU-5** A game's menu has a Performance tile with its CPU cap per core type and its GPU cap, and each screen's overrides on pages of their own, the same values as its Settings page. D-pad left and right step a value, and A steps forward. A change is saved to the game's own keys, so the next launch loads it, and applies to the running game on leaving the page or the menu. A core type turned back on may need a game restart, because launchers pin emulators to the cores online at launch.
- **MENU-6** Every in-game menu has Wi-Fi and Bluetooth, a sub-grid whose two tiles open Settings' own Wi-Fi and Bluetooth pages on the menu's screen, drawn as the menu (its header, B back, big tiles, no Settings categories): on and off, joining a network with the on-screen keyboard, pairing, connecting and disconnecting. Back returns to the menu, and the menu closing closes them.

### Per-game and per-emulator overrides

Some games need different settings. These let a user tune one game or system without affecting the others, and always see where a value comes from.

- **OVR-1** An option's value comes from the game, then the system, then the OS default, as section 4 explains. An unset row names what it takes: `Emulator settings (80%)`, `OS (100%)` or `Default`. Unsetting a value goes back to inheriting.
- **OVR-2** Every emulator gets the same hardware overrides, per system and per game: CPU cap per core type, GPU cap, fan, gyro, sound EQ, sleep mode, Wi-Fi and Bluetooth while the screens are off, and each screen's refresh rate, brightness, warmth, tint and contrast, plus Ultra Black on the top. A screen override never changes the Settings value it overrides.
- **OVR-3** The emulator and core can be chosen per system and per game. A game's shader cache can be deleted from its settings.
- **OVR-4** Overrides last only as long as the game: they apply at launch, and when changed from its in-game menu (MENU-5), and the menu's profile, fan and EQ come back when it exits. Back to Home puts the menu's CPU and GPU caps, cores, fan and screen settings on while the game waits, and returning puts the game's back before it continues.
- **OVR-5** Each emulator's own options, such as shaders, aspect ratio and Azahar's resolution and layouts, come from `es_features.cfg` and appear as settings rows with no extra work per emulator.

### Companion windows on the bottom screen

Puts the second screen to use during a game: for a second display, controls or a companion app, while the game keeps focus.

- **COMP-1** A second window goes to the bottom screen if its title matches `Secondary|[w2]|Sub|Bottom|Screen 2|GamePad`. That powers the panel on and rotates it, and focus stays on the game. melonDS's second window uses this rule.
- **COMP-2** Eden Duo shows live companion windows on the bottom screen.
- **COMP-3** RetroArch games can have save-state and brightness controls on the bottom screen (ROCKNIX's lowerdeck), with focus kept on the top. The setting `asgardos.bottomscreen.type` turns them on (`vc`, the default) or off.
- **COMP-4** Asgard has window rules for ports the user installs in `/storage`, which aren't in the image: the Wind Waker HD GamePad window, Dusklight's second screen, Gen1 Recomp's secondary display, and Lumi-Dex, a Pokédex companion that opens with Brilliant Diamond.
- **COMP-5** A DS game in RetroArch (melonDS, melonDS DS or DeSmuME) uses both screens: RetroArch's one window spans them, with the bottom panel placed below the top one (ROCKNIX's `vertical-check`), so the DS's top screen is on the top panel and its touch screen on the bottom one. These games don't get COMP-3's controls. Each launch sets the core to match: melonDS DS's viewport by ROCKNIX, and for melonDS and DeSmuME top/bottom, a 31 px gap and touch input, with RetroArch's aspect from the core and no integer scaling.

### Text prompts

Lets a game ask for text, such as a character name, on a device with no keyboard.

- **TXT-1** A game's text prompt uses Asgard Home's keyboard on the bottom screen, for emulator frontends that have none. Eden Duo's software keyboard goes through it.
- **TXT-2** The result is the text on stdout with exit 0, exit 1 if cancelled, or exit 2 if it failed.
- **TXT-3** The keyboard takes over the bottom screen and powers it on, and the screen goes back to its previous state afterwards. If the game is killed while it's open, the keyboard goes with it and nothing is left behind.

## 4. Settings

Everything is reachable with the pad, and a user-facing feature ships with a way to use it on the Thor. The exceptions
are what's defined to come from outside: `asgard.yml`, WireGuard `.conf` files and the sensors root.

- **SET-1** Settings offers: device name; date, time and time zone; emulator options per console; accent and animations; library rescan; RetroAchievements sign-in and hardcore mode; about, updates and debug; sleep, restart and power off.
- **SET-2** Under Hardware it offers: audio, display, performance, network, storage, battery report and calibration. Display has a page for each screen, with that screen's refresh rate, white balance and, when separate, brightness.
- **SET-3** Restart, power off and installing an update ask for confirmation first. An update is offered only when a `.tar` is in `/storage/.update`.
- **SET-4** A change takes effect without a restart where it can. A setting that needs one says so on its row.
- **SET-5** Storage shows the free, total and used space of the internal storage and the SD card (or that no card is in), whether the games folder is on the card or inside, and the system partition.
- **SET-6** About shows the Asgard version, build and date, the Linux kernel's version, and a page with each shipped emulator's version. The image step writes that list (`scripts/emulator-versions`) from each installed package's `PKG_VERSION` (EMU-6), a tag in its trailing comment before a bare commit; no emulator binary is run to read it.
- **NET-1** Wi-Fi scan and join with the on-screen keyboard; Bluetooth pairing and forgetting, and a connected device's battery when it reports one and its audio codec while it plays, which can be switched to another the device offers; USB mode; and SSH, Samba and Syncthing.
- **NET-2** VPN offers Tailscale (sign-in link on screen), ZeroTier (join by network ID) and WireGuard (`.conf` files).

### Personal configuration: asgard.yml

Sets up a Thor once from a PC, such as Wi-Fi, logins and SSH keys, without building anything personal into the image. A fresh install picks it up with no re-entry.

- **CFG-1** Precedence, at every boot: image defaults < `asgard.yml` < the user's own changes. A value changed on the device is never overwritten by the yml.
- **CFG-2** The yml is read from `/flash/asgard.yml`, then `/storage/.config/asgard/asgard.yml`. First found wins, and they aren't merged.
- **CFG-3** `ssh.authorized_keys` lines are appended, and existing lines are kept.

### How configuration nests

There's one flat file, `system.cfg`. The nesting is in the key names, and it has two separate parts: **scope** decides
which key is read, and **source** (CFG-1) decides what value a key holds.

When something asks for an option, `get_setting <key> [system] [game]` tries these keys in order, here for `ratio` on
the 3DS. The first one with a value wins:

| Order | Scope | Key |
|---|---|---|
| 1 | This game | `3ds["Pokemon X.3ds"].ratio` |
| 2 | This system | `3ds.ratio` |
| 3 | Named system-wide | `system.ratio` |
| 4 | Bare | `ratio` |
| 5 | Global | `global.ratio` |
| 6 | Nothing set | Whatever the reader falls back to: the emulator's own default, or stock clocks, gyro off and the image's Mesa |

For example, with these two lines in `system.cfg`:

```
3ds.cpu_cap_mid=80
3ds["Pokemon X.3ds"].cpu_cap_mid=60
```

Pokémon X runs its big cores at 60 %. Other 3DS games run at 80 %, and their row reads `Emulator settings (80%)`. Games
on other systems run at stock, and their row reads `OS (100%)`. None of this affects Home, which uses
`asgard.cpu_cap.mid`.

- **CFG-9** Code that reads a game option uses `get_setting`'s order, not a lookup of its own. An empty value counts as unset, so unsetting a key means it inherits again.
- **CFG-10** "Per-emulator" settings are stored per system. The Settings level called `Emulator settings` is `<system>.<key>`. The chosen emulator and core only decide which option rows appear, so a value stays in place if the system's emulator changes.
- **CFG-11** The emulator and core resolve as the game's `<system>["<rom>"].emulator` and `.core`, then the system's `<system>.emulator` and `.core`, then the default in `es_systems.cfg`. Picking another emulator also resets the core to that emulator's first.
- **CFG-12** The menu's `asgard.*` keys aren't a scope. A game reads `cpu_cap_<type>`, `gpu_cap` and `motion` and doesn't inherit `asgard.cpu_cap.<type>`, `asgard.gpu_cap` or `asgard.motion`, so unset means stock. Sound EQ is the exception: an unset game EQ uses the saved setting from Settings.
- **CFG-13** Nesting in `asgard.yml` flattens with dots: `wifi: {ssid: x}` becomes `wifi.ssid=x`. A key that holds a value and also has children is written dotted and quoted, such as `"global.retroachievements": 1`.
- **CFG-14** Submenus in Settings, such as Hardware overrides, are display only. Their keys stay flat.

### How settings are stored

- **CFG-4** Settings live in `system.cfg`. Writes are atomic, keep comments, and replace in place. A per-game key (`<system>["<rom>"].<key>`) doesn't affect the system key.
- **CFG-5** New Asgard settings use the `asgard.` prefix. ROCKNIX's existing key names stay.
- **CFG-6** New Asgard state goes in `/storage/.config/asgard/`. Logs and reports go in `/storage/.config/thor/`.
- **CFG-7** Every setting has a safe default, and the system runs when the setting or its file is missing. A feature whose data can't ship stays off rather than failing: the gyro's service starts only when `sensors-root/` is there.
- **CFG-8** The default root password is `asgardos`, in both `distribution/options` (`ROOT_PASSWORD`) and `system.cfg` (`root.password`), and it's documented in the README. `root.password` is the source of truth: every boot applies it to the root login, Samba and the Syncthing GUI. It's a public default, not a secret.

## 5. AYN button: Thor Panel

The device's quick menu, opened with the AYN button at any time, including mid-game. It shows how the Thor is doing and
changes common settings without leaving the game. The Home button's menu controls the game; this one controls the
device. Its layout follows AYN's Android panel, so it's familiar on this hardware.

- **PANEL-1** The AYN button toggles Thor Panel on the bottom screen. A running game is frozen (SIGSTOP) while it's open and continues (SIGCONT) when it closes.
- **PANEL-2** It shows status, FPS, temperature and CPU, GPU, power and RAM gauges, and it has fan control. A second page has volume and per-screen brightness, with a lock that moves both screens together.
- **PANEL-3** Its hardware side answers one request per line and ends when its input closes.
- **PANEL-4** Its quick toggles are Wi-Fi, Airplane mode, Vibration, Ambient LED, Screenshot, Clean memory, Quit game, and the top screen's refresh rate.

## 6. Screens and input

The Thor has two different panels mounted rotated. This makes them work and look like one device, with games on the right screen and touch where the picture is.

- **SCR-1** Each screen has its own white balance in the display hardware: warmth, tint and contrast, set from Settings, with warmth and tint from -10 to 10 and 0 being the panel's own. Unset, the bottom screen uses tint +3 and contrast +3, chosen by eye to sit close to the top while keeping shadow detail. That's deliberately not an exact match, which measured at tint +10. Gains only lower a channel, so nothing clips.
- **SCR-2** Each screen's refresh rate is set separately, at 60 or 120 Hz. The bottom defaults to 60, because at 120 Hz its colours wash out (about 1.8× brighter, roughly half the saturation) until the panel's 120 Hz commands are known. Settings says so on the row. Switch games default to a 60 Hz top screen (`switch.top_refresh=60`): they run at 60 fps at most, so 120 Hz only costs power. A system or game override sets it back.
- **SCR-3** The top screen reaches its full 12-bit brightness. Brightness can be linked or separate per screen.
- **SCR-4** Touch lines up with the picture on both rotated panels.
- **SCR-5** Boot is quiet, with the Asgard splash and boot animation on the top screen.
- **SND-5** Volume and brightness changes show an overlay above games, in Asgard Home's style.

### OLED protection

Both screens are OLED, so static menus can burn in. This turns them off when they aren't needed and makes that one button away.

- **OLED-1** In Home, X turns both screens off. Any button then only wakes them and does nothing else.
- **OLED-2** Ultra Black on the top panel can be switched in Settings. It's sent at each panel power-on, so a change applies after the screen cycles.
- **OLED-3** Screens turn off after `asgard.idle_blank` seconds without input (default 300, 0 = never), and any input turns them back on.

### Calibration

Touch and sticks vary between units, so a user can correct their own on the device, with no PC.

- **CAL-1** Touch is calibrated per panel with 5 targets and then a test screen: A keeps it, Y redoes it, B puts the old one back. The pad drives every step, so a bad calibration can't lock out touch. It's kept in `asgard.touch.<screen>`, re-applied at boot, and can be reset.
- **CAL-2** Stick calibration applies before InputPlumber starts, so the pad never drops after boot. Only the rsinput parameter lines of GPcal's file are run.
- **CAL-3** `asgard.yml`'s `asgard.stick_calibration` (rsinput parameter: whole number) carries a unit's stick calibration onto a fresh install. It's written as the saved calibration and applied with CAL-2, so it's in place on the first boot. A calibration made on the device wins and is never overwritten by the yml. Its keys aren't `system.cfg` keys.
- **CAL-4** Sticks and triggers are calibrated inside Asgard Home's Settings (Hardware > Calibration), one control at a time, with no outside program. Each control is measured step by step, applied live and tested: A keeps it and saves it as the saved calibration (CAL-2), Y measures again, B puts back what was there. Home leaves from any step and puts back what was there. While a control is open InputPlumber is stopped, because it hides and grabs the raw pad, and Home reads the raw pad itself, so its buttons still drive the page. InputPlumber is restarted when the page closes, or at Home's next start if Home stopped mid-way. Until its pad is back, the raw pad keeps driving Home, so there's no moment when the buttons do nothing.

### Other input

Motion aiming for the games that use it, and stick lights as a personal touch or a battery indicator.

- **INP-1** The gyro serves both as the DualSense's motion and as a DSU server on `127.0.0.1:26760`. It needs a HexagonFS root copied to `/storage/.config/asgard/sensors-root/`, because Android's blobs and the unit's calibration can't ship.
- **INP-2** Stick lights offer colour, brightness or battery level.

## 7. Sound

The speakers sound thin and harsh without tuning, and headphones differ widely. This makes both sound good with no setup, and gives the interface audible feedback.

- **AUD-1** The default output follows the headphone jack.
- **AUD-2** EQ filter nodes stay at 100 %, and volume is set on the real sink. Every EQ chain ends in the limiter, so no preset's boost, nor bass, mid and treble on top of it, can clip.
- **AUD-3** There's one volume. Every output plays at it as it appears (headphones connecting, the jack, boot), not at a level WirePlumber saved for that output, so a volume key steps from what's heard.
- **SND-1** Speaker EQ offers Thor tuning, Joey's preset and off. Headphone EQ offers Thor tuning, AutoEQ and off.
- **SND-2** AutoEQ finds a profile by headphone model, which needs internet. A downloaded profile stays usable offline.
- **SND-3** A game's EQ override lasts until the game ends and leaves the saved setting alone. It's set on the running EQ, as SND-7's changes are.
- **SND-7** Each output's EQ, and bass, mid and treble (±6 dB) on top of it, change while sound plays, with no gap: every EQ is one chain of the same shape, and a change only sets its values. PipeWire doesn't restart for it, because SDL3's PulseAudio backend doesn't reconnect and a game would stay silent. Every in-game menu has a Sound page with them for the output that plays (Bluetooth has no EQ: it shows the speaker's), Settings > Hardware > Audio's own rows and saved settings. While a game's override sets that output's EQ (SND-3), the menu shows it and leaves it alone.
- **SND-4** Menu sounds and charger chimes can be switched off, and menu sounds have a volume. They play through `pw-play`, not Qt Multimedia, whose audio thread once froze Home.
- **SND-6** A menu sound starts with no audible delay: an output stays open for 60 s after its last sound, instead of WirePlumber's 5 s, because reopening the DSP's path took about half a second.

## 8. Power and performance

A handheld gets picked up and put down all day, and its battery and heat limit how it's used. This keeps a game ready to resume and lets the user trade speed for battery.

### Sleep

Close the lid and come back later to the same moment in the game, having lost as little battery as possible.

- **PWR-1** Sleep is s2idle with the game still loaded. CX, AOSS and DDR collapse for the sleep (`/sys/kernel/debug/qcom_stats/`).
- **PWR-2** Sleep drain stays at or under the 30 mA baseline, and lower is always better. It's measured over an unplugged sleep of an hour or more, starting at 4.13 V or lower, because readings just after a charge are gauge artifacts.
- **PWR-3** After a wake the pad, Wi-Fi, audio and storage work, with no reboot. The power button and the RTC both wake it.
- **PWR-4** With the lid closed the game stays stopped through any wake, including a sleep that aborted, and continues only when the lid opens. A lid-closed cable or charge-limit wake goes back to sleep.
- **PWR-6** The fan's rail is off in sleep: fan mode 1 becomes 3 for the sleep and comes back after it.
- **PWR-8** The gyro service runs only while asked for, per game or by `asgard.motion`, because it keeps the ADSP awake.
- **PWR-9** Background work doesn't wake the SoC in sleep or redraw when nothing changed, unless there's a stated reason.
- **PWR-10** Closing the lid or pressing the power button sleeps the Thor, and logind ignores lid events for 10 s after boot or a wake. The power key instead wakes screens that are off, and with an external display attached it blanks the internal panel rather than suspending.
- **PWR-11** The sleep mode setting offers Sleep, Light sleep (freeze) and Screen off only (no suspend).
- **PWR-12** After every wake, `asgard-pad-fix` re-probes the pad if its stream stalled, and restarts InputPlumber. `asgard.pad_fix` (on by default) controls it, with a log in `/storage/pad-fix.log`.
- **PWR-13** Opening the lid again while a lid-close sleep is still going down cancels the sleep, or wakes the Thor right after, and ends the post-wake hold early. A sleep that didn't start with the lid closing isn't cancelled by the lid being open.
- **PWR-14** Home's battery level and charging state are read again as soon as it wakes, not up to 5 s later.
- **BAT-3** A game with sleep mode `screen` keeps running with the screens off, for music on the headphone jack or Bluetooth, instead of suspending. Wi-Fi and Bluetooth stay on with the screens off unless set off (the game, the system, then Settings > Performance), and a radio turned off this way always comes back with the screens, reconnecting the Bluetooth devices it had connected.

### Charging

Lets a battery that's often plugged in last longer, by not holding it at full charge.

- **PWR-5** Charging stops at the limit and resumes 5 % below it. `100` = off, `full` = hold at 100 and resume at 95. The default is 80. Under a limit, once the gauge's full capacity has drifted 5 % above its value at the last full charge, the next charge goes to 100 % once to recalibrate it, and Settings says so; not with bypass charging.
- **BAT-2** Bypass charging runs the Thor from the cable and leaves the battery alone, charging only below 20 %.

### CPU clusters, GPU and fan

Lets the user trade speed against heat, noise and battery. Home doesn't need full clocks, and games differ in what they need.

- **PERF-1** There are three core types: little (3× A510, CPU0-2), mid (2× A715 + 2× A710, CPU3-6), prime (1× X3, CPU7). Each takes a clock cap of 25–100 % of its top clock, or off. A cap sets the highest supported frequency at or under it as `scaling_max_freq`.
- **PERF-2** At least one core type stays on, and CPU0 is never taken offline. Settings doesn't offer a choice that turns every type off.
- **PERF-3** The menu's profile applies only in Home (defaults: little 90 %, mid 75 %, prime 75 %, GPU 100 %). Games start at stock, with every core on and full clocks, and their overrides apply on top.
- **PERF-4** The GPU takes a clock cap of 25–100 %, in Home and per game. Per game, the CPU and GPU caps can also be set to Auto.
- **PWR-7** Auto (autotune) only moves maximum clocks, and doesn't take the GPU ceiling below 348 MHz until lower is tested against GMU hangs.
- **PERF-5** The fan offers curve modes (quiet, moderate, aggressive) and fixed speeds. A fixed speed survives game launches.

## 9. Battery tracking

Lets a user find out what's draining the battery, on the device, with no PC. A handheld's battery life depends on what
ran and how it slept, so the answer has to name the game, not just give a percentage.

- **BAT-1** Settings → Hardware → Battery breaks usage down since the last unplug by game, app, Home and sleep, each with its time, % used and average current. It also shows the current draw, the time left at this rate, and the charging session.
- **BAT-4** Each sample records what was running, including the game, emulator and core Home launched, so a native port or PC app isn't counted as Home.
- **BAT-5** The gauge updates in coarse, delayed steps, so per-activity figures only mean something over minutes. The report shouldn't imply more precision than that.
- **LOG-6** `battery-log.sh` writes one CSV line every 30 s to `/storage/battery-log.csv`, rotating at 5 MB and keeping one old file. A gap in the timestamps means asleep. The battery report reads it, and the logger's cost stays small because it runs all the time.

### Finding what drains the battery in sleep

Sleep drain is what's left when nothing appears to be running, so these tools show what stayed on and what woke the
device. They're on the Debug page, for investigating rather than everyday use.

- **LOG-4** `asgard.sleep_audit=1` writes one line per sleep with its deltas to `/storage/sleep-audit.csv`, including drain, what collapsed and what was running. For each sleep it also saves what stayed on and what woke the device in `/storage/sleep-audit/`, so a good sleep can be compared with a bad one.
- **LOG-5** The sleep experiment (`asgard.sleep_experiment`) switches radios off during sleep, to test one suspect at a time.

## 10. Tools, ports and PC apps

Makes the Thor useful beyond emulators: music, files, a browser, a terminal, game streaming and native games, with no PC.

- **TOOL-1** Asgard Music (playlists, screens-off playback), Asgard Files (copy, move, rename, delete across internal storage, ROMs and SD), Firefox, Terminal and Moonlight open from Home, full screen on the right screens. Firefox and Terminal have Asgard Keyboard on the bottom screen.
- **PORT-1** PortMaster is the Ports system's launcher.
- **PORT-2** A `.desktop` file in the PC system runs its own `Exec=` command. `X-Asgard-Kill=` names the process Quit stops, if it isn't the command's own name.
- **PORT-3** LÖVE ports run outside PortMaster, such as Gen1 Recomp, find the `libtheoradec` they need. Gen1 Recomp runs under XWayland, because it gets no input on native Wayland.

## 11. Graphics

Some games only run correctly on a particular driver, so a user can pick one per game instead of the whole system changing.

- **GPU-1** The Turnip driver can be chosen per game, and an unset row names what it falls back to: the system's, else the OS's (GPU-4), else the image's Mesa. "Image's Mesa" can be chosen by name, to go back to it. `runemu.sh` selects it through `VK_DRIVER_FILES`.
- **GPU-2** The image ships an extra, older Turnip (`turnip-extra`, 25.3.6) in `/usr/lib/gpu-drivers`, because the 3DS Zeldas run on it. Users can add builds in `/storage/.config/gpu-drivers`, made with `tools/turnip/turnip.sh`.
- **GPU-3** A game's OpenGL runs on Vulkan through Zink by default, as ROCKNIX's SM8550 quirk sets for the whole image, because native OpenGL showed flicker and tiling on this GPU family. It can be set to Mesa's native driver per game or system (`gl_driver=freedreno`), and back to Zink (`gl_driver=zink`). Unset is the OS's choice (GPU-4), else Zink.
- **GPU-4** Settings > Performance sets the Vulkan and OpenGL drivers for every game (`asgard.gpu_driver`, `asgard.gl_driver`), and a system's or game's own choice wins. They apply to what `runemu.sh` starts, not to Home or sway, so a bad driver can't take the menus down.
- **VID-1** Every emulator with a setting for how its picture is scaled to the screens has a Screen filter option: nearest neighbour, bilinear, and sharp bilinear or FSR where the emulator has them. The game's choice wins, then its system's, then Settings > Display (`asgard.screen_filter`), else bilinear, because nearest neighbour scales unevenly to the 1080p panels (a 1 px step across Brilliant Diamond's HP bar). `asgard-screen-filter.sh` writes it into each emulator's own config at launch.

## 12. Diagnostics

A handheld has no terminal in front of it when something goes wrong. These leave a record on the device, so a freeze or crash can be understood afterwards.

- **LOG-1** Warnings, errors, oopses, Wi-Fi and sleep events reach `/storage/.config/thor/logs/events.log`, which rotates.
- **LOG-2** A boot that never shut down leaves a report in `/storage/.config/thor/freezes/` (newest 10).
- **LOG-3** Crashes leave a core dump (`coredumpctl`, `/storage/.cache/cores`).

## 13. Kernel and hardware support

The kernel carries about 140 patches, from ROCKNIX, Kettle Linux, Armada and Asgard itself. `docs/changes.md` says which
is which and why. A patch is there to deliver one of these outcomes, and a rebase has to keep them:

- **KERN-1** Both panels run at 60 and 120 Hz, with AYN's Ultra Black and the SY7758 backlight driver, and the touchscreens work.
- **KERN-2** The pad's MCU (`rsinput`) comes back after a wake, its rail is off in sleep, and haptics and stick LEDs survive a sleep.
- **KERN-3** UFS runs at HS-G5 and resumes without PHY calibration failures. SD cards run at UHS-I SDR104.
- **KERN-4** USB resumes cleanly and releases its DDR vote when idle. A USB-C attach can wake the Thor, and charger updates don't wake it from s2idle.
- **KERN-5** The Wi-Fi PCIe link powers down in sleep and retrains on resume.
- **KERN-6** Neither the GPU nor the unused crypto engine holds a DDR vote in sleep.
- **KERN-7** The audio block (LPASS) is released in sleep, so CX can collapse, and audio resumes afterwards.
- **KERN-8** The fan's tach and RPM timer don't wake s2idle. Charge current is controllable, which is what the charge limit relies on.

## 14. Emulators and packages

Asgard's reason to exist is playing games, so the image ships every ROCKNIX system. This section covers how an emulator is packaged and which ones ship.

### How an emulator is packaged

- **EMU-3** A standalone emulator is a package in `packages/emulators/standalone/<name>/`: `package.mk`, source patches in `patches/`, and `scripts/start_<name>.sh`. A RetroArch core is a package in `packages/emulators/libretro/<name>-lr/`.
- **EMU-4** The metapackage `packages/virtual/emulators/package.mk` decides what's in the image: `PKG_EMUS` and `LIBRETRO_CORES` list the packages, and `add_emu_core <system> <emulator> <core> <default>` registers each one for a system. `runemu.sh` runs `/usr/bin/start_<core minus -sa>.sh`.
- **EMU-5** Its per-game options go in `es_features.cfg`. EmulationStation isn't in the image, but its option catalogue is.
- **GAME-8** A new emulator, or a new version of one, meets `docs/adding-an-emulator.md`: launching, exit codes, sleep with no catch-up, in-game menu, Back to Home, windows and controller. That file is part of this spec.
- **EMU-6** A package's version is `PKG_VERSION` in its `package.mk`. `docs/plans/emulator-versions.md` tracks how far each is behind upstream.

### Standalone emulators

**Bold** is the system's default.

| System | Packages |
|---|---|
| Nintendo 3DS | **azahar-sa** |
| Nintendo Switch | **eden-sa**, eden-duo-sa |
| GameCube, Wii, Triforce | **dolphin-sa** |
| Wii U | **cemu-sa** |
| Nintendo DS | **melonds-sa**, drastic-sa, dsperate-sa, skyemu-sa |
| Game Boy, Color, Advance | nanoboyadvance-sa (GBA), skyemu-sa, mednafen, ares-sa (default: RetroArch) |
| Nintendo 64 | gopher64-sa, mupen64plus-sa, daedalusx64-sa, ares-sa (default: RetroArch) |
| PlayStation | duckstation-sa, mednafen (default: RetroArch) |
| PlayStation 2 | **armsx2-sa**, aethersx2-sa |
| PlayStation 3 | **rpcs3-sa** |
| PSP | **ppsspp-sa** |
| PS Vita | **vita3k-sa** |
| Dreamcast, Naomi, Atomiswave | **flycast-sa** |
| Saturn | **yabasanshiro-sa** |
| Xbox | **xemu-sa** |
| Sega Model 3 | **supermodel-sa** |
| Atari Jaguar | bigpemu-sa (default: RetroArch) |
| Atari ST | hatarisa (default: RetroArch) |
| Amiga | amiberry (default: RetroArch) |
| Commodore | vice-sa (default: RetroArch) |
| Laserdisc | **hypseus-singe** |
| DOOM | **gzdoom-sa** |
| ScummVM | **scummvm-sa** |
| OpenBOR | **openbor** |
| iOS | **touchhle-sa** |

mednafen and ares-sa also cover many older systems, as alternatives to RetroArch.

### Platforms, apps and players

| System | Packages |
|---|---|
| Steam | **steam**: the ARM64 client, with x86 games through FEX and Proton. Pad settings survive reboots. Home can't pause Steam or PC games. |
| Heroic | **heroic** |
| Windows | **wine**, with box64 |
| Ports | **portmaster** |
| Game streaming | **moonlight** |
| Music | **asgard-music**, gmu |
| Video | **mplayer** |

### RetroArch cores

RetroArch is the default for every other system. `docs/supported-emulators.md` lists each of the roughly 140 systems,
with its ROM directory, extensions and cores. The image's cores are:

81, a5200, arduous, atari800, b2, beetle-gba, beetle-lynx, beetle-ngp, beetle-pce, beetle-pce-fast, beetle-pcfx,
beetle-psx, beetle-saturn, beetle-supafaust, beetle-supergrafx, beetle-vb, beetle-wswan, bk, bluemsx, bsnes, bsnes-hd,
bsnes-mercury-accuracy, bsnes-mercury-balanced, bsnes-mercury-performance, bsnes2014-accuracy, bsnes2014-balanced,
bsnes2014-performance, cap32, crocods, daphne, dolphin, dosbox-core, dosbox-pure, doublecherrygb, duckstation,
easyrpg, emuscv, fbalpha2012, fbalpha2019, fbneo, fceumm, flycast, flycast2021, fmsx, freechaf, freeintv, freej2me,
fuse, gambatte, gearboy, gearcoleco, geargrafx, gearlynx, gearsystem, genesis-plus-gx, genesis-plus-gx-wide, geolith,
gw, handy, hatari, idtech, jaxe, kronos, mame, mame2003-plus, mame2010, mame2015, melonds, melonds-ds, mesen, mesen-s,
mgba, minivmac, mojozork, mu, mupen64plus, mupen64plus-nx, neocd, nestopia, np2kai, o2em, opera, parallel-n64,
pcsx_rearmed, picodrive, pokemini, potator, ppsspp, prboom, prosystem, puae, puae2021, px68k, quasi88, quicknes, race,
same_cdi, sameboy, sameduck, scummvm, skyemu, smsplus-gx, snes9x, snes9x2002, snes9x2005_plus, snes9x2010, stella,
supersnes9x, swanstation, tgbdual, theodore, tic80, uae4arm, uzem, vba-next, vbam, vecx, vice, vircon32,
virtualjaguar, wasm4, xmil, yabasanshiro.

- **EMU-1** Every ROCKNIX system stays in the image. Changing a system's default emulator is a deliberate change, recorded in the README's emulator table.

## 15. Development constraints

These keep one person able to maintain a fork of a large distribution and keep upgrading its kernel. Each says why it exists.

### The fork

- **DEV-1** Asgard is its own fork, and this repo is the whole distribution. ROCKNIX fixes come in one at a time with `git cherry-pick <sha>`, never by merging `next`. The two trees have diverged, and newer `next` flashes OpenABL to the ABL slots.
- **DEV-2** The Thor is the only target. Recipes don't carry branches for other devices.
- **DEV-3** `main` is the only long-lived branch here, and `asgard` the only one in the kernel repo.
- **DEV-4** Each layer has its place: `distribution/` the distro and image tools; `device/` the SM8550 board; `packages/` all recipes (ours: `asgard/`, `asgard-home/`, `asgardos/`); `config/` and `scripts/` the build system; `tools/` build helpers; `docs/` the docs.
- **DEV-5** ROCKNIX's interfaces stay: `runemu.sh`, `system.cfg` keys, `es_systems.cfg`, `es_features.cfg`, `set_kill`. Emulator scripts rely on them, and cherry-picks keep applying because of them.

### The kernel

- **DEV-6** The kernel is a submodule, `packages/linux/src`, on its own repo (`asgardos/linux`, branch `asgard`): Linux stable plus each patch as one commit, and the device trees as one commit. That's what makes kernel upgrades easy: moving to a new version is `git rebase --onto vNEW vOLD asgard`, conflicts appear per patch, and patches that went upstream are simply dropped.
- **DEV-7** There are no kernel patch files or tarballs. The build copies the submodule as it is. A change is a commit in the submodule, pushed, followed by a pointer bump here. An upgrade also sets `PKG_VERSION` in `packages/linux/package.mk`. Force-push is allowed on `asgard` only, because rebasing needs it.
- **DEV-8** The submodule keeps its own git objects, with no alternates or `--reference`, because the build container only sees the tree at `/work`.

### Packages and the build

- **DEV-9** `./build.sh` builds the image in a build container pinned by digest. A clean checkout with submodules builds with no other setup.
- **DEV-10** The build starts from an empty environment, so tokens and `LOCAL_WIFI_*` can't reach the image. The tree is mounted at `/work`, so binaries carry no personal paths.
- **DEV-11** All build output goes under `build/`, and nothing is written elsewhere in the tree.
- **DEV-12** A package declares every dependency it uses, optional ones too. A build doesn't depend on package build order.
- **DEV-13** Package patches are applied with `patch -p1`, fuzz allowed, so that's how they're checked. `git apply` gives wrong answers here.
- **DEV-14** Tree files don't change while a build runs: stamps are re-hashed, and a change cleans install dirs mid-build.
- **DEV-15** New build inputs don't depend on LAN hosts or personal paths.

### The image and updates

- **UPD-1** The root filesystem is read-only. What must survive a reboot or update lives in `/storage`, or `/flash` for boot files.
- **UPD-2** A partial copy never looks like an update: staging copies to a temporary name, checks the checksum on the device, then renames to `*.tar`.
- **UPD-3** Staging doesn't reboot or disturb a running game. The update installs on the next boot.
- **UPD-4** An update keeps user data: saves, ROMs, `system.cfg`, `/storage/.config/asgard`, `/storage/.config/thor`, SSH keys, and emulators' own settings. New shipped keys are added to those settings, and the user's values stay. A change to a key or file format converts existing values. A default added to the image's `system.cfg` later reaches an installed system once (`/storage/.config/asgard/defaults-applied`), never over the user's value, and stays away once the user clears it.
- **UPD-5** An update never writes `abl_a`/`abl_b`, directly or through a script it calls, because a bad ABL can only be recovered through EDL. `updateabl` stays a manual command. Updates don't change the boot entry's layout without a migration.
- **UPD-6** `updateabl` runs only on a Thor and only with an image that matches its checksum. Before writing, it saves both slots whole to `/storage` and checks the copies, and it writes only after a typed confirmation (or `--yes`). It writes `abl_b` and then `abl_a`, reading each back from the device. A slot that doesn't match is restored from its backup, and the other slot isn't written, so one working slot always remains.
- **UPD-7** `installtointernal` settles everything that could stop a partition removal before it removes the first one. It refuses if the running system is on one of those partitions, and unmounts the others' mounts or stops. A removal that still fails stops it before anything is created, so a failure never leaves a half-removed table. A new partition starts after the last byte of the one before it.
- **DEV-16** Nothing personal goes in git or an image: Wi-Fi keys, logins, SSH keys, Android blobs or a unit's calibration. Those come from `asgard.yml` or from `/storage`.

### Asgard's code

- **DEV-17** Asgard Home is C++ and QML on the image's Qt 6. Asgard's services are shell and Python using the standard library and `ctypes`, with no pip dependencies.
- **DEV-18** New logic that runs without hardware gets a `test_*` file next to its source, with paths overridable through the environment so it can run against a fake sysfs. Those files don't ship in the image. `./test.sh` runs them.
- **DEV-19** Paths and setting names are interfaces: scripts, configs and installed systems rely on them.
- **DEV-20** Each kind of fact has one home: this file for what must be true, the README for what works today, `docs/changes.md` and commit messages for why, `docs/plans/` for what's planned, `docs/testing.md` for how it's tested, and the project wiki for user guides (install, recovery). A change that alters an install or recovery step updates the wiki with it, and the wiki links to these files instead of restating their rules.
- **DEV-21** Original ROCKNIX and JELOS code keeps its copyright notices. Asgard's own packages are GPL-2.0.

## 16. Known gaps

Where the tree doesn't meet this spec today. These aren't precedents. When one is fixed, delete its row.

| Rule | Gap | Plan |
|---|---|---|
| DEV-9, DEV-15 | `.gitmodules` and the `Makefile`'s build image point at LAN hosts (`gitlab.lan.example`, `registry.lan.example`), so outside the LAN a clean checkout can't build. | Replace at the public move |
| DEV-9 | Ten packages (thirteen, counting `emulationstation`, `textviewer` and `rocknix-joypad`) and `DISTRO_MIRROR` still download from ROCKNIX's GitHub. If ROCKNIX moves a file, a clean build breaks. | `docs/plans/rocknix-sources.md` |
| VID-1 | Screen filter isn't on Amiberry (`amiberry.scaling_method`, set up in several launch paths) or VICE (an SDL filter per video chip). gopher64 and Yaba Sanshiro hard-code nearest, ares only scales through a shader, DuckStation's key in this build is unknown, and SkyEmu, OpenBOR and BigPEmu keep it in binary settings. | Amiberry and VICE next; then patches or shaders for the rest. `test_gap_screen_filter.py` |
| DEV-11 | A Go package's build writes `.cache/` and `.config/` to the tree root (git-ignored). | `docs/plans/autotdp.md`, side note |
| DEV-15 | `distribution/options` points its URLs at the old `asgardos/asgardos` project. `PKG_SITE` values and Home's RetroAchievements user agent carry the GitLab URL. | Fix with the public move |
| DEV-2 | `device/config.xml` and `device/filesystem/` still carry other SM8550 handhelds' device trees and input maps. | Remove when next touched |
| MENU-5 | PPSSPP, ARMSX2, AetherSX2 and Flycast open their own menus (MENU-3), so they have no Performance tile. | Decide how Home's menu reaches them, then change MENU-3 |
| DEV-11 | The emulators package regenerates the tracked `docs/supported-emulators.md` during a build, so a build can change a file outside `build/`. | Decide whether it stays tracked |
| HOME-2 | No Recently played: `backend.recent` exists, but no QML reads it. | `docs/plans/open-gaps.md` |
| SET-3 | `PowerMenu.qml` restarts and powers off with no confirmation. | `docs/plans/open-gaps.md` |
| CFG-9 | `optionRow` in `Settings.qml` does its own lookup: it says `Default` when `get_setting` would find `global.X`. | `docs/plans/open-gaps.md` |
| CFG-13 | `parse_yaml` doesn't take the inline form `wifi: {ssid: x}`, only the block form. | `docs/plans/open-gaps.md` |
| CFG-5 | `asgardos.bottomscreen.type`, `screenscraper.*` and `global.retroachievements.webapikey` are new or renamed keys without `asgard.`. | `docs/plans/open-gaps.md` |
| LOOK-3 | The grid's scroll and the card's settle run 260 ms and 200 ms, and still move with Animations off. | `docs/plans/open-gaps.md` |
| BAT-5 | The report gives every activity an average current, even one a single sample long. | `docs/plans/open-gaps.md` |
| EMU-1 | `pico-8` was dropped from the metapackage, and no doc records it. | `docs/plans/open-gaps.md` |
| EMU-3 | `dolphin-sa`, `heroic`, `hypseus-singe`, `mupen64plus-sa` and `openbor` name or place their start script differently, and `neocd_lr` isn't `neocd-lr`. | `docs/plans/open-gaps.md` |
| EMU-4 | `cps1`, `cps2` and `cps3` register `AdvanceMame`, which has no package. The image also ships `desmume` and `gpsp`, which section 14's core list omits. | `docs/plans/open-gaps.md` |
| EMU-6 | `docs/plans/emulator-versions.md` tracks 18 standalone packages, and 16 aren't tracked. | `docs/plans/open-gaps.md` |
| KERN-1 | No Thor device tree has an SY7758 node, only the Ayaneo Pocket trees, so nothing on a Thor binds that driver. The rule may be what's wrong. | `docs/plans/open-gaps.md` |
| DEV-2 | 87 other devices' quirks in `packages/hardware/quirks/devices`, and about 45 files naming other SoCs. | `docs/plans/open-gaps.md` |
| DEV-3 | The kernel repo has `origin/debug/disp-rsc-dump`, as of the last fetch. | `docs/plans/open-gaps.md` |
| DEV-7 | `packages/linux/patches/mainline` holds four patch files, not applied because `PKG_PATCH_DIRS` is empty. | `docs/plans/open-gaps.md` |
| DEV-11 | `scripts/image` leaves an empty `target/` at the tree root. | `docs/plans/open-gaps.md` |
| DEV-17 | `asgard-motiond.py` imports `dbussy`, a recipe's package, and `asgard-gamma` is C. | `docs/plans/open-gaps.md` |
