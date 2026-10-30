# Adding an emulator to Asgard OS

What a new emulator (or a new version of one) has to support to behave like the others on the Thor. Each item says
what Asgard expects, why, and how to check it. Most of it is wiring in Asgard. A few items depend on how the emulator
itself behaves: those are marked **(emulator)** and may need a patch to its source.

Use it as a checklist: a new emulator isn't done until every item is ticked or noted as not applicable.

## 1. Package and registration

- **Package:** `asgardos/projects/AsgardOS/packages/emulators/standalone/<name>-sa/` (`package.mk`, `patches/`,
  `scripts/start_<name>.sh`). Source patches go in its `patches/`, applied with `patch -p1` (fuzz allowed).
- **Registration:** a commit in `asgardos/` that adds it to `PKG_EMUS` for SM8550 and calls
  `add_emu_core <system> <emulator> <core> <default true|false>` in `virtual/emulators/package.mk`
  (example: the "Asgard patch 0038-eden-duo-switch-emulator" commit). runemu.sh runs `/usr/bin/start_<core minus -sa>.sh`.
- **Options:** its per-game/per-system options go in ROCKNIX's `es_features.cfg` (same patch). Thor Settings shows them,
  plus the CPU/fan profile every emulator gets (`asgard-perf-profile.sh`), with no extra work.

## 2. Launching through runemu.sh

Home starts every game as `runemu.sh <rom> -P<system> --core=<core> --emulator=<emulator>`. Going through runemu is what
gives the emulator its per-game options, CPU/fan profile, display pre-rotation, crash logs and playtime. Don't add a
launch path that skips it. Apps in the PC/Steam list (`.desktop` files) are the one exception: Home runs those itself
(see 8).

- **Kill target:** `start_<name>.sh` calls `set_kill set "<signal> <process name>"`, e.g. `set_kill set "-9 azahar"`.
  Home's in-game menu and Quit read it from `/tmp/.process-kill-data` to know which process is the game and how to stop
  it. Use the process's real name (`pidof` finds it). Name the signal only if the emulator needs one other than SIGTERM
  (Azahar asks for confirmation on SIGTERM, so it gets -9).
- **Output:** stdout/stderr go to `/var/log/exec.log`. Keep the emulator's own logging on: it's what a crash report
  contains.

## 3. Exit codes and crashes

