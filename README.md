# Asgard OS

An OS for the AYN Thor built on ROCKNIX. ROCKNIX is a pinned submodule and Asgard is a stack of patches and new
files on top of it, so following ROCKNIX is a pin bump plus fixing whichever patch stops applying.

```
rocknix/      ROCKNIX distribution (submodule: branch next, shallow)
patches/      changes to existing ROCKNIX files, applied in order with git apply
overlay/      new files copied over the tree (kernel patches, quirks, packages)
build.sh      prepare rocknix/ and build the image (./build.sh [prepare|upgrade])
inject-config.sh  put your asgard.yml on an image's boot partition
```

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
| Azahar 2126.2 (`0005`) | HD texture packs crashed Azahar (OpenGL) or hard-locked the Thor (Vulkan). |
| No Steam (`0006`) | FEX-Emu's 32-bit thunks fail to build with GCC 16.2, breaking the image build. |
| melonDS menu bar (`0007`) | In two-window mode melonDS showed its Qt menu bar on one screen. |
| asgard package + boot tuning (`0008`) | Hostname, USB autosuspend, charge limit, CPU clock cap at every boot. |
| asgard.yml | ROCKNIX preconfigures Wi-Fi and keys by baking them into the image; Asgard keeps them in a file next to it. |
| Display sleep hook | After resume the bottom panel lit up (black) even when it was off before sleep. |
| Bottom screen rotation + window rules | The bottom panel was portrait; games opened on the wrong screen or half the screen. |
| OLED idle blank | Burn-in protection: both screens off after 5 min without input. |
