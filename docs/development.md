# Developing Asgard OS

How the repo is laid out, how to build and stage an image, how the kernel is kept, and how to work on Asgard Home.
How it's tested is in [testing.md](testing.md); what must stay true is in [SPEC.md](../SPEC.md).

## Layout

```
build.sh          build the image (./build.sh), or stage it on a Thor (./build.sh stage)
test.sh           run the host tests: no Thor, no build, no root
test-device.sh    run the read-only device checks on a Thor over SSH
inject-config.sh  put your asgard.yml on an image's boot partition
distribution/     Asgard OS itself: options, kernel_options, logos, image tools, extra package patches
device/           the board (SM8550): options, config.xml (DTB list), bootloader, rootfs overlay, kernel .config
packages/         every package recipe; ours: asgard/, asgard-home/ (src/), asgardos/;
                  linux/src is the kernel, a submodule (AsgardOperationSystem/linux)
config/ scripts/  the build system (from LibreELEC by way of ROCKNIX, ours now)
tools/            build helpers; tools/turnip/ builds extra Turnip (Vulkan) drivers
docs/             changes, sleep work, adding an emulator, the supported emulators, screenshots
build/            git-ignored: everything the build makes (build dirs, sources, target/ images, log/)
thor/             git-ignored: device notes (ayn_thor_pro.md) and the Thor workspace
```


## Building

```
git clone --recurse-submodules https://github.com/AsgardOperationSystem/asgardos.git
cd asgardos && ./build.sh      # docker build of the SM8550 image -> build/target/ (all output in build/)
```
`./build.sh stage root@<thor>` copies the update to a running Thor; it's applied on the next reboot.

To put Asgard on a Thor, see [Install](https://github.com/AsgardOperationSystem/asgardos/wiki/Install) in the wiki.


## Releases

A release is the image step's output plus a signature, published by hand (DEV-22):

1. Raise `OS_VERSION` in `distribution/version`, build, and check the image on a Thor.
2. `scripts/release` (default `build/target`): checks each `.tar` against its `.sha256` and signs that file into
   `<name>.tar.sig` with the release key, then checks the signature with the key the image ships.
3. `gh release create vX.Y.Z` with the `.img.gz`, the `.tar` and their `.sha256`, and the `.tar.sig`. Thors offer a
   release only when its tag is `vX.Y.Z` and the `.tar`, `.sha256` and `.sig` are all there.

The key pair: `scripts/release --keygen` writes the private key to `~/.config/asgard/release-key/asgard-release.key`
(or `$ASGARD_RELEASE_KEY`) and the public one to `packages/asgard/sources/release-key.pem`, which the image ships as
`/usr/share/asgard/release-key.pem`. Keep the private key backed up off the build machine. If it's lost, a new key
can only reach Thors through an update copied by hand, since they won't take a release signed with a key they don't
have.

## Kernel

The kernel is its own repo, [AsgardOperationSystem/linux](https://github.com/AsgardOperationSystem/linux) (branch `asgard`): Linux
stable plus every Asgard kernel patch and the SM8550 device trees as one commit each. It's a submodule here; the build
copies it as is (no patch files, no tarball). To change the kernel, commit in the submodule, push, and commit the new
submodule pointer here. To move to a new kernel, rebase `asgard` onto the new stable tag (`git rebase --onto v7.3.2
v7.3.1`), fix the conflicts, force-push (allowed on `asgard`), set `PKG_VERSION` in `packages/linux/package.mk`.

To take a fix from ROCKNIX: `git remote add rocknix https://github.com/ROCKNIX/distribution.git` once, then
`git fetch rocknix next` and `git cherry-pick <sha>` (git maps ROCKNIX's `projects/ROCKNIX/...` paths to ours by
rename detection; a conflict means the file moved too far). Until 2026-10-30 Asgard was patches/ +
overlay/ on a pinned ROCKNIX; each old patch is now one commit ("Asgard patch NNNN" in its message).


## Gyro: ADSP sensors root

The gyro and accelerometer (SH5001) live in the ADSP's sensor core. `thor-sensorspd.service` (hexagonrpcd) serves
it a HexagonFS root that can't ship in the image (Android blobs plus this unit's calibration). It lives in
`/storage/.config/asgard/sensors-root/`: `hexagonrpc.json`, `dsp/` from the Thor's `dsp_a`,
`vendor/etc/sensors`, three libraries from `vendor/lib/rfsa/adsp`, `odm/etc`, a writable copy of `persist/sensors`, and
`socinfo/` (Android's `soc0` values). `asgard-sensors-root.service` builds it once at boot from Android's partitions
(`vendor` and `odm` are ext4 images in `super`, found through its liblp metadata), all mounted read-only; log
`/var/log/asgard-sensors-root.log`. A root already there, such as one copied by hand, is never replaced. The service
starts only when it's there.


## Asgard Home

Qt Quick on the image's Qt 6, two windows: top 1920×1080 (grid, dock) and bottom 1240×1080 (detail card, hints).
- `backend.cpp`: library from ROCKNIX's `es_systems.cfg`, ROM dirs and ES-DE-format scraped media; play time;
  launching through `runemu.sh`; the pad from evdev (the Thor's Nintendo layout: A east, B south).
- `qml/`: `Main.qml` (state and navigation), `HeroCard`, `Tile`, `Dock`, `Settings`, `GameMenu`, small parts.
- `dev.sh shot ["keys"]` renders both screens offscreen on the desktop; `THOR=root@<thor> dev.sh thor ["keys"]`
  cross-builds, copies to the Thor and renders there. The screenshots above come from running the installed
  `asgard-home` with `ASGARD_SHOT`/`ASGARD_KEYS` on the Thor.

