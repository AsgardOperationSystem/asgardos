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
- ✅ **AYN button → Thor Panel** (status tiles, fan modes, touch); a fixed fan speed now survives game launches.
- ✅ **OLED idle blank** (timeout in Settings), **battery logger**, **speaker DSP**, **CPU clock cap**, **hostname**.
- ✅ **melonDS** two-window layout without the Qt menu bar.
- ✅ **Gyro step 2:** the ADSP sensor core's QMI service (svc 400) comes up (FastRPC heap + hexagonrpcd).
- ✅ **Gyro step 3:** accel and gyro stream from the sensor core over QMI/QRTR (`ssc.py`, ~110 Hz each).
- 🧪 **Gyro step 4:** `asgard-motiond` serves them as a DSU (cemuhook) motion source on 127.0.0.1:26760, and
  Azahar uses it while it runs (`0016`). Axis directions still to be tuned in games (`asgard.motion_map`).

### In progress / untested
- **In-game menu (Home tap):** plumbing verified (command FIFO, virtual keyboard); not yet tried inside a game.
- **lowerdeck touch fix** (GB/GBA bottom-screen companion): tested in code, waiting for a try on the device.
- **Boot splash** ("ASGARD"): compiles; shows from the next image.
- **Thor Panel** labels don't scale well; a rebuild in Asgard Home's style is planned.
- Shaders, ratios and other per-game overrides still open the classic (SDL) screen.
- **asgard.yml:** self-test passes; not yet applied on a real boot.
- **hexagonrpc package:** not yet built through ROCKNIX's cargo flow (the Thor runs a separate cross-build).
- **Sleep drain:** the SoC rails (`aosd`/`cxsd`/`ddr`) still never collapse; the smp2p sleepstate driver meant to
  help is unmeasured.
- Our own scraper (ScreenScraper, with an Asgard developer ID kept out of the repo).
- **Steam:** back in the image (Valve's native ARM64 client in gamescope, x86 games through FEX and Proton ARM64).
  First run installs it with ROCKNIX's Install Steam (`0015` fixes it on the image's grep); games still untested.

### Known broken / limitations
- **Charge limit (`9003`) doesn't work:** the threshold reads back 0 and charging continues past 80 %. Thor Settings →
  System → Charge limit (80 % / Off) already stores the choice and applies it at boot, for when the kernel side works.
- **Pokémon Alpha Sapphire at auto 3DS resolution freezes the Thor** on Vulkan (`dpu_encoder_frame_done_timeout`):
  a GPU/display hang below Azahar. Workaround: that game at 2× (per-game `resolution_scale`). Azahar 2126.2 is
  kept but does **not** fix it (correction to !13).
- **Steam** isn't in the image (FEX thunks don't build).
- **thor-sensorspd** is stopped for sleep and not restarted after resume; whether the sensor PD survives sleep is
  untested.
- Once, the Thor didn't charge after a 4 h sleep until a reboot (cause unknown; the battery logger now records USB
  and charging state).
- Occasional `fenced register write (0x8a1)` from the GPU; no hang seen.
- SD SDR104: Thorch keeps UHS off as unstable; watch for mmc errors after sleep.
- No locale generation for `system.language` (ROCKNIX ES did it).

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
| Charge limit (`9003`) | **Not working yet:** the ADSP ignores the threshold request. |
| Azahar 2126.2 (`0005`) | Newer Azahar, kept by choice; it does **not** fix the Alpha Sapphire freeze (see Status). |
| No Steam (`0006`) | FEX-Emu's 32-bit thunks fail to build with GCC 16.2, breaking the image build. |
| melonDS menu bar (`0007`) | In two-window mode melonDS showed its Qt menu bar on one screen. |
| asgard package + boot tuning (`0008`) | Hostname, USB autosuspend, charge limit, CPU clock cap at every boot. |
| asgard.yml | ROCKNIX preconfigures Wi-Fi and keys by baking them into the image; Asgard keeps them in a file next to it. |
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
| Motion server (`asgard-motiond`, `0016`) | Gyro steps 3–4: accel/gyro as a DSU motion source; Azahar's 3DS motion input. |
| Trophies tab | RetroAchievements progress per game: ROMs hashed like RA does (rcheevos), matched through RA's Web API. |