- **(emulator)** Exit **0** on a normal quit. runemu.sh treats 137/143 (Home's Quit and the exit hotkey) as clean too.
  Any other code counts as a failed launch, and `asgard-crashlog.sh` keeps that launch's log in
  `/storage/.config/thor/crashes/`.
- **(emulator)** Don't swallow fatal signals. A crash must end the process with its signal so the kernel writes a core
  dump to `/storage/.cache/cores` (`coredumpctl`). A crash handler that catches SIGSEGV and then exits 0 hides the crash.
- **Quit and save log** (in-game menu) sends **SIGABRT** to a hung game for a core dump, then SIGKILL after 30 s. An
  emulator that ignores SIGABRT still gets its log saved, but no backtrace.

## 4. Sleep: no catch-up after waking (important)

The Thor sleeps with the game running. On wake, the emulator must carry on from where it was. It must **not** replay
the time asleep. An emulator that tries to "catch up" runs every missed frame as fast as it can, and the game looks
frozen for minutes. Eden did this after a 53-minute sleep: 2,100 frame ticks a second for about 2 minutes (2026-10-26).

An emulator is fine if **any** of these holds. Check its source: find the frame limiter / scheduler and the clock it
reads.

1. **(emulator) Its pacing clock stops during sleep:** `CLOCK_MONOTONIC` / `CLOCK_MONOTONIC_RAW`,
   `std::chrono::steady_clock`, Rust's `Instant`, SDL's `SDL_GetTicks` / `SDL_GetPerformanceCounter`, Qt's
   `QElapsedTimer`. Clocks that **keep running** through sleep: the raw ARM counter (`mrs cntvct_el0`, read directly by
   Eden and ARMSX2), `CLOCK_BOOTTIME`, and the wall clock (`CLOCK_REALTIME`, `gettimeofday`, `system_clock`, and
   libstdc++'s `high_resolution_clock`, which is the same as `system_clock`).
2. **(emulator) Its limiter drops missed time instead of replaying it:** when it is more than a frame or so behind it
   moves its reference to "now" (ARMSX2 skips whole frames, Dolphin's 100 ms "max fallback", Azahar's ±25 ms and
   melonDS's ±1 frame error clamps, RetroArch and gopher64 re-anchoring). Pacing by blocking on audio or on vsync has
   nothing to catch up either. What fails is a scheduler that re-runs every missed period of a repeating event: Eden's
   CoreTiming. Patch that kind so an event more than a second late continues from now (as Eden already does after its
   own pause): `eden-sa/patches/0002-coretiming-no-catch-up-after-sleep.patch`.
3. **Pause hook (Asgard):** before every sleep the sleep hook (`sleep.d/asgard-game-pause`) tells Home `sleep`, and
   Home pauses the running game with the emulator's own pause. On wake it sends `wake`, and Home unpauses it.
   Emulators reset their timing when unpaused. To add one, extend `Backend::togglePause()` in
   `asgard-home/src/backend.cpp` with a hotkey sent through Home's virtual keyboard (`gameKeys("F4")`) or a command
   (RetroArch's `PAUSE_TOGGLE`). It has to be a **toggle**: Home only unpauses what it paused itself. The match is on the
   exact process name from the kill data: `eden` doesn't match `eden-duo-cli`. This is also what pauses the game while
   the in-game menu is open (5), so add it whenever the emulator has a pause key.

**Test:** play for a minute, sleep for 2+ minutes, wake. The game must answer within a couple of seconds. Check
`top` right after waking: the emulator shouldn't sit at 100%+ of a core per thread while showing nothing new. If it
writes FPS to its log, the FPS should be normal straight away.

Status (2026-10-26, from each emulator's source; the sleep test on the device is still to do for each):

| Emulator | Pacing clock | After a sleep | Pause hook |
|---|---|---|---|
| Eden, Eden Duo | ARM counter (keeps running) | **replayed every missed frame**: fixed by patch 0002 | Eden F4; Eden Duo has none |
| ARMSX2 | ARM counter (keeps running) | skips whole missed frames: OK | none bound (TogglePause unset) |
| Azahar | emulated cycles + wall clock | limiter error clamped to ±25 ms: OK | F4 |
| Dolphin (NoGUI, Wayland) | steady_clock | stops in sleep; 100 ms max fallback: OK | none (NoGUI Wayland has no pause) |
| melonDS | SDL performance counter | stops in sleep; ±1 frame clamp: OK | unbound (`HKKey_Pause=-1`) |
| RetroArch | CLOCK_MONOTONIC, audio, vsync | OK | `PAUSE_TOGGLE` command |
| gopher64 | Rust `Instant` | stops in sleep; skips missed deadlines: OK | Alt+P |
| mednafen | blocking audio, CLOCK_MONOTONIC | OK; 75 ms catch-up clamp | Pause key |
| NanoBoyAdvance (SDL) | vsync | OK (no clock limiter) | none |
| Steam / PC games | each game its own | unknown: Home can't pause them | none |

## 5. In-game menu (Home button)

Pressing Home opens Home's in-game menu (`asgard-home/src/qml/GameMenu.qml`) on the bottom screen. The game should be
**paused** while it's open (`togglePause()`, the same pause as in 4). Every game gets Resume, Back to Home, Quit and save
log, and Quit game. An emulator can add its own hotkeys (quick save/load, screenshot, layout, restart): add a list for it
in `GameMenu.qml`, picked by process name, as for Azahar, RetroArch, Eden and Wind Waker HD. Hotkeys are sent with
`gameKeys()`. Home focuses the game's window first, so **(emulator)** the hotkey only needs to work while the window has
focus.

## 6. Back to Home (background)

"Back to Home" moves the game's windows to sway's scratchpad and freezes its processes with SIGSTOP
(`asgard-background.py`). "Return to game" sends SIGCONT and puts the windows back. **(emulator)** It must survive
being stopped for a long time: audio has to come back after SIGCONT, and the window must accept being moved between
outputs. The same timing rule as 4 applies, but a game in the background is never paused by the sleep hook (it's
already frozen), so here only the clock (4.2) protects it.

## 7. Screens and windows

- **Top screen (DSI-2, 1920x1080, rotated 90°):** the main window. Home focuses DSI-2 before a launch, and sway makes
  every new window fullscreen except second-screen ones (`thor-sway-rotate.sh`).
- **Bottom screen (DSI-1, 1240x1080 touch):** a second window goes there if its **title** matches
  `Secondary|[w2]|Sub|Bottom|Screen 2|GamePad`. The rule powers the panel on and rotates it. Name a second window to
  match, or add a sway rule for its app_id/title in `thor-sway-rotate.sh` (see the melonDS `[w2]`, lowerdeck and
  Azahar homebrew rules). With no window on the bottom screen, Home turns it off a few seconds after launch.
- **Touch:** the bottom panel's touches are mapped to DSI-1. The emulator has to take touch, or mouse events, on that
  window.
- **Vulkan/EGL on the rotated panel:** runemu.sh sets the pre-rotation environment (`vk_wsi_wayland_prerotate`,
  `egl_wayland_prerotate`). **(emulator)** Test that the picture isn't sideways and isn't slower than expected.

## 8. Controller

- Games see InputPlumber's virtual **DualSense**. The raw Thor pad is hidden from them. Map the emulator to that pad.
- Its SDL GUID differs between SDL2 (`030000004c050000e60c000011810000`) and SDL3
  (`030000004c050000e60c000000006800`), and so does the button order (SDL3's HIDAPI order vs evdev's). An emulator that
  binds by GUID and button number needs its config fixed **on every start** from the launcher, as
  `start_eden-duo.sh` does, because configs get seeded from other emulators.
- Motion: `asgard-motiond.py` reads the Thor's gyro and accelerometer and serves them two ways: as the DualSense's motion
  (SDL and Steam Input read it there) and as a cemuhook/DSU server on `127.0.0.1:26760` (Azahar and Dolphin use that).
- **Test:** every button, both sticks (centred at rest), triggers, d-pad in menus, and motion if the system uses it.

## 9. PC/Steam apps (`.desktop`)

Ports and PC games launched from Home through a `.desktop` file get playtime, crash logs (output in `exec.log`) and the
in-game menu like emulators. `X-Asgard-Kill=` names the process Home's Quit stops, if it isn't the `Exec=` command's own
name.

## 10. Before calling it done

- Every checklist item above checked, or noted as not applicable, in the emulator's commit message.
- Sleep test (4) passed.
- A crash test: `kill -SEGV` its process while a game runs. A log should appear in `crashes/` and a core in `coredumpctl`.
- README's changes table updated, and the status line in 4 updated.
