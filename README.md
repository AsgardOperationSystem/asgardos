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

**No Asgard image has been booted yet**; the first build is running. ✅ below means verified on the Thor running
the ROCKNIX PR #3126 build with the same changes applied by hand, which is what Asgard packages. The packaged
form of each is untested until the first image boots.

### Working
- ✅ **Sleep/resume (s2idle):** lid close in the menu and 10+ min asleep mid-game both resume cleanly; the gamepad
  re-handshakes on the first try. CPU cluster reaches `cluster_sleep_1`. (PR #3126, `0001`, CPU0 idle quirk,
  regulator mem states, PCIe suspend OPP, USB autosuspend, rsinput `1023`)
- ✅ **Storage:** SD at UHS-I SDR104 (76.8 MB/s), UFS at HS-G5 (2.6–2.8 GB/s).
- ✅ **OLED Ultra Black** on the top panel.
- ✅ **Bottom screen:** landscape rotation, dual-screen window rules, display sleep hook (3/3 sleeps).
- ✅ **OLED idle blank**, **battery logger**, **speaker DSP**, **CPU clock cap**, **hostname**.
- ✅ **Thor Settings** and **AYN button → Thor Panel** (Home tap opens the emulator menu).
- ✅ **melonDS** two-window layout without the Qt menu bar (verified as a runtime override; the patch form is new).
- ✅ **Gyro step 2:** the ADSP sensor core's QMI service (svc 400) comes up (FastRPC heap + hexagonrpcd).

### In progress / untested
- **Asgard Home (frontend):** renders correctly on the desktop and on the Thor's GPU (offscreen), never run live on
  the device; launching a game from it is untested. Missing: trophies/profile/apps tabs, Details/Menu/favourites,
  sounds, system artwork, our own scraper.
- **Booting without ROCKNIX ES** (own `essway.service` + `start_frontend.sh`): untested.
- **asgard.yml:** self-test passes; never applied on a real boot.
- **hexagonrpc package:** not yet built through ROCKNIX's cargo flow (the Thor runs a separate cross-build).
- **Gyro steps 3–4:** stream accel/gyro from the sensor core and feed InputPlumber's DualSense motion, so Azahar
  (3DS) sees a gyro. Not started.
- **Sleep drain:** the SoC rails (`aosd`/`cxsd`/`ddr`) still never collapse; the smp2p sleepstate driver meant to
  help is unmeasured.

### Known broken / limitations
- **Charge limit (`9003`) doesn't work:** the threshold reads back 0 and charging continues past 80 %.
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
| ADSP sensors PD server (`hexagonrpc`) | Gyro step 2: starts the sensor core's QMI service; the readings aren't streamed to games yet. |
