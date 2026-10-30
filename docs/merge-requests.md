# Merge requests (2026-10-09 to 10-10)

The merge requests of the old project `asgardos/asgardos`, copied here before it was deleted (2026-10-30). Each one is a change on top of ROCKNIX: what was broken, why, and what changed. The commit links go to the merge commit in this repo. Later changes are ordinary commits; their messages carry the same.

| ! | Title | Merged |
|---|---|---|
| [!1](#mr-1) | Carry ROCKNIX PR #3126: SM8550 deep suspend/resume | 2026-10-09 |
| [!2](#mr-2) | SM8550 cmdline: s2idle and fw_devlink sync_state timeout | 2026-10-09 |
| [!3](#mr-3) | Thor quirk: re-enable CPU0 idle state1 | 2026-10-09 |
| [!4](#mr-4) | Apply regulator suspend states in s2idle; keep L15B in LPM | 2026-10-09 |
| [!5](#mr-5) | PCIe: keep a minimal DDR/LLCC vote in s2idle (suspend OPP) | 2026-10-09 |
| [!6](#mr-6) | SM8550: runtime-autosuspend the primary USB controller | 2026-10-09 |
| [!7](#mr-7) | ADSP smp2p sleepstate: tell the ADSP when the CPUs sleep (experimental) | 2026-10-09 |
| [!8](#mr-8) | rsinput: parse oversized RX chunks (gamepad dead after resume) | 2026-10-09 |
| [!9](#mr-9) | Thor DT: enable UHS-I SDR104 on the SD slot | 2026-10-09 |
| [!10](#mr-10) | UFS: map SM8550's 300 MHz UniPro clock to HS-G5 | 2026-10-09 |
| [!11](#mr-11) | ICNA3520 panel: enable Ultra Black | 2026-10-09 |
| [!12](#mr-12) | qcom_battmgr: AYN Thor charge limit (not working yet) | 2026-10-09 |
| [!13](#mr-13) | Azahar 2126.0 → 2126.2 (HD texture pack crash / hard lock) | 2026-10-09 |
| [!14](#mr-14) | SM8550: drop Steam from the image (FEX thunks don't build) | 2026-10-09 |
| [!15](#mr-15) | melonDS: hide the Qt menu bar in two-window layouts | 2026-10-09 |
| [!16](#mr-16) | Add the asgard package: Thor boot tuning | 2026-10-09 |
| [!17](#mr-17) | asgard.yml: personal settings outside the image | 2026-10-09 |
| [!18](#mr-18) | Display sleep hook: restore only the screens that were on | 2026-10-09 |
| [!19](#mr-19) | Bottom screen: landscape rotation and dual-screen window rules | 2026-10-09 |
| [!20](#mr-20) | OLED guard: screens off after 5 minutes without input | 2026-10-09 |
| [!21](#mr-21) | Battery logger for sleep drain and charging diagnostics | 2026-10-09 |
| [!22](#mr-22) | Speaker DSP: the Android "Thor Speakers" EQ as a PipeWire filter chain | 2026-10-09 |
| [!23](#mr-23) | Thor Settings: the system menus, controller-driven | 2026-10-09 |
| [!24](#mr-24) | AYN button → Thor Panel; Home tap opens the emulator menu | 2026-10-09 |
| [!25](#mr-25) | Asgard Home: iiSU-style dual-screen frontend | 2026-10-09 |
| [!26](#mr-26) | Boot into Asgard Home; drop ROCKNIX ES | 2026-10-09 |
| [!27](#mr-27) | Thor DT: FastRPC remote heap for the ADSP sensors PD | 2026-10-09 |
| [!28](#mr-28) | Gyro step 2: ADSP sensors PD server (hexagonrpcd) | 2026-10-09 |
| [!29](#mr-29) | README: status (working / in progress / broken) | 2026-10-09 |
| [!30](#mr-30) | README: move the sensors root over on the first Asgard boot | 2026-10-09 |
| [!31](#mr-31) | Trophies tab: RetroAchievements | 2026-10-09 |
| [!32](#mr-32) | Thor Settings: charge limit 80 % / Off | 2026-10-10 |
| [!33](#mr-33) | First boot fixes: sound, boot suspend, d-pad, game screens, services; X screens off, touch, faster trophies | 2026-10-10 |
| [!34](#mr-34) | Frontend polish: system art, Start/Select, emulator choice, Thor Panel fan control | 2026-10-10 |
| [!35](#mr-35) | Top screen stays lit: window placement and screens-off recovery | 2026-10-10 |
| [!36](#mr-36) | Volume/brightness slider OSD | 2026-10-10 |
| [!37](#mr-37) | Asgard boot splash | 2026-10-10 |
| [!38](#mr-38) | Thor Panel on top of the frontend | 2026-10-10 |
| [!39](#mr-39) | Fixed fan speed survives game launches | 2026-10-10 |
| [!40](#mr-40) | Azahar: HD texture packs on by default | 2026-10-10 |
| [!41](#mr-41) | Fewer modesets around game launches | 2026-10-10 |
| [!42](#mr-42) | build.sh stage: copy the update safely | 2026-10-10 |
| [!43](#mr-43) | README: status as of 2026-10-10 | 2026-10-10 |
| [!44](#mr-44) | README: status 2026-10-10 (afternoon) | 2026-10-10 |
| [!45](#mr-45) | README: confirmed items, new ones to try | 2026-10-10 |

<a id="mr-1"></a>
## !1: Carry ROCKNIX PR #3126: SM8550 deep suspend/resume

Merged 2026-10-09 from `rocknix-pr3126`, commit [`ea081967a1`](https://github.com/AsgardOperationSystem/asgardos/commit/ea081967a1c98f33279febf740d27b5f8b483a80).

#### Problem
ROCKNIX `next` has no working suspend/resume on SM8550: the gamepad MCU, UFS, Wi-Fi and the USB role break or hang around sleep.

#### Fix
Carry [ROCKNIX PR #3126](https://github.com/ROCKNIX/distribution/pull/3126) (open upstream) as `patches/0000`, rebased onto `next` `7cffc96`. The SM8550 cmdline hunk is left to patch 0001, because `next` changed that line.

#### When to remove
Once #3126 is merged and the `rocknix` pin moves past it.

<a id="mr-2"></a>
## !2: SM8550 cmdline: s2idle and fw_devlink sync_state timeout

Merged 2026-10-09 from `sm8550-s2idle-cmdline`, commit [`ef412aa62d`](https://github.com/AsgardOperationSystem/asgardos/commit/ef412aa62da162640cddd5457a98e8eff7f6a4e6).

#### Problem
- With PSCI `deep` the last CPU never reached `cluster_sleep_1`.
- `fw_devlink.strict=1` left `gcc`/`gpu_cc` `sync_state()` waiting forever on the unbound GPU GMU, so GPU power domains stayed on.

#### Fix
`mem_sleep_default=s2idle`, `fw_devlink.strict=0 fw_devlink.sync_state=timeout`, and PR #3126's `ufshcd_core.uic_cmd_timeout=3000` (missing from `next`'s line).

#### Result
`sync_state()` is forced at ~22 s; GPU GDSCs reach 0 users; DDR hits 547 MHz in sleep. Awake idle ~524 → ~454 mA.

<a id="mr-3"></a>
## !3: Thor quirk: re-enable CPU0 idle state1

Merged 2026-10-09 from `thor-cpu0-idle`, commit [`1c0e467b3c`](https://github.com/AsgardOperationSystem/asgardos/commit/1c0e467b3c91e9b799fea93574ff26e557056059).

#### Problem
ROCKNIX quirk `096-cpuidle` disables CPU0 idle state1 ("GMU issues"). With CPU0 stuck in WFI the cluster never powers down: s2idle never reaches `cluster_sleep_1`, watchdogs kill logind/journald at resume, and Wi-Fi stays blocked.

#### Fix
A Thor device quirk (runs after the platform quirks) re-enables it.

#### Result
254 s lid close: cluster S1 entered, apss asleep 246 s.

#### Watch
GPU hangs / `fenced register write (0x8a1)`, the reason ROCKNIX added 096.

<a id="mr-4"></a>
## !4: Apply regulator suspend states in s2idle; keep L15B in LPM

Merged 2026-10-09 from `s2idle-regulator-mem-state`, commit [`df953b9c5c`](https://github.com/AsgardOperationSystem/asgardos/commit/df953b9c5c3ac60fdd8c961d96ad96ddc2b072a3).

#### Problem
The regulator core applies DT `regulator-state-mem` only for s2ram, but the Thor sleeps with s2idle, so no rail changed state in sleep.

#### Fix
- Kernel `0219` (from [Thorch #19](https://github.com/thorch-os/thorch/pull/19)) applies the mem state in s2idle.
- Patch `0002`: L15B (1.8 V) in LPM during suspend.

#### Note
This makes PR #3126's `bob2` off-in-suspend real: the gamepad MCU powers off in sleep; it is re-handshaked on resume (rsinput fix 1023).

<a id="mr-5"></a>
## !5: PCIe: keep a minimal DDR/LLCC vote in s2idle (suspend OPP)

Merged 2026-10-09 from `pcie-suspend-opp`, commit [`6b3d6b29e4`](https://github.com/AsgardOperationSystem/asgardos/commit/6b3d6b29e492ba325148ba1a644ad55156ab6e6c).

#### Problem
Dropping the PCIe interconnect vote completely in sleep lets AOP sleep but the firmware never returns to Linux (hang on wake, seen on the Thor and RP6). Leaving the full vote keeps DDR up.

#### Fix
Kernel `0220` + `0221` from [Thorch #19](https://github.com/thorch-os/thorch/pull/19): a 5 MB/s suspend OPP used in s2idle.

#### Result
`opp:1-1 suspend: Y` in debugfs; sleep/wake cycles are stable.

<a id="mr-6"></a>
## !6: SM8550: runtime-autosuspend the primary USB controller

Merged 2026-10-09 from `usb-autosuspend`, commit [`120b71941a`](https://github.com/AsgardOperationSystem/asgardos/commit/120b71941a23be9ff154f2ef1c025191328828ae).

#### Problem
`a600000.usb` stayed runtime-active while idle and held a 1 GB/s USB→DDR interconnect vote.

#### Fix
udev rule: `power/control=auto` for it (from [Thorch #19](https://github.com/thorch-os/thorch/pull/19)).

<a id="mr-7"></a>
## !7: ADSP smp2p sleepstate: tell the ADSP when the CPUs sleep (experimental)

Merged 2026-10-09 from `adsp-smp2p-sleepstate`, commit [`aa9deb87cc`](https://github.com/AsgardOperationSystem/asgardos/commit/aa9deb87cccb92f140888f9654b4a6b086641eb0).

#### Problem
Even with PR #3126 the SoC rails never collapse in sleep (`aosd`/`cxsd`/`ddr` stay 0, ~4–5 %/h). Android signals CPU sleep to the ADSP over smp2p `sleepstate`; mainline has no driver.

#### Fix
- Kernel `9000`: port of Qualcomm/OnePlus `smp2p_sleepstate` to 7.2 (two downstream bugs fixed).
- Patch `0003`: Thor DT nodes + `CONFIG_QCOM_SMP2P_SLEEPSTATE=y`.

#### Status
Experimental: effect on sleep current unmeasured.

<a id="mr-8"></a>
## !8: rsinput: parse oversized RX chunks (gamepad dead after resume)

Merged 2026-10-09 from `rsinput-oversized-rx`, commit [`c5453b9254`](https://github.com/AsgardOperationSystem/asgardos/commit/c5453b925466796f828076afc413ebc02f6b2046).

#### Problem
Gamepad dead after resume: `rsinput_resume returns -110` (3/3 handshakes) with `RX buffer overflow` ~1/s. After resume the UART hands the driver >1024 bytes at once, and it dropped the whole chunk, version reply included.

#### Fix
Kernel `1023`: parse oversized chunks frame by frame.

#### Result
Handshake first try on resume, 0 overflows; menu and mid-game sleep pass.

<a id="mr-9"></a>
## !9: Thor DT: enable UHS-I SDR104 on the SD slot

Merged 2026-10-09 from `sd-uhs-sdr104`, commit [`76b95ef449`](https://github.com/AsgardOperationSystem/asgardos/commit/76b95ef44999cf3152adab359773ad9954fc72c7).

#### Problem
`sdhci-caps-mask = <0x3 0x0>` masked SDR50/SDR104, so the card ran 3.3 V high-speed: **16.6 MB/s**.

#### Fix
Patch `0004` removes the mask.

#### Result
`UHS-I speed SDR104`, 1 GB direct read **76.8 MB/s**, checksums match, no mmc errors.

#### Caveat
Thorch keeps the mask on purpose ("unstable UHS modes"); watch for mmc errors after sleep.

<a id="mr-10"></a>
## !10: UFS: map SM8550's 300 MHz UniPro clock to HS-G5

Merged 2026-10-09 from `ufs-hs-g5`, commit [`8ce3096272`](https://github.com/AsgardOperationSystem/asgardos/commit/8ce30962724afe1b4279956d39cad30a7708152a).

#### Problem
SM8550's 300 MHz UniPro clock was mapped to HS-G4, so the UFS 4.0 storage never ran at G5.

#### Fix
Kernel `1024` (from Thorch's custom-kernel work).

#### Result
8 GiB direct read: **1.5 → 2.6–2.8 GB/s**.

<a id="mr-11"></a>
## !11: ICNA3520 panel: enable Ultra Black

Merged 2026-10-09 from `oled-ultra-black`, commit [`6c62b4e54e`](https://github.com/AsgardOperationSystem/asgardos/commit/6c62b4e54e91806989a0cfc416290c33199d8997).

#### Problem
Dark backgrounds on the top OLED show colour shift/mura at low brightness. Android fixes this with AYN's hidden "OLED Ultra Black Mode"; Linux never sent it.

#### Fix
Kernel `9001`: the ICNA3520 driver sends AYN's enhance_color sequence (9F/B7/B8).

<a id="mr-12"></a>
## !12: qcom_battmgr: AYN Thor charge limit (not working yet)

Merged 2026-10-09 from `charge-limit`, commit [`a10f48096d`](https://github.com/AsgardOperationSystem/asgardos/commit/a10f48096d4fd288e967aaaaa303aebdf152bbe3).

#### Goal
An 80 % charge limit like AYN's Android setting.

#### Change
Kernel `9003`: send AYN's battery property 16 request (what Android's charger module does) instead of mainline's ignored `CHG_CTRL_LIMIT_EN`.

#### Status
**Not working yet:** the threshold reads back 0 and charging continues past 80 %. The failure is silent; next step is logging the request's return code and reply.

<a id="mr-13"></a>
## !13: Azahar 2126.0 → 2126.2 (HD texture pack crash / hard lock)

Merged 2026-10-09 from `azahar-2126.2`, commit [`902cd48ce3`](https://github.com/AsgardOperationSystem/asgardos/commit/902cd48ce3d0d66543101f748a49be104fc373c1).

> **Correction (2026-10-10):** 2126.2 does **not** fix the Alpha Sapphire freeze. The device notes had already found that azahar#2407 isn't the fix: it's a resolution-dependent GPU/display hang below Azahar (`dpu_encoder_frame_done_timeout`), still present on 2126.2 at auto resolution. Workaround: that game at 2× (per-game `resolution_scale`). 2126.2 is kept by choice. See the README's Status section.

#### Original description
HD texture packs (e.g. Alpha Sapphire) crashed Azahar 2126.0 ~8 s in (`Trying to unregister an already unregistered surface`); on Vulkan the whole Thor hard-locked.

Bump to 2126.2 (azahar#2407, texture-cache use-after-free) and rebase ROCKNIX's patch 0003.

<a id="mr-14"></a>
## !14: SM8550: drop Steam from the image (FEX thunks don't build)

Merged 2026-10-09 from `drop-steam`, commit [`fe0080b49f`](https://github.com/AsgardOperationSystem/asgardos/commit/fe0080b49f8479fc3be1eb373155c0a00506656c).

#### Problem
FEX-Emu's 32-bit thunks fail with GCC 16.2 (`'long double' does not match '__float128'`), failing the SM8550 image build.

#### Fix
Leave `steam` out of the SM8550 emulator list until FEX builds again.

<a id="mr-15"></a>
## !15: melonDS: hide the Qt menu bar in two-window layouts

Merged 2026-10-09 from `melonds-menu-bar`, commit [`e27684b115`](https://github.com/AsgardOperationSystem/asgardos/commit/e27684b1159f40bc5b8b937c521bd2066a3807d5).

#### Problem
In two-window layouts melonDS shows its Qt menu bar on the window it doesn't fullscreen; there's no setting, and F11 doesn't react to uinput.

#### Fix
A stylesheet collapsing `QMenuBar`, passed with `-stylesheet` from `start_melonds.sh`.

<a id="mr-16"></a>
## !16: Add the asgard package: Thor boot tuning

Merged 2026-10-09 from `asgard-package-boot-tuning`, commit [`289356282f`](https://github.com/AsgardOperationSystem/asgardos/commit/289356282f8d3fe35714a79f0bd94fa81228e32f).

#### What
- Patch `0008`: a new `asgard` package in the SM8550 image (scripts, services, apps of this OS).
- `090-asgard-tuning` at every boot: apply `system.hostname` (read-only `/etc/hostname` says ROCKNIX), USB autosuspend on all DWC3 controllers, charge limit (`asgard.charge_limit`, default 80), CPU clock cap ~75 % (`asgard.cpu_cap`, 0 = off).

#### Why
ROCKNIX never sets a hostname from its own setting nor caps clocks; idle sat at 45–46 °C before the cap.

<a id="mr-17"></a>
## !17: asgard.yml: personal settings outside the image

Merged 2026-10-09 from `asgard-yml`, commit [`40ce3483bd`](https://github.com/AsgardOperationSystem/asgardos/commit/40ce3483bdacc7ce7f284fe1b1425ba86c37536f).

#### Problem
ROCKNIX preconfigures images with `LOCAL_WIFI_SSID`/`LOCAL_WIFI_KEY`/`LOCAL_SSH_KEYS_FILE`, which bake secrets into the image.

#### Fix
- `asgard.yml` on the boot partition, applied at every boot by `asgard_config.py`: **image defaults < asgard.yml < the user's own changes**.
- `inject-config.sh` puts it on a local copy of an image; `asgard.yml.example` documents the keys.
- `build.sh` strips the `LOCAL_*` variables.

#### Test
`asgard_config.py --test`

<a id="mr-18"></a>
## !18: Display sleep hook: restore only the screens that were on

Merged 2026-10-09 from `display-sleep-hook`, commit [`ca41afc8c6`](https://github.com/AsgardOperationSystem/asgardos/commit/ca41afc8c6bb16a1360332e79526e6fa69590d68).

#### Problem
After resume the bottom panel came back on (black) even if it was off before sleep.

#### Fix
`thor-display-sleep.service`: before sleep record which outputs are powered and turn all off; after resume restore only those and refocus the top screen.

#### Result
3/3 sleeps clean.

<a id="mr-19"></a>
## !19: Bottom screen: landscape rotation and dual-screen window rules

Merged 2026-10-09 from `bottom-screen-rotation`, commit [`a3b1713d45`](https://github.com/AsgardOperationSystem/asgardos/commit/a3b1713d454393bdfde6a836d949780052a3b9bc).

#### Problem
- The bottom panel (DSI-1) stayed portrait 1080x1240.
- Games opened on half the top screen, RetroArch reopened on the bottom screen after Close Content, and touches on the bottom screen stole focus (d-pad "dead").

#### Fix
A `sway.service` drop-in runs `thor-sway-rotate.sh`, which appends the rotation and the window rules to ROCKNIX's generated sway config.

<a id="mr-20"></a>
## !20: OLED guard: screens off after 5 minutes without input

Merged 2026-10-09 from `oled-idle-blank`, commit [`16866e22c7`](https://github.com/AsgardOperationSystem/asgardos/commit/16866e22c788b5c65ac399637d184eb48c0ce324).

#### Problem
Both screens are OLED; a static menu left on burns in.

#### Fix
`thor-idle-blank.service`: outputs off after 5 min without input, back on with any input.

<a id="mr-21"></a>
## !21: Battery logger for sleep drain and charging diagnostics

Merged 2026-10-09 from `battery-logger`, commit [`481f16ceac`](https://github.com/AsgardOperationSystem/asgardos/commit/481f16ceacb075213a1da4ebb5d99c577b5412f7).

#### Problem
No way to measure sleep drain, and a not-charging-after-sleep case left no data (journal is in RAM).

#### Fix
`thor-battery-log.service`: one CSV line every 30 s (charge, current, clocks, backlights, suspend count, running app, USB/charging state). Gaps = sleep.

<a id="mr-22"></a>
## !22: Speaker DSP: the Android "Thor Speakers" EQ as a PipeWire filter chain

Merged 2026-10-09 from `speaker-dsp`, commit [`e8db6816bf`](https://github.com/AsgardOperationSystem/asgardos/commit/e8db6816bf24611e8570a6d6b5beddd6c9c2d2d9).

#### Problem
Without Android's JamesDSP preset the speakers sounded thin and harsh.

#### Fix
PipeWire filter chains: the "Thor Speakers" 15-band EQ for the speakers, a loudness EQ + light widening for headphones.

<a id="mr-23"></a>
## !23: Thor Settings: the system menus, controller-driven

Merged 2026-10-09 from `thor-settings`, commit [`e867a96fc3`](https://github.com/AsgardOperationSystem/asgardos/commit/e867a96fc3fc84793d859ffc675981861e67b525).

#### Problem
ROCKNIX keeps every system setting inside its EmulationStation, which Asgard replaces.

#### Fix
Thor Settings: Game/System Options (from ROCKNIX's `es_features.cfg`), Wi-Fi, Bluetooth, LEDs, RetroAchievements, Updates, System. Same `system.cfg` keys and ROCKNIX scripts. Python stdlib + ctypes SDL2, no new deps.

#### Test
`test_thor_settings.py` on the device.

<a id="mr-24"></a>
## !24: AYN button → Thor Panel; Home tap opens the emulator menu

Merged 2026-10-09 from `ayn-button-thor-panel`, commit [`0aa8e69acf`](https://github.com/AsgardOperationSystem/asgardos/commit/0aa8e69acf5fe3e2f1fd5c8d191be3f78e28901a).

#### Problem
The AYN key did nothing on Linux, and there was no one-button way into an emulator's menu.

#### Fix
`thor-ayn-button.service`: AYN key toggles **Thor Panel** (AYN-style bottom-screen panel: quick toggles, stats, gauges); a Home tap opens RetroArch's menu (UDP), sends Esc to standalone emulators, or exits the app. `playlog.py` keeps playtime.

<a id="mr-25"></a>
## !25: Asgard Home: iiSU-style dual-screen frontend

Merged 2026-10-09 from `asgard-home`, commit [`45c1bc3b41`](https://github.com/AsgardOperationSystem/asgardos/commit/45c1bc3b4182764ec072cd2523cbd54db4f33613).

#### Why
ROCKNIX ES looks dated and isn't built for the Thor's two screens. Asgard Home is our own frontend, styled after iiSU's dual-screen home (own code and artwork).

#### What
- **Backend:** library from ROCKNIX's `es_systems.cfg` + ROM dirs + scraped media, playtime, battery, launching through `runemu.sh`; the pad read from evdev in the Thor's Nintendo layout.
- **UI:** top screen hero card + status + hints; bottom screen dock + tile grid with "Jump back in!".
- **Dev loop:** `frontend/dev.sh shot|thor ["keys"]` renders both screens offscreen (desktop fixture or on the Thor's GPU).

#### Not yet
Trophies/profile/apps tabs, Details/Menu/favourites, sounds, system artwork, our own scraper.

<a id="mr-26"></a>
## !26: Boot into Asgard Home; drop ROCKNIX ES

Merged 2026-10-09 from `boot-asgard-home`, commit [`fbfef75dc7`](https://github.com/AsgardOperationSystem/asgardos/commit/fbfef75dc78a96f03e5ad10b883447bd5d8f04e2).

#### What
- Patch `0009`: no ROCKNIX ES / es-themes in the image.
- `essway.service` (the unit name ROCKNIX's scripts use for the frontend) now starts `asgard-home` via `start_frontend.sh`.
- Sway rule: Asgard Home's bottom window fills the bottom screen.

#### Not carried over
Locale generation for `system.language`; ROCKNIX's sway rules keyed to ES's app_id.

<a id="mr-27"></a>
## !27: Thor DT: FastRPC remote heap for the ADSP sensors PD

Merged 2026-10-09 from `thor-dt-fastrpc-heap`, commit [`38e445ca37`](https://github.com/AsgardOperationSystem/asgardos/commit/38e445ca3713ada477c0fb2ed01755ebd5a31259).

#### Problem
Gyro, step 2: the Thor's IMU (SH5001) is behind the ADSP's sensor core. With a FastRPC server attached, the sensors PD rewrote its registry but its QMI service (svc 400) never registered: `no reserved DMA memory for FASTRPC`.

#### Fix
Patch `0010`: a 16 MiB reusable `shared-dma-pool` below 4 GiB (`fastrpc_mem`) as the ADSP FastRPC `memory-region`, same as the SM8550 Xiaomi Pad 6S Pro port ([lzxcr/arch-xiaomi-sheng](https://github.com/lzxcr/arch-xiaomi-sheng)).

#### Result
`assigned reserved memory node fastrpc` at boot; svc 400 appears within seconds of the sensors server starting; audio unaffected.

<a id="mr-28"></a>
## !28: Gyro step 2: ADSP sensors PD server (hexagonrpcd)

Merged 2026-10-09 from `adsp-sensors-pd`, commit [`2a8cdec727`](https://github.com/AsgardOperationSystem/asgardos/commit/2a8cdec72783fe9ef4a18b2cd0f47b56c8637e68).

#### Problem
Gyro step 2: the SH5001 gyro/accel live in the ADSP's sensor core, whose QMI service (svc 400) only starts when a userspace FastRPC server serves the sensors PD its files (Android's `sscrpcd`). Nothing did that on Linux.

#### Fix
- Package `hexagonrpc`: [lzxcr/hexagonrpc](https://github.com/lzxcr/hexagonrpc) `db659bd` + the 3 fixes from [arch-xiaomi-sheng](https://github.com/lzxcr/arch-xiaomi-sheng) (SM8550 Xiaomi Pad 6S Pro).
- `thor-sensorspd.service`: runs `hexagonrpcd` on `/dev/fastrpc-adsp` against `/storage/.config/asgard/sensors-root` (Android blobs + this unit's calibration, supplied per device, not in the image; README explains the layout).

#### Result
With the FastRPC heap (!27): svc 400 on node 5 within seconds.

#### Open
- Not restarted after resume (`Conflicts=suspend.target`); sleep survival untested.
- ROCKNIX cargo build of the package untested (the Thor runs a `rust:1-bookworm` cross-build of the same source).
- Steps 3–4: stream readings, feed InputPlumber's DualSense motion → 3DS gyro.

<a id="mr-29"></a>
## !29: README: status (working / in progress / broken)

Merged 2026-10-09 from `readme-status`, commit [`54ad54bbdc`](https://github.com/AsgardOperationSystem/asgardos/commit/54ad54bbdc7aacb19dab20c1e43e458b3ff536ed).

Adds a **Status** section to the README: verified on the Thor / in progress or untested / known broken. No Asgard image has booted yet, so "verified" means on the ROCKNIX PR #3126 build with the same changes applied by hand.

Also corrects the Azahar row: 2126.2 does **not** fix the Alpha Sapphire freeze (a resolution-dependent GPU/display hang below Azahar; workaround 2× for that game). !13 credited azahar#2407 for it.

<a id="mr-30"></a>
## !30: README: move the sensors root over on the first Asgard boot

Merged 2026-10-09 from `readme-sensors-migration`, commit [`7ceafe5b90`](https://github.com/AsgardOperationSystem/asgardos/commit/7ceafe5b908f67597026d9555815e26c0f133523).

Adds the one-time migration step to the README's gyro section: copy the Thor's existing root (`/storage/.config/thor/sensors/root2`) to `/storage/.config/asgard/sensors-root` on the first Asgard boot, then start `thor-sensorspd`.

<a id="mr-31"></a>
## !31: Trophies tab: RetroAchievements

Merged 2026-10-09 from `trophies`, commit [`1a6c5581ec`](https://github.com/AsgardOperationSystem/asgardos/commit/1a6c5581ecfb4244fe601e219fb941d846375430).

#### What
The **Trophies** tab: RetroAchievements progress for the games on the device.

- **Matching:** ROMs hashed exactly like RA identifies games (vendored rcheevos v12.5.0 `rhash`, MIT), matched against each console's RA game list (Web API, cached a week). Hashes cached by path + size + mtime; only consoles with sets are hashed.
- **Progress:** `API_GetUserCompletionProgress` for counts, `API_GetGameInfoAndUserProgress` per game for achievements, badges, unlock dates (hardcore marked). One request at a time; offline falls back to the cache; the key never hits the logs.
- **UI:** grid of trophy games (cover, progress bar, earned/total, gold rim when mastered) → A opens the badges (greyed while locked); the top card shows set or achievement details.
- **Setup:** `global.retroachievements.webapikey` (retroachievements.org → Settings → Keys) next to the RA login in asgard.yml; without it the tab says what to add.

Also two small fixes: screenshot runs no longer read the physical pad, and tiles no longer error during tab switches.

#### Tested on the Thor (real account)
362 ROMs hashed, 249 matched to RA sets; trophy grid and the 007 TWINE achievement list render with real badges and descriptions. The account has no unlocks yet, so earned counts are all 0.

#### Limits
GameCube `.rvz` can't be hashed (rcheevos); RA has no 3DS sets.

<a id="mr-32"></a>
## !32: Thor Settings: charge limit 80 % / Off

Merged 2026-10-10 from `charge-limit-choice`, commit [`43eaba37d0`](https://github.com/AsgardOperationSystem/asgardos/commit/43eaba37d0c7fb41b17fb6ef6f0b49ef53a83c96).

Thor Settings → System → **Charge limit**: 80 % (default, battery longevity) or Off (charge to 100 %). Stores `asgard.charge_limit` (applied at boot by `090-asgard-tuning`, also settable from asgard.yml) and writes the threshold immediately.

**Known:** kernel patch 9003 doesn't make the firmware honour the threshold yet, so charging still runs to 100 % until that's fixed; the choice is stored and will apply once it does.

<a id="mr-33"></a>
## !33: First boot fixes: sound, boot suspend, d-pad, game screens, services; X screens off, touch, faster trophies

Merged 2026-10-10 from `boot-fixes`, commit [`0321bde6ac`](https://github.com/AsgardOperationSystem/asgardos/commit/0321bde6ac960932e641e41f8819f667772a7054).

#### What the first boot of Asgard OS found, and the fixes (verified on the Thor after reinstalling)

| Problem | Cause | Fix |
|---|---|---|
| No sound card | logind suspended the Thor 3.6 s into boot (lid reads "closed" for a moment; holdoff was 0); the ADSP audio PD timed out mid-init, so the LPASS LPI pinctrl never probed | `HoldoffTimeoutSec=10` shipped in the image |
| Power button needed at boot, top screen dark | same boot suspend; the display sleep hook ran before sway existed | same |
| D-pad dead after a few seconds / after sleep | InputPlumber re-creates the virtual pad (stick calibration restarts it, and on resume); the frontend kept the removed device | reopen the pad on ENODEV, retry until it's back |
| Pokémon X: two black screens | sway focus stayed on the bottom output, the game opened there and the launch had powered it off | focus DSI-2 before launching |
| AYN button / idle blank never started | ordering cycle (WantedBy=multi-user + After=essway) | WantedBy=rocknix.target |
| Gyro server dead after sleep | Conflicts=suspend.target, nothing restarted it | systemd-sleep `post` hook |
| Qt locale warning | nothing set LANG once ROCKNIX ES was gone | `LANG=C.UTF-8` |

Plus three frontend features asked for while testing: **X turns both OLEDs off** (any button wakes), **bottom touchscreen** (tap/tap-to-open, dock tabs, swipe), and **faster grids/trophies** (lazy tile art, single glow, disk-cached web images, achievement lists from cache first).

After reinstalling: 0 suspends at boot, sound card present, all services active, no ordering cycles, the pad reopened by itself after InputPlumber's boot restart.

<a id="mr-34"></a>
## !34: Frontend polish: system art, Start/Select, emulator choice, Thor Panel fan control

Merged 2026-10-10 from `frontend-polish`, commit [`14f920dd7f`](https://github.com/AsgardOperationSystem/asgardos/commit/14f920dd7f925c4a6285d8f78314e4c185301ebb).

Frontend polish asked for while testing the first Asgard boot; installed and checked on the Thor.

- **System artwork** from ROCKNIX's Art Book Next (now an asgard-home dependency): artwork + white logo on system tiles and the top card instead of "3DS"/"GB" text.
- **Start** opens Thor Settings (Game Options on the highlighted game); **Select** flips the top card to details (description, playtime, last played).
- **Home** shows "Jump back in!" + systems only (recent games read as games outside their console folder); the useless **LT/RT** tags are gone.
- **Emulator choice respected**: launches use `<sys>["<file>"]`, then `<sys>`, then global emulator/core from system.cfg, like ROCKNIX's get_setting (your `gba` → retroarch/vba_next now applies).
- **Thor Panel**: fan control on the FAN card (Quiet/Smart/Sport or fixed 30–100 %), Direct Power as a real on/off switch shown purple when on, no bottom bar (Settings + Quit game are tiles), parks Asgard Home's bottom window.
- dev: screenshot mode sizes windows early; logs to stderr.

Not in here: touch still unconfirmed on the device (needs a recorded test), and the iiSU-style Settings/Quick Settings and the 3DS in-game menu are next.

<a id="mr-35"></a>
## !35: Top screen stays lit: window placement and screens-off recovery

Merged 2026-10-10 from `window-placement`, commit [`4aaed260ad`](https://github.com/AsgardOperationSystem/asgardos/commit/4aaed260ad420929fd76434936597327f5c35afc).

#### Top screen dark, bottom lit
Two ways to end up there, both checked on the Thor:
- **Placement:** a new window opens on the focused output; with focus on the bottom screen the frontend's top window mapped on DSI-1 behind the bottom one. sway `assign` rules now pin "Asgard Home" to DSI-2 and "Asgard Home (Bottom)" to DSI-1 on every map.
- **Screens off (X) + re-map:** a restart/game/panel close re-mapped the bottom window, ROCKNIX's "Bottom" rule powered DSI-1 on, nothing powered DSI-2. The frontend now powers DSI-2 on at start and after every game/tool.

Also: `dev.sh thor` uploads beside the running binary (it failed silently over a bind-mounted one), and `ASGARD_DEBUG_INPUT` logs touch/pointer presses, which showed that no touch reaches either window today (real or virtual touchscreen); touch is still under investigation.

<a id="mr-36"></a>
## !36: Volume/brightness slider OSD

Merged 2026-10-10 from `volume-osd`, commit [`3e73221ff5`](https://github.com/AsgardOperationSystem/asgardos/commit/3e73221ff56eb7ea8f1b6920321202f0d7864d53).

Volume and brightness keys now show a slider (a mako progress bar) instead of the "Volume: 70%" text toast. Holding a key moves the same bar instead of stacking notifications.

- `asgard-osd <label> <percent>`: adds its own `[app-name=asgard-osd]` style section to the mako config and replaces its previous notification by ID
- patch 0011: `input_sense` calls it for volume and brightness

Tested live on the Thor with a bind-mounted `input_sense`.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

<a id="mr-37"></a>
## !37: Asgard boot splash

Merged 2026-10-10 from `boot-splash`, commit [`f161e4398e`](https://github.com/AsgardOperationSystem/asgardos/commit/f161e4398e853a0c999c4f9fca70181e0d346ed1).

Boot splash draws "ASGARD" (Nunito Black, OFL) in the aurora purple instead of the ROCKNIX logo.

- `overlay/.../rocknix-splash/patches/0001-asgard-logo.patch`: new path data on the same 1284x500 canvas, generated from the font with fontTools
- drops the `/run/rocknix-splash` marker (flags an unmodified ROCKNIX image; nothing in the image reads it)

Patch applies and compiles on the host; shows on the next image build.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

<a id="mr-38"></a>
## !38: Thor Panel on top of the frontend

Merged 2026-10-10 from `thor-panel-on-top`, commit [`c2fd9f734e`](https://github.com/AsgardOperationSystem/asgardos/commit/c2fd9f734ee11c46a677a9c0a82c04ccf87bfa45).

Thor Panel opened as a half-width tiled window behind Asgard Home's fullscreen bottom window, so the AYN button looked like it did nothing. A sway rule fullscreens it.

Verified live on the Thor (rule applied at runtime; the panel showed on top at 1240 wide).

🤖 Generated with [Claude Code](https://claude.com/claude-code)

<a id="mr-39"></a>
## !39: Fixed fan speed survives game launches

Merged 2026-10-10 from `fan-manual`, commit [`f4035eb417`](https://github.com/AsgardOperationSystem/asgardos/commit/f4035eb41733c774fe3ce0c047c9c6aa6c5723de).

A fixed fan speed chosen in Thor Panel was dropped on every game launch: `runemu.sh` restarts fancontrol, which went back to its curve (the panel showed 75%, the fan sat at 0%).

- `fancontrol.service.d/asgard-fan.conf`: `ExecCondition=/usr/share/asgard/asgard-fan.sh`, which applies `asgard.fan_manual` and skips starting fancontrol
- Thor Panel and 090-asgard-tuning no longer poke the PWM themselves

Verified on the Thor with a runtime drop-in: `systemctl restart fancontrol` -> skipped, pwm1=191.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

<a id="mr-40"></a>
## !40: Azahar: HD texture packs on by default

Merged 2026-10-10 from `azahar-textures`, commit [`e482bbb89a`](https://github.com/AsgardOperationSystem/asgardos/commit/e482bbb89a5f0fb7ad2282a692eeabcf0ccacf65).

Azahar custom textures (HD packs in `load/textures`) are now set on every launch, on by default; `3ds.custom_textures=0` (per system or per game) turns them off. The image default config had them off.

- patch 0012 for `start_azahar.sh`, in the same style as the resolution/CPU options
- sed lines verified on the Thor against the image default qt-config.ini (false -> true)

🤖 Generated with [Claude Code](https://claude.com/claude-code)

<a id="mr-41"></a>
## !41: Fewer modesets around game launches

Merged 2026-10-10 from `screen-modesets`, commit [`fc6ee6ffd7`](https://github.com/AsgardOperationSystem/asgardos/commit/fc6ee6ffd73f88a2c841518a675700e652e0c6d9).

The top panel hung again (`dpu_encoder_frame_done_timeout`, garbled until reboot) as a GBC game started. In about a second: Asgard Home powered the bottom panel off, ROCKNIX powered it back on for lowerdeck, and a sway rule re-rotated it 1.5 s later, while the game's top window committed.

- `thor-bottom-rotate.sh`: rotate DSI-1 only when it isn't landscape (the rules rotated on every bottom window that mapped)
- `thor-bottom-idle-off.sh`: power DSI-1 off 3 s after launch, only if nothing opened there, instead of off-then-on

Both dry-run on the Thor (no-ops in the normal state). The hang is intermittent, so this lowers the odds; it is not proven gone.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

<a id="mr-42"></a>
## !42: build.sh stage: copy the update safely

Merged 2026-10-10 from `safe-stage`, commit [`bfa48bd62a`](https://github.com/AsgardOperationSystem/asgardos/commit/bfa48bd62af1673206724df3f63b5c5abe1acb5d).

A copy of the update cut short by a reboot was taken for an update (the installer rejected it on md5, then that boot hung on the splash). `./build.sh stage` copies to `<name>.tar.part`, checks sha256 on the device, then renames; ROCKNIX's installer only picks up `*.tar`.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

<a id="mr-43"></a>
## !43: README: status as of 2026-10-10

Merged 2026-10-10 from `readme-status`, commit [`9b44436517`](https://github.com/AsgardOperationSystem/asgardos/commit/9b444365170948273d42e2021b5dee9d22eed521).

Status section rewritten for the current state: what is verified on the Thor, what is on the device waiting for a try, what is in progress (Steam research, scraper, Thor Panel), and known limitations.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

<a id="mr-44"></a>
## !44: README: status 2026-10-10 (afternoon)

Merged 2026-10-10 from `readme-2026-10-10b`, commit [`37f89f3666`](https://github.com/AsgardOperationSystem/asgardos/commit/37f89f36665bce4358d696555b6db6b3b9e5aabe).

Status update for the work since the morning builds:

- Steam back and working (native ARM64 client; Install Steam fixed by 0015)
- Gyro step 3 verified; step 4 (DSU motion server for Azahar) on the device
- Volume/brightness slider now an Asgard Home overlay
- Boot animation: KMS retry, 90-degree rotation, "ASGARD OS"
- Steam pad settings across boots, Steam art, RetroArch bottom-screen switch

🤖 Generated with [Claude Code](https://claude.com/claude-code)

<a id="mr-45"></a>
## !45: README: confirmed items, new ones to try

Merged 2026-10-10 from `readme-confirmed`, commit [`d7eef3c3df`](https://github.com/AsgardOperationSystem/asgardos/commit/d7eef3c3df8fda76de4a79ca8328d386a1f40527).

Status after testing on the Thor:

- Confirmed: top-screen grid, tile reordering, gyro step 4 (axis order measured), Steam pad settings, Steam art, 60 Hz, boot splash and update bar on the top panel, Steam inside sway (AYN panel, Home -> Quick Access), Steam games, hexagonrpc package
- New, waiting for a try: in-game menu speed, CPU cap per core type, PC system with Gen1 Recomp, Start on the recent tile
- Top-panel hang: not proven gone

🤖 Generated with [Claude Code](https://claude.com/claude-code)
