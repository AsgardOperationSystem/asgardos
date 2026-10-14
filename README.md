# Asgard OS

An OS for the AYN Thor built on ROCKNIX. ROCKNIX is a pinned submodule and Asgard is a stack of patches and new
files on top of it, so following ROCKNIX is a pin bump plus fixing whichever patch stops applying.

```
rocknix/      ROCKNIX distribution (submodule: branch next, shallow)
patches/      changes to existing ROCKNIX files, applied in order with git apply
overlay/      new files copied over the tree (kernel patches, quirks, packages)
build.sh      prepare rocknix/ and build the image (./build.sh [prepare|upgrade])
inject-config.sh  put your asgard.yml on an image's boot partition
frontend/     -> the Asgard Home source (overlay/projects/ROCKNIX/packages/asgard-home/src)
```

## Status (2026-10-10)

Asgard runs on the Thor (installed 2026-10-10 as a `.tar` update over ROCKNIX). Newer frontend changes are tested
live from bind-mounted dev builds before they reach an image.

### Working
- ✅ **Boot without ROCKNIX ES:** `essway.service` starts Asgard Home; sound, services and the pad come up. Boot-time
  suspend is gone (logind holdoff 10 s; with 0 the lid's boot state suspended the Thor and broke ADSP audio).
- ✅ **Sleep/resume (s2idle):** lid close in the menu and 10+ min asleep mid-game both resume cleanly; the gamepad
  re-handshakes on the first try. CPU cluster reaches `cluster_sleep_1`. (PR #3126, `0001`, CPU0 idle quirk,
  regulator mem states, PCIe suspend OPP, USB autosuspend, rsinput `1023`)
- ✅ **Storage:** SD at UHS-I SDR104 (76.8 MB/s), UFS at HS-G5 (2.6–2.8 GB/s).
- ✅ **OLED Ultra Black** on the top panel.
- ✅ **Bottom screen:** landscape rotation, dual-screen window rules, display sleep hook.
- ✅ **Asgard Home:** library with system artwork, launching (emulator/core per system and per game), play time,
  Trophies tab (RetroAchievements: 249 of 362 hashed ROMs matched; needs `global.retroachievements.webapikey`),
  X turns both OLEDs off, touch on the bottom screen, menu sounds.
- ✅ **Settings (Start), iiSU layout:** Wi-Fi (scan/join with an on-screen keyboard), Bluetooth, USB mode, SSH/Samba/
  Syncthing, stick lights, RA options, fan, CPU cap, charge limit, sleep mode, Power (sleep/restart/off), updates
  from `/storage/.update`. Y on a game: its own emulator/core.
- ✅ **Volume/brightness keys** show a slider.
- ✅ **AYN button → Thor Panel** (status tiles, fan modes; touch or d-pad + A, L1/R1 page, only AYN closes); the running
  game is frozen (SIGSTOP) while it's open. Page 2: volume and per-screen brightness sliders in the OSD's style, with a link lock.
- ✅ **OLED idle blank** (timeout in Settings), **battery logger**, **speaker DSP**, **CPU clock cap**, **hostname**.
- ✅ **melonDS** two-window layout without the Qt menu bar.
- ✅ **Settings → Hardware → Battery** (2026-10-12): since the last unplug, what used it (Sleep, Home, each emulator) with
  time, % and mA, time left at that rate, and the charge in progress (`battery-report.py` over the battery log).
- ✅ **Audio** (2026-10-12): the default output follows the headphone jack (`0025` + WirePlumber priority);
  Settings → Hardware → Audio: speaker EQ Thor / Joey / off, headphone EQ Thor / off / **AutoEQ** (type a model,
  pick from AutoEQ's ~8,850 profiles, needs internet; `asgard-eq.py`); charger in/out chimes.
- ✅ **Select on a game → Scrape this game** (2026-10-12): cover + screenshot from libretro thumbnails into ES-DE's
  media (`asgard-scrape.py`); ScreenScraper is wired in but off until a developer ID is set (`asgard.yml`).
- ✅ **Gyro step 2:** the ADSP sensor core's QMI service (svc 400) comes up (FastRPC heap + hexagonrpcd).
- ✅ **Gyro step 3:** accel and gyro stream from the sensor core over QMI/QRTR (`ssc.py`, ~110 Hz each).
- 🧪 **Gyro step 4:** `asgard-motiond` serves them as a DSU (cemuhook) motion source on 127.0.0.1:26760, and
  Azahar uses it while it runs (`0016`). Axis directions still to be tuned in games (`asgard.motion_map`).

### In progress / untested
- **Switch: Eden v0.2.1** (`eden-sa`, built from source, NCE on; `0021` adds the `switch` system and Qt Charts
  for Eden's performance overlay; `eden-sa/patches/0001` fixes the build on GCC 16/fmt 12). Keys and firmware come
  from the card's `bios/NSO/` (`prod.keys`, `title.keys`, `Firmware.<ver>.zip`, installed on the first start).
  Handheld mode, pinned to cores 3–7, updates/DLC loaded from the ROM folders (Asgard Home hides them from the
  library). Home menu: docked toggle, speed limit, overlay, screenshot, restart. `.nsz` isn't supported: convert
  to `.nsp`. **Tested 2026-10-11:** TWEWY Final Remix, Legends Arceus, Legends Z-A and Violet boot; controls work
  as Player 1 = Handheld in handheld mode, which in Eden's ini is two slots: `player_0` typed Handheld but
  disconnected, `player_8` connected with the bindings (Pro Controller is rejected by TWEWY; a Handheld pad on a
  docked console is rejected by every game). TWEWY is touch-only in handheld, as on hardware.
  Open: Eden's docked toggle (F10) pops a modal dialog and leaves player 1 on Pro after returning to handheld;
  Z-A's software keyboard asserts (`SwkbdConfig revision=1048590`; harmless, the 0x4C8 config parses as the newest
  known layout); Eden reports firmware 22.0.0 with 23.0.1 installed (games boot regardless). Violet's name-entry
  keyboard once flipped case constantly (pad verified idle over SDL); opening and closing the Home menu (pause/
  resume) cured it. Suspect Eden's `InputInterpreter` press-state latch; dig in if it recurs.
- **Batch B sleep drain** (2026-10-12): MCU rail and stick-LED controllers off in sleep, fan tach/timer quiesced
  (`9032`–`9035`, `0024`). Pad resumes first try over 3 RTC sleeps; CX/AOSS still never collapse and DDR stays at
  1555 MHz asleep. ≥1 h unplugged sleep not measured yet.
- **gen1recomp touch:** its on-screen controls need `POKEPORT_TOUCH=1`, and under native Wayland (SDL3 via sdl2-compat)
  its window got no input at all, not even a keymap; under XWayland (`SDL_VIDEODRIVER=x11`) touch works. Both are set
  in the port's own launcher (`/storage/apps/gen1recomp/gen1recomp-sbc.sh`). Root cause in SDL3's Wayland path not found.
- **D-pad slow to work after boot** (reported 2026-10-10): for a while after the Thor boots the d-pad doesn't respond
  well. Not investigated yet (suspects: rsinput's boot handshake / RX stream, InputPlumber or the frontend's pad open retry).
- **In-game menu (Home tap):** plumbing verified (command FIFO, virtual keyboard); not yet tried inside a game.
- **lowerdeck touch fix** (GB/GBA bottom-screen companion): tested in code, waiting for a try on the device.
- **Boot splash** ("ASGARD"): compiles; shows from the next image.
- **Thor Panel** labels don't scale well; a rebuild in Asgard Home's style is planned.
- Shaders, ratios and other per-game overrides still open the classic (SDL) screen.
- **asgard.yml:** self-test passes; not yet applied on a real boot.
- **hexagonrpc package:** not yet built through ROCKNIX's cargo flow (the Thor runs a separate cross-build).
- **Persistent event log (wanted):** the journal is RAM-only, so a crash or reboot loses the previous boot. On
  2026-10-12 (~20:40) the Thor came up after a reboot, had Wi-Fi for a minute, then went into airplane mode by
  itself; something had crashed, and nothing survived to say what. Log to `/storage` across boots: kernel
  oopses/WARNs/panics (pstore/ramoops too), rfkill/airplane and NetworkManager radio changes, USB/PHY resume
  failures (`dwc3_qcom_pm_resume returns -110`), sway seat changes, and suspend/resume. Then they can be monitored.
- **Sleep drain:** the SoC rails (`aosd`/`cxsd`/`ddr`) still never collapse (see Deep sleep plan). Since `9039`
  (2026-10-14) DDR sits at 200 MHz asleep instead of 1555; the ≥1 h drain with it is unmeasured.
- Our own scraper (ScreenScraper, with an Asgard developer ID kept out of the repo).
- **Steam:** back in the image (Valve's native ARM64 client in gamescope, x86 games through FEX and Proton ARM64).
  First run installs it with ROCKNIX's Install Steam (`0015` fixes it on the image's grep); games still untested.

### Known broken / limitations
- 🧪 **Charge limit** (2026-10-11 build): `9003` replaced by Kettle's charge-current control (`9020`) and
  `asgard-charge-limit.service` (0 A at the limit, back at limit − 5 %). Untested on the device yet.
- **Pokémon Alpha Sapphire at auto 3DS resolution freezes the Thor** on Vulkan (`dpu_encoder_frame_done_timeout`):
  a GPU/display hang below Azahar. Workaround: that game at 2× (per-game `resolution_scale`). Azahar 2126.2 is
  kept but does **not** fix it (correction to !13).
- **Steam** isn't in the image (FEX thunks don't build).
- **thor-sensorspd** stops for sleep and is restarted 3 s after resume (fixed 2026-10-11: the resume hook's direct
  start was rejected while suspend.target's job was queued, so gyro was gone after any sleep). Restart verified
  over a 30 s RTC sleep.
- **Charger plugged in while asleep isn't seen** (2026-10-10): the Thor stays on the cable discharging, reporting no
  charger (`qcom-battmgr-usb/online=0`, no typec partner), sometimes until reboot. Likely `0502` masking the IPCC
  mailbox in suspend, so the UCSI attach is never delivered or acked. Fix in the next image (untested): `9005` keeps
  IPCC live in s2idle on `ayn,thor` and wakes on a USB-C connector change; `/storage/.config/sleep.d/95-thor-charge-fix.sh`
  re-suspends a lid-closed cable wake and rebinds `ucsi_glink` if still stuck 75 s after a wake (log
  `/storage/charge-fix.log`). Watch sleep drain: battmgr messages are now handled during sleep. First `9005` image (15:59) **reset the Thor on an unplug while asleep**: the ucsi/altmode workers programmed dwc3 and the QMP PHY with devices suspended; they now run on `system_freezable_wq` (after resume). Plug-in while asleep produced no UCSI notification at all on that image (ADSP probably holds it while `0003` sleepstate says the AP is asleep). **16:13 image (2026-10-10):** unplug while asleep wakes and re-sleeps without a reset (2/2); plug-in while asleep woke and charged on the 2nd try (1/2, `0003` kept). Still to do: more plug-in repeats, and a ≥1 h unplugged sleep to compare drain with the ~4–5 %/h baseline.
- Occasional `fenced register write (0x8a1)` from the GPU; no hang seen.
- SD SDR104: Thorch keeps UHS off as unstable; watch for mmc errors after sleep.
- No locale generation for `system.language` (ROCKNIX ES did it).

## Deep sleep plan (2026-10-14)

Goal: full SoC sleep (`cxsd`/`ddr`, ideally `aosd`, counting in `/sys/kernel/debug/qcom_stats/`), as Android does
on this Thor (750+ CX/DDR collapses in 10 min, each one resumed). Today the PCIe suspend OPP (`0220`/`0221`)
keeps a small DDR vote in sleep; without it the first wake from DDR low power resets the SoC. Full notes:
`~/system/devices/ayn_thor_pro.md`, sections from "CXSD-only sleep experiment" on.

**Known (2026-10-14):**
- The reset is the SoC dropping PS_HOLD: XBL log (`9043`, `/sys/kernel/debug/xbl_log`) shows `Reset by PSHOLD`,
  `Hard Reset` and, only after the crash, `PON by RTC`. Not a TZ crash (`qcom_scm` download mode stays unused),
  not a power fault (PMIC PON registers match a normal reboot). DDR is re-initialised, so pstore stays empty.
- It hits the first wake event after DDR enters low power (alarm +60: kernel 117 s after suspend; +300: 163 s).
- Android's apps_rsc sleep/wake sets (RPMh trace, cmd-db names) match Linux's with the floor dropped, except
  LDO E1 and E3, which Android switches off in SLEEP and on in WAKE. Copying that alone (`0028`, disabled in
  `patches-disabled/`) hung a normal sleep: their consumers (PCIe PHY, USB PHY, DSI/UFS PLL) aren't ready.
- Ruled out: ADSP/CDSP (stopped), UFS (already `spm_lvl=5`), MC4/SH5 (`9042`), Wi-Fi PDC table (`9038`),
  AOSD block (`9037`), GPU stale votes (fixed by `9039`), display RSC (empty TCSs, `9044` disabled).

**Plan (port Android's suspend behaviour driver by driver, Qualcomm downstream source:
[OnePlusOSS/android_kernel_oneplus_sm8550](https://github.com/OnePlusOSS/android_kernel_oneplus_sm8550)):**
1. Measure the ≥1 h unplugged sleep drain on the current image (`9039`) against the 100–135 mA baseline.
2. PCIe: read `msm_pcie`'s system-suspend path (PHY power-down, GDSC, rails, its RPMh votes) and make
   `pcie-qcom` do the same. Both LDO E1 and E3 feed the PCIe PHY.
3. USB: same for `dwc3-msm` and the QMP/HS PHYs (`usb3_phy_gdsc` stays on in sleep today).
4. Retry `0028` (LDO E1/E3 off in sleep) once no consumer still needs them.
5. Floor-dropped test: `DEBUG=1 ~/system/thor/rocknix/aosd-test.sh c` (`a` = floor kept, safe).
6. If still resetting: write the findings up for linux-arm-msm (Qualcomm's engineers work on this state for
   X1E/SC8280XP), and ask AYN for its kernel source under the GPL.
7. Clean up whatever is no longer needed: test switches (`9037`/`9038`/`9042`), ftrace (`0027`), ramoops
   (`0029`/`0030`).

## Building

```
git clone --recurse-submodules https://github.com/AsgardOperationSystem/asgardos.git
cd asgardos && ./build.sh      # ROCKNIX's docker build of the SM8550 image -> rocknix/target/
```
`./build.sh prepare` only resets `rocknix/`, applies `patches/` and copies `overlay/`.

## Upgrading ROCKNIX

```
./build.sh upgrade          # pin -> latest next, then apply patches
# a failing patch: fix the file in rocknix/, regenerate that patch with git -C rocknix diff, rerun
git add rocknix patches && git commit -m "ROCKNIX <date>"
./build.sh
```

## Personal config: asgard.yml

Nothing personal is built into the image. Wi-Fi, logins and SSH keys live in `asgard.yml` (start from
`asgard.yml.example`; `asgard.yml` is git-ignored) on the boot partition (`/flash/asgard.yml`, or
`/storage/.config/asgard/asgard.yml` after `installtointernal`). `./inject-config.sh <image> asgard.yml` puts it
on a local copy of an image. At every boot each key is applied unless the setting was changed on the device:
**image defaults < asgard.yml < the user's own changes**. Never build with ROCKNIX's `LOCAL_WIFI_SSID` /
`LOCAL_WIFI_KEY` / `LOCAL_SSH_KEYS_FILE`; they bake secrets into the image (`build.sh` strips them).

## Asgard Home (frontend)

`frontend/` → `overlay/projects/ROCKNIX/packages/asgard-home/src`: the only frontend. Qt Quick on the image's Qt 6,
two windows: top 1920x1080 (hero card, status, hints) and bottom 1240x1080 (dock + tile grid), styled after
iiSU's dual-screen home with our own code and artwork (Nunito, OFL).
- `backend.cpp`: library from ROCKNIX's `es_systems.cfg` + ROM dirs + ES-DE-format scraped media
  (`/storage/ES-DE/{gamelists,downloaded_media}`), playtime (`playtime.jsonl`), battery, launching through
  `runemu.sh`; InputPlumber's pad read from evdev (positional = the Thor's Nintendo layout: A east, B south).
- `qml/`: `Main.qml` (state + navigation), `HeroCard`, `Tile`, `Dock`, `Backdrop`, small parts.
- `dev.sh shot ["keys"]` renders both screens offscreen on the desktop from `frontend-dev/root` (a git-ignored
  copy of the Thor's library); `dev.sh thor ["keys"]` cross-builds, copies to the Thor and renders there.

## Gyro: ADSP sensors root

The Thor's gyro/accel (SH5001) live in the ADSP's sensor core. `thor-sensorspd.service` (hexagonrpcd) serves the
sensors PD a HexagonFS root that isn't in the image (Android blobs + this unit's calibration): copy it to
`/storage/.config/asgard/sensors-root/` (`hexagonrpc.json`, `dsp/` from the Thor's `dsp_a`, `vendor/etc/sensors`,
`vendor/lib/rfsa/adsp`, `odm/etc`, a writable copy of `persist/sensors`, `socinfo/`). The service starts only when
it's there. Streaming the readings to games (steps 3–4) isn't done yet.

**Moving from the current ROCKNIX install (one time, first Asgard boot):** the Thor already has a working root at
`/storage/.config/thor/sensors/root2`. Copy it over, then start the service:
```
cp -a /storage/.config/thor/sensors/root2 /storage/.config/asgard/sensors-root
systemctl start thor-sensorspd
```

## Changes on top of ROCKNIX

One merge request each; its description and commits say what was broken, why, and what changed.

| Change | Why |
|---|---|
| ROCKNIX PR #3126 (SM8550 suspend/resume) | Upstream `next` has no working sleep on the Thor; the open PR does. Delete `0000` once it merges. |
| s2idle + `fw_devlink` cmdline (`0001`) | CPUs never reached cluster sleep; GPU power domains stayed on because `sync_state()` waited forever. |
| CPU0 idle quirk (`097-cpu0-idle`) | ROCKNIX disables CPU0's deep idle, so the CPU cluster could never power down. |
| Regulator suspend states in s2idle (`0219`, `0002`) | DT `regulator-state-mem` only applied to s2ram; the Thor sleeps with s2idle. |
| PCIe suspend OPP (`0220`, `0221`) | Without a small DDR vote in sleep, AOP firmware never returns to Linux (hang on wake). |
| USB autosuspend udev rule | The idle USB controller held a 1 GB/s USB→DDR bandwidth vote. |
| smp2p sleepstate (`9000`, `0003`) | Experimental: Android tells the ADSP when the CPUs sleep; mainline doesn't. |
| rsinput oversized RX (`1023`) | Gamepad dead after resume: handshake replies arrived in big chunks and were dropped. |
| SD UHS-I SDR104 (`0004`) | A caps mask kept the SD card at 3.3 V high-speed: 16.6 MB/s. |
| UFS HS-G5 (`1024`) | Internal storage ran at HS-G4: 1.5 GB/s instead of 2.6–2.8. |
| OLED Ultra Black (`9001`) | Android's Ultra Black fixes colour shift/mura at low brightness; Linux never sent it. |
| Charge limit (Kettle `1121` `1170` `1190` `1388` = `9018`–`9021`, `asgard-charge-limit`) | The firmware ignores the end threshold (our old `9003`); it takes a charge current. `1170`: charger updates no longer wake s2idle. |
| Azahar 2126.2 (`0005`) | Newer Azahar, kept by choice; it does **not** fix the Alpha Sapphire freeze (see Status). |
| No Steam (`0006`) | FEX-Emu's 32-bit thunks fail to build with GCC 16.2, breaking the image build. |
| melonDS menu bar (`0007`) | In two-window mode melonDS showed its Qt menu bar on one screen. |
| asgard package + boot tuning (`0008`) | Hostname, USB autosuspend, charge limit, CPU clock cap at every boot. |
| asgard.yml | ROCKNIX preconfigures Wi-Fi and keys by baking them into the image; Asgard keeps them in a file next to it. |
| Kettle sleep/GPU fixes (`9007`–`9017`) | Kettle `1150` `1160` `1180` `1291`–`1293` `1350`–`1352` `1384` `1385` (see Projects to learn from). Flashed 2026-10-11 20:02: GPU boot DDR vote gone, 60 s RTC sleep resumes clean (pad handshake first try, Wi-Fi, audio). Sleep drain over ≥1 h not measured yet. |
| Bottom touch follows the panel (`thor-bottom-touch`) | Single-screen games run with DSI-1 off but its touchscreen on: a touch moved sway focus to the empty bottom workspace and RetroArch paused (`pause_nonactive`). The watcher enables/disables the touchscreen with every DSI-1 power change. Also: the AYN panel now powers DSI-1 off when it closes during a game. |
| No seat1 touch (`0022`) | ROCKNIX attached both touchscreens to seat0 and seat1, so every touch reached Asgard Home twice; the phantom second press stole taps (Home power button did nothing). Recurs if ROCKNIX's `start_steam.sh`/Heroic launchers die before undoing `seat seat1 fallback true`; Home resets it after every game (`backend.cpp`). |
| Display sleep hook | After resume the bottom panel lit up (black) even when it was off before sleep. |
| Bottom screen rotation + window rules | The bottom panel was portrait; games opened on the wrong screen or half the screen. |
| OLED idle blank | Burn-in protection: both screens off after 5 min without input. |
| Battery logger | Measures sleep drain and records charging state (a not-charging-after-sleep case had no data). |
| Speaker DSP | The speakers sounded thin and harsh without Android's JamesDSP preset. |
| Thor Settings | All system settings lived in ROCKNIX ES; Asgard needs them without it. |
| AYN button → Thor Panel | The AYN key did nothing on Linux; Home was only a hotkey modifier. |
| Asgard Home | ROCKNIX ES feels dated and isn't built for two screens; this is our own frontend. |
| Asgard Home as the only frontend (`0009`) | ROCKNIX ES is removed from the image; the frontend unit boots Asgard Home. |
| ADSP FastRPC remote heap (`0010`) | The ADSP sensors PD (gyro/accel) can't start without a reserved FastRPC heap. |
| ADSP sensors PD server (`hexagonrpc`) | Gyro step 2: starts the sensor core's QMI service. |
| Motion server (`asgard-motiond`, `0016`, `0023`) | Gyro steps 3–4: accel/gyro as a DSU motion source; Azahar's 3DS motion input. Runs only while Azahar does (`0023`): streaming kept the ADSP waking ~185×/s. |
| Trophies tab | RetroAchievements progress per game: ROMs hashed like RA does (rcheevos), matched through RA's Web API. |
| Kettle/Armada batch A (`9022`–`9031`) | Kettle `1060` `1110` `1200` `1210` `1220` `1250` `1270` `1280` `1383`, Armada `0048`: tsens wakes, haptics buzz after rumble, GPU queue priority, command-mode vblank timestamps, DSI clocks off the PLL when the screens are off, ICE/PCIe/ath12k fixes, GPU load in debugfs. Picked by dry-running every Kettle/Armada patch against our tree (2026-10-12). |
| MCU rail off in sleep (`9032`–`9033` Kettle `1310` `1311`, `0024`) | `vdd_mcu_3v3` was always-on: the gamepad MCU and both stick-LED controllers stayed powered through sleep. |
| Fan quiet in sleep (`9034`–`9035`, Kettle `1300` `1410`) | The 1 Hz RPM timer and tach IRQs kept waking s2idle (Kettle: blocks CPU cluster collapse). |
| USB PHY pipe clock (`9036`) | One PHY init timeout (a USB-C cable wake) disabled `pipe_clk` twice; every later resume then failed (`-110`) and the controller held its 1 GB/s DDR vote through sleep until a reboot. |
| Default output follows the jack (`0025`, WirePlumber rule) | ROCKNIX's `hdmi_sense` pinned the first sink at boot (our speaker EQ filter), so headphones never took over; and ALSA ranked the speaker above them. |
| Gunyah watchdog driver (`0026`, `CONFIG_GUNYAH_WATCHDOG=y`) | Probe: shows whether the hypervisor has a watchdog (a `watchdog` under `/sys/class/watchdog`), a suspect for the restart on wake from full SoC collapse. The driver stops it at probe and across suspend. |
| Game-aware battery and sleep logs (`playlog.py`, `battery-log.sh`, `asgard-sleep-audit`, `asgard-charge-fix`) | Native ports and PC apps were logged as "menu". Home's launch record (`/run/thor-playing.txt`) now names the game, emulator and core; sleeps log DDR residency and save interconnect/regulator/genpd summaries; the game is SIGSTOPped through a lid-closed cable wake. |
| EQ filters at 100 % (`state.restore-props = false`) | While the speaker EQ was the pinned default, the volume keys moved it; a stale 45 % (−21 dB) stayed behind. |
| Speaker/headphone EQ, AutoEQ, Joey (`asgard-eq.py`, `eq/`) | Selectable EQ. Joey's Retro Handhelds JamesDSP preset as a minimum-phase FIR (`gen-speaker-ir.py`) + width-2 widener + `asgard-limiter` (our LADSPA lookahead limiter: PipeWire has none, and the preset adds +15 dB). PipeWire 1.2.6's parametric-equalizer module ignores node names, so AutoEQ files become biquad filter-chains. |
| Home sounds via `pw-play` | `QSoundEffect`'s audio thread once spun at 100 % holding a lock the UI waited on: Home froze. Qt Multimedia is gone. |
| Battery report, charger chimes, scraper | Settings → Hardware → Battery; `charger-in`/`out` on the charger's online flag (the battery reads "Not charging" at the limit); Select → Scrape this game. |
| GPU stale RPMh votes (`9039`) | Upstream [d9108bfdb746](https://github.com/torvalds/linux/commit/d9108bfdb746edacdb05bd27959a4ae63c6c7f3f), not in 7.2: an inverted check left the GPU RSC awake after any GPU use, holding DDR at 1555 MHz (4224 after Eden) through sleep. Now 200 MHz. |
| LPASS macro votes, syscon XO (`9040`, `9041`) | From x1e-sleep: tx/rx macros held `macro`/`dcodec` (ADSP audio core) forever (upstream 7.3); syscon kept TCSR's parent `bi_tcxo` prepared. |
| Deep-sleep test switches (`9037`, `9038`, `9042`) | Runtime-only, off by default: `qcom_aoss.aosd` (AOP `aoss_slp`), `pcie_qcom.suspend_floor`, `qcom_aoss.send` (raw AOP message), `asgard_ddr_wake.enable` (Android `dcvs_fp` MC4/SH5 votes). Driven by `aosd-test.sh`. |
| Reset forensics (`9043`, `0027`, `0029`, `0030`) | XBL log in debugfs (reset reason), ftrace for RPMh traces, pstore console + 4 MB ramoops. Debug only; see Deep sleep plan step 7. |

## Projects to learn from

Other ARM64 handheld distros that cover the Thor or SM8550. Check them before solving a Thor problem from scratch.

- **[Kettle Linux](https://github.com/kettlelinux/kettlelinux)** (BSD-3-Clause, early, single developer). SteamOS "deckard" aarch64 userspace + mainline **7.2** with a pinned patch stack. **Targets the AYN Thor and Odin 2 Portal** (SM8550) and the RP5. Worth reading:
  - kernel patches for panels, gamepad, LEDs, haptics, microSD, Wi-Fi and **s2idle suspend**. Compare with ours for sleep drain (DDR stuck at 1555 MHz asleep) and the rsinput resume stall.
  - Thor bottom screen: a Performance app (stats, trackpad, keyboard) plus a Plasma Mobile touch shell in Game Mode.
  - power controls: TDP, per-game fan curves, Auto TDP, **charge limit** (our `9003` doesn't work yet), refresh rate.
  - InputPlumber presents the pad as a Steam Deck controller; A/B atomic updates (RAUC).
- **[Armada](https://github.com/armada-os/armada)** (GPL-2.0+, ~1.9k stars, very active). Fedora bootc + device support derived from ROCKNIX; Steam Gaming Mode + KDE, FEX + Proton, OTA updates, Armada Control (power, fan, controller, calibration). Its SM8550 sleep work is [armada-packages #1](https://github.com/gh123man/armada-packages/pull/1) (RP6: #2954 ported to 7.0.11, UFS gate-race fix, charger-wake classifier, PCIe D3cold). Worth checking:
  - its sleep patches against ours.
  - how it sets up Steam + FEX + Proton and per-game compatibility settings (our Steam installs, but no game has been tested yet).

### Findings from Kettle/Armada (2026-10-11)

Kettle's `kernel/patches/README.md` is a dense, per-patch log of SM8550 sleep/GPU fixes, many by gennro and
shared with Armada. These apply cleanly to our 7.2 tree (dry run) and aren't in it:

| Kettle | What it fixes | Relevance here |
|---|---|---|
| `1180` a6xx drop boot bus vote | GPU driver's boot DDR vote (680 MHz OPP, 16.5 GB/s) is never removed while the GPU is powered | **DDR at 4224 MHz with the screens on** (measured) |
| `1150` geni power down open ports | open UARTs (rsinput pad, BT) keep SE clocks, CX and QUP/NoC votes through s2idle | blocks CX collapse |
| `1160` ufs lane clocks once | leaked clock refs keep UFS clocks and XO on in s2idle (upstream bug) | blocks XO shutdown |
| `1291`–`1293` AudioReach suspend | an open PCM keeps the ADSP out of power collapse all night | sleep drain with a game's stream open |
| `1350`–`1352` a6xx GMU HFI fixes | HFI IRQ ate GMU replies: `GX_BW_PERF_VOTE timed out`, GPU freeze | our `fenced register write` / GMU errors |
| `1384`, `1385` | review fixes on top of our `1006` (geni) and `1010` (UFS) | correctness |

- `1170` (battmgr without a wakeup source) doesn't apply: it conflicts with our `9003`/`9005`.
- Kettle **dropped `0502`** (IPCC masked in suspend). With the mailbox masked, the charger stops drawing power about 5 min into s2idle. That's our "not charging after sleep" bug; `9005` already keeps IPCC live on the Thor.
- Kettle gamescope `0021`: a 120 Hz UI holds a 7.8 GB/s display vote, so DDR sits at 1555 MHz while idle. Asgard Home's top screen runs at 120 Hz.
- Still unexplained: the 1555 MHz DDR floor with both screens off and asleep (no Linux vote above 547 MHz).
- **Charger, compared (2026-10-11):**
  - **IPCC in sleep:** our `9005` (live on the Thor), Kettle (dropped `0502`) and Armada `0504` (live in s2idle, masked only for s2ram) agree.
  - **Charge limit:** our `9003` (AYN vendor property 16) is ignored by the firmware. Kettle `1190` / Armada `0903` set the fast-charge current (`BATT_CHG_CTRL_LIM`) instead, as `constant_charge_current`, and a daemon writes 0 at the limit. Read on the Thor too (4.68 A max). **Port this to replace `9003`.**
  - **battmgr wakeups:** Kettle `1170` drops battmgr's wakeup source; while charging, its notifications otherwise end s2idle within minutes. Unplugged sleeps here last hours, but sleep *while charging* is unmeasured. Needs a hand port (conflicts with `9003`).
  - **Unplug while asleep:** Armada `0519` clears the USB role for charger-only partners (otherwise a hang on unplug while asleep). Our `9005` fixed our reset differently (freezable wq).
  - **`95-thor-charge-fix`** logs "stuck" and rebinds UCSI after *every* unplugged wake (no partner looks the same as unplugged). With `9005` it may be obsolete.
