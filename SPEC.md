# Asgard OS specification

What Asgard OS must be and must keep doing. Anyone changing this repo, human or AI, works inside it.

## 0. How to use this document

**Authority.** A change that would break a requirement here is out of spec. Stop and ask the owner. If the owner agrees,
change the spec in the same commit as the code. Never edit the spec only to make a change fit.

**What lives where.** Each kind of fact has one home, so this file doesn't go stale by repeating them:

| Question | Home |
|---|---|
| What must be true? | this file |
| What works today? | `README.md`, feature tables |
| Why was it changed? | `docs/changes.md`, `docs/merge-requests.md`, commit messages |
| What must an emulator do? | `docs/adding-an-emulator.md`, part of this spec by reference (GAME-8) |
| What did we find while investigating? | `docs/sleep.md`, `thor/ayn_thor_pro.md` (local, not in git) |
| What is planned? | `docs/plans/` |
| How is it tested? | this file, section 12 |

If a plan or doc disagrees with this file, this file wins. If the code disagrees, the code is either a bug or a listed
deviation (section 11). An unlisted disagreement is a bug in the code or in the spec: raise it, don't pick one silently.

**Wording.** MUST / MUST NOT are hard rules. SHOULD can be broken with a reason given in the commit message. IDs are
stable: don't reuse or renumber them, so tests and commits can cite them.

**Verified by.** The tag after each requirement says how it's checked today:

- `[host: file]`: a test in `packages/asgard/sources/`, runs without a Thor.
- `[build]`: a build of the image shows it.
- `[device]`: only a check on a real Thor shows it.
- `[review]`: checked by reading the change.

## 1. Product

Asgard OS is a Linux gaming OS for one device, the **AYN Thor** (SM8550, two OLED touch screens). It is a fork of
ROCKNIX, forked 2026-10-30 at `7cffc96`. It exists to make the Thor a complete handheld: its own dual-screen frontend,
working Thor hardware support, and native settings and tools.

**Goals, in priority order when they conflict:**

1. **Don't lose the device or the user's data.** No change may risk an unbootable Thor or lost saves, ROMs or settings.
2. **A game in progress is safe.** Sleep, Back to Home and overlays must not lose or corrupt it.
3. **Works on the device, with no PC.** Everything a user does, they can do on the Thor itself.
4. **Games run well.** While a game plays, its speed and compatibility come before saving power, unless the user chose a cap or profile.
5. **Battery and heat.** Sleep drain and idle power are product features, not afterthoughts.
6. **Stays maintainable by one owner.** Fewer mechanisms, each understandable, each with its reason written down.

**Non-goals.** Don't work towards these without the owner asking:

- Other devices or SoCs, including handhelds on the same SoC such as the Odin 2 family. Recipes don't grow branches for them.
- EmulationStation or another frontend, or a dual-boot setup.
- Staying in sync with ROCKNIX `next`.
- A public release. See SAFE-6.

## 2. Safety boundaries

Each of these needs the owner's explicit go **for that specific action**. Approval doesn't carry over to the next one.

| ID | Rule | Verified by |
|---|---|---|
| SAFE-1 | Nothing writes `abl_a`/`abl_b` without the owner's go, and an update MUST NOT flash them, directly or through a script it calls. `updateabl` stays a manual command. A bad ABL can only be recovered through EDL. | `[review]` `device/bootloader/update.sh` |
| SAFE-2 | Changes to the boot chain need the owner's go first: the Boot Loader Spec entry, `/flash` layout, kernel or DTB names, partition labels, GPT. | `[review]` |
| SAFE-3 | Never reboot a Thor, restart its session or stop a game while `/run/thor-playing.txt` shows a game is running, unless the owner says to. | `[review]` |
| SAFE-4 | Never start an emulator binary on a Thor to inspect it (`--version` opens a window over the game). Read logs or compare against `build/.../install_pkg/`. The one exception is the launch test (TEST-7), which the owner has approved under the rules there. | `[review]` |
| SAFE-5 | No secret or personal data in git or in an image: Wi-Fi keys, logins, SSH keys, this unit's Android blobs and calibration. Never set `LOCAL_WIFI_SSID`, `LOCAL_WIFI_KEY` or `LOCAL_SSH_KEYS_FILE`. `build.sh` MUST keep running the build from an empty environment. | `[review]` `build.sh` |
| SAFE-6 | Nothing leaves the private GitLab without the owner's go: no public repos, no pushes to GitHub, no sending device or user data to outside services. | `[review]` |
| SAFE-7 | Don't delete or overwrite ABL backups, the EDL kit, or anything else in `thor/`. `thor/` is not backed up and can't be rebuilt. | `[review]` |

## 3. Repository and build

| ID | Rule | Verified by |
|---|---|---|
| REPO-1 | Files go in the layer they belong to: `distribution/` the distro and image tools; `device/` the SM8550 board; `packages/` all recipes (ours: `asgard/`, `asgard-home/`, `asgardos/`); `config/`, `scripts/` the build system; `tools/` build helpers; `docs/` the docs. | `[review]` |
| REPO-2 | `main` is the only long-lived branch here, `asgard` the only one in the kernel repo. Feature branches are short and merge back quickly. | `[review]` |
| REPO-3 | Kernel changes are commits in `asgardos/linux` (the submodule `packages/linux/src`), followed by a pointer bump here. No kernel patch files in this repo. The submodule keeps its own objects: no alternates, no `--reference`. Force-push is allowed on `asgard` only. | `[build]` |
| REPO-4 | ROCKNIX fixes come in by `git cherry-pick <sha>`. MUST NOT merge ROCKNIX `next`: newer `next` flashes OpenABL to the ABL slots (SAFE-1). | `[review]` |
| REPO-5 | `./build.sh` builds the SM8550 image in the digest-pinned container. A clean checkout with submodules MUST build with no other setup. | `[build]` |
| REPO-6 | All build output goes under `build/`. Nothing is written to the tree outside it. | `[build]` |
| REPO-7 | A package declares every dependency it uses, optional ones too. A build MUST NOT depend on package build order. | `[build]` |
| REPO-8 | Package patches are checked with `patch -p1 --dry-run`, which is how they're applied. `git apply` gives wrong answers here. | `[build]` |
| REPO-9 | New build inputs MUST NOT depend on LAN hosts or on personal paths. The existing ones listed in section 11 stay until the public move. | `[review]` |
| REPO-10 | Personal paths and LAN addresses don't appear in code, configs or shipped binaries, apart from the GitLab URLs listed in section 11. Binaries carry `/work/...` paths. | `[review]` |
| REPO-11 | Don't edit tree files while `./build.sh` runs: re-hashed stamps clean install dirs mid-build. | `[review]` |

## 4. Updates and persistence

| ID | Rule | Verified by |
|---|---|---|
| UPD-1 | The root filesystem is read-only. Everything that must survive a reboot or update lives in `/storage`, or `/flash` for boot files. | `[device]` |
| UPD-2 | A partial copy MUST NOT look like an update: staging copies to a temporary name, checks the checksum on the device, then renames to `*.tar`. | `[review]` `build.sh` |
| UPD-3 | Staging an update MUST NOT reboot the device or disturb a running game. The update installs on the next boot. | `[review]` `build.sh` |
| UPD-4 | An update keeps user data: saves, ROMs, `system.cfg`, `/storage/.config/asgard`, `/storage/.config/thor`, and SSH keys. A change to a key or file format MUST convert existing values. | `[device]` |
| UPD-5 | A setting that exists on a running device keeps working across an update, or its removal is called out in the commit message. | `[review]` |

## 5. Configuration

| ID | Rule | Verified by |
|---|---|---|
| CFG-1 | Precedence, at every boot: **image defaults < `asgard.yml` < the user's own changes**. A value changed on the device is never overwritten by the yml. | `[host: asgard_config.py --test]` |
| CFG-2 | The yml is read from `/flash/asgard.yml`, then `/storage/.config/asgard/asgard.yml`. First found wins; they aren't merged. | `[review]` `asgard_config.py` |
| CFG-3 | `ssh.authorized_keys` lines are appended. Existing lines are kept. | `[host: asgard_config.py --test]` |
| CFG-4 | Settings live in `system.cfg`. Writes are atomic, keep comments, and replace in place. A per-game key (`<system>["<rom>"].<key>`) doesn't affect the system key. | `[host: test_thor_settings.py]` |
| CFG-5 | New Asgard settings use the `asgard.` prefix. Keep ROCKNIX's existing key names. | `[review]` |
| CFG-6 | New Asgard state goes in `/storage/.config/asgard/`; logs and reports go in `/storage/.config/thor/`. | `[review]` |
| CFG-7 | Every setting has a safe default, and the system boots and runs when the setting or its file is missing. Hardware data that can't ship (`sensors-root/`) MUST leave its feature off, not fail: a unit's service starts only when the data is there. | `[review]` `thor-sensorspd.service` |
| CFG-8 | The default root password is `asgardos`, in both `distribution/options` (`ROOT_PASSWORD`) and `system.cfg` (`root.password`), and is documented in the README. `root.password` is the source of truth: every boot applies it to the root login, Samba and the Syncthing GUI. It's a public default, not a secret; a personal password goes in `asgard.yml` or on the device, never in the image (SAFE-5). | `[review]` `007-rootpw` |

## 6. Frontend and on-device use

| ID | Rule | Verified by |
|---|---|---|
| UI-1 | Asgard Home is the only frontend. It is what boots, and it's where games start. | `[build]` |
| UI-2 | Two windows: top screen (`DSI-2`, 1920×1080) for the grid and dock, bottom screen (`DSI-1`, 1240×1080, touch) for the detail card and hints. L+R swaps them. | `[device]` |
| UI-3 | A user-facing feature ships with a way to use it on the Thor. It MUST NOT need SSH, a keyboard or a PC, except for what `asgard.yml`, WireGuard `.conf` files and the sensors root are defined to need. | `[review]` `[device]` |
| UI-4 | The pad uses the Thor's Nintendo layout: A east, B south. | `[device]` |
| UI-5 | Text entry from Home, tools or a game's prompt uses Asgard's own on-screen keyboard. | `[device]` |
| UI-6 | Screens turn off after `asgard.idle_blank` seconds without input (default 300, 0 = never); any input turns them back on. | `[device]` |
| UI-7 | Home and everything it starts run in a UTF-8 locale. | `[device]` |

## 7. Running games

| ID | Rule | Verified by |
|---|---|---|
| GAME-1 | Home starts every game as `runemu.sh <rom> -P<system> --core=<core> --emulator=<emulator>`. Only `.desktop` apps in the PC and Steam lists may skip it, and those still get playtime, crash logs and the in-game menu. | `[review]` |
| GAME-2 | A launcher declares its process with `set_kill set "<signal> <name>"`, so Home can find and stop the game. | `[review]` |
| GAME-3 | Exit codes 0, 137 and 143 are a clean quit. Anything else keeps that launch's log in `/storage/.config/thor/crashes/` (newest 20). | `[review]` `runemu.sh` (exit codes), `[host: test_crashlog.sh]` (log kept) |
| GAME-4 | While a game runs, `/run/thor-playing.txt` names the game, emulator and core. | `[device]` |
| GAME-5 | Pressing Home in a game opens the in-game menu on the bottom screen. Every game gets Resume and Quit game; a game with kill data also gets Back to Home and Quit and save log. The game pauses while it's open if the emulator can pause. | `[device]` |
| GAME-6 | Back to Home freezes the game (SIGSTOP, windows in the scratchpad); returning continues it (SIGCONT, windows restored). Audio and input MUST come back. | `[device]` |
| GAME-7 | After a sleep the game carries on from where it was within a couple of seconds and MUST NOT replay the time asleep. Home only unpauses what it paused itself. | `[device]` |
| GAME-8 | A new emulator, or a new version of one, meets `docs/adding-an-emulator.md`. Its commit message records each checklist item as passed or not applicable. | `[review]` `[device]` |
| GAME-9 | Games see InputPlumber's virtual DualSense; the raw Thor pad is hidden from them. | `[device]` |
| GAME-10 | The main window is full screen on the top screen. A second window goes to the bottom screen by the rules in `thor-sway-rotate.sh`. With nothing to show there, the bottom screen goes off shortly after launch. | `[device]` |

## 8. Power

| ID | Rule | Verified by |
|---|---|---|
| PWR-1 | Sleep is s2idle with the game still loaded. CX, AOSS and DDR MUST collapse for the sleep (`/sys/kernel/debug/qcom_stats/`). | `[device]` |
| PWR-2 | Sleep drain stays at or under the 30 mA baseline; lower is always better, so 30 mA is a ceiling and not a target. **How to measure:** an unplugged sleep of an hour or more, starting at 4.13 V or lower. Readings just after a charge are gauge artifacts: MUST NOT be used as a baseline or to credit a fix. | `[device]` |
| PWR-3 | After a wake the pad, Wi-Fi, audio and storage work, with no reboot. The power button and the RTC both wake it. | `[device]` |
| PWR-4 | A lid-closed cable wake keeps the game stopped and goes back to sleep. | `[host: test_charge_fix.sh]` |
| PWR-5 | Charge limit: charging stops at the limit and resumes 5 % below it. `100` = off. `full` = hold at 100, resume at 95. | `[host: test_charge_limit.sh]` |
| PWR-6 | The fan's rail is off in sleep: fan mode 1 becomes 3 for the sleep and comes back after it. | `[host: test_fan_sleep.sh]` |
| PWR-7 | Autotune only moves maximum clocks and MUST NOT take the GPU ceiling below 348 MHz until lower is tested against GMU hangs. | `[host: test_asgard_autotune.py]` |
| PWR-8 | The gyro service runs only while asked for (per game or by `asgard.motion`): it keeps the ADSP awake. | `[device]` |
| PWR-9 | Background work SHOULD NOT wake the SoC in sleep or redraw when nothing changed. A periodic wake needs a reason in the commit message. | `[review]` |

## 9. Audio and logs

| ID | Rule | Verified by |
|---|---|---|
| AUD-1 | The default output follows the headphone jack. | `[device]` |
| AUD-2 | EQ filter nodes stay at 100 %: volume is set on the real sink. A preset with positive gain goes through the limiter. | `[device]` |
| LOG-1 | Warnings, errors, oopses, Wi-Fi and sleep events reach `/storage/.config/thor/logs/events.log`, which rotates. | `[host: test_asgard_events.py]` |
| LOG-2 | A boot that never shut down leaves a report in `/storage/.config/thor/freezes/` (newest 10). | `[device]` |
| LOG-3 | Crashes leave a core dump (`coredumpctl`, `/storage/.cache/cores`). Emulator handlers MUST NOT swallow fatal signals. | `[device]` |
| LOG-4 | `asgard.sleep_audit=1` writes one line per sleep with its deltas. | `[host: test_sleep_audit.sh]` |

## 10. Definition of done

| ID | Rule |
|---|---|
| DONE-1 | **Status is earned on the device.** A feature is ✅ in the README only after it was checked on a real Thor. Built or tested on a host only is 🧪. Tested against a fake is 🧪, and says so. |
| DONE-2 | **Say what was and wasn't checked.** A commit or handover states what ran and where. Never report something as working from a build alone. |
| DONE-3 | **Logic gets a host test.** New or changed logic that runs without hardware (parsing, state machines, calculations) gets a `test_*` next to its source, using fake sysfs or stubs through environment overrides. A bug fix adds the check that would have caught it. Section 12 has the rules for tests. |
| DONE-4 | **Investigate before changing.** Search `docs/` and `thor/ayn_thor_pro.md` first, then the projects listed in the README's credits. Don't re-test what is recorded as ruled out. |
| DONE-5 | **Commit messages explain.** What was broken, why, and what changed, with the requirement ID if one applies. One change per commit. |
| DONE-6 | **Docs move with the code**, in the same commit: the README's status, `docs/changes.md` for a change on top of ROCKNIX, this file if a requirement changes. |
| DONE-7 | **Stay in scope.** No unrequested refactors or renames, new daemons or dependencies. Paths and key names are interfaces: scripts, configs and existing devices use them (UPD-4). |

## 11. Known deviations

Where the tree breaks this spec today. Don't copy these or treat them as precedent. When one is fixed, delete its row.

| Rule | Deviation | Plan |
|---|---|---|
| REPO-5, REPO-9 | `.gitmodules` and the `Makefile`'s build image point at LAN hosts (`gitlab.lan.example`, `registry.lan.example`), so outside the LAN a clean checkout can't build. Accepted by the owner until the public move. | Replace at the public move |
| REPO-5 | Ten packages and `DISTRO_MIRROR` still download from ROCKNIX's GitHub. If ROCKNIX moves a file, a clean build breaks. | `docs/plans/rocknix-sources.md` |
| REPO-6 | A Go package's build writes `.cache/` and `.config/` to the tree root (git-ignored). | `docs/plans/autotdp.md`, side note |
| REPO-10 | `distribution/options` points its URLs at the old `asgardos/asgardos` project. `PKG_SITE` values and Home's RetroAchievements user agent carry the GitLab URL. | Fix with the public move |
| GAME-7 | The sleep test on the device is still to do for most emulators. Home can't pause Steam or PC games. | `docs/adding-an-emulator.md` §4 |
| DONE-3 | Tests have no runner or CI. `test_thor_settings.py` and `test_thor_panel.py` need host `libSDL2`, `test_gamma.sh` needs `wayland-scanner`. | Single runner first; see section 12 |
| TEST-1 | Existing tests don't cite requirement IDs yet. | Add when each test is next touched, or with the runner |
| TEST-9 | `packages/asgard/package.mk` installs `test_*` into the image. | With the runner |
| Section 12 | Only level 1 has tests, and they're run by hand. Level 5 is informal. Levels 2 to 4, the fake emulator, the launch test and the QEMU checks aren't built. QEMU isn't installed on the build node. | Build in the order in section 12 |
| Docs | `docs/adding-an-emulator.md` §10 cites a README changes table now in `docs/changes.md`; `docs/sleep.md` has old `~/Projects/asgard` paths; `docs/changes.md` still lists "No Steam (`0006`)". | Fix when next touched |

## 12. Testing

A test is an automated or recorded check that a requirement in this file still holds, and that fails when the
requirement is broken.

**Levels, cheapest first.** A check belongs at the lowest level that can catch the problem.

| Level | Runs | Catches | Examples |
|---|---|---|---|
| 1. Host logic | This machine, every commit | Parsing, state machines, calculations, how Home handles a game | `test_*`, Asgard Home offscreen, the fake emulator (TEST-8) |
| 2. Tree checks | This machine, every commit | Rules visible in the source | No update path calls `updateabl` (SAFE-1), no new LAN hosts (REPO-9), no `LOCAL_WIFI_*` (SAFE-5) |
| 3. Image checks | After a build, before staging | A bad image, before it reaches a Thor | The boot entry names a kernel and DTB that exist, no test files or personal paths, a file list diff against the last image, the image's programs under QEMU user mode (TEST-8) |
| 4. Device checks | A Thor over SSH, after an update | Hardware and integration problems | Services up, both screens and the pad present, the launch test (TEST-7), an RTC-timed sleep that checks collapse and resume |
| 5. Human checks | On a Thor, recorded per release or feature | What a script can't judge | Touch feel, picture quality, the emulator sleep test, drain under PWR-2's method |

**Build order:** a single runner for levels 1 and 2 with proper skips; the SAFE and REPO tree checks; image checks;
read-only device checks; the fake emulator; the launch test. A full virtual boot (TEST-8) comes last, if at all.

| ID | Rule |
|---|---|
| TEST-1 | Every test cites the requirement ID it checks. A test with no requirement points to a gap in this file, or isn't needed. |
| TEST-2 | A new test MUST be seen failing once: break the code, watch it go red, restore the code. |
| TEST-3 | A test changes only if it missed the code being wrong, or if this file changes in the same commit. MUST NOT change a test just to get a pass. |
| TEST-4 | No silent skips. A test that can't run, such as for a missing tool, reports as skipped with the reason. It doesn't crash or count as a pass. |
| TEST-5 | Status follows the level (DONE-1). Levels 1 to 3 earn at most 🧪. ✅ needs level 4 or 5. |
| TEST-6 | Device checks are read-only and stop if `/run/thor-playing.txt` shows a game. Anything that sleeps, restarts or changes the device needs an idle Thor and the owner's go for that run. |
| TEST-7 | **Launch test, the exception to SAFE-4.** It may start a game on a Thor only if all of these hold: no game shows in `/run/thor-playing.txt`, including one held by Back to Home; it goes through `runemu.sh`; it uses a homebrew ROM we may redistribute; it doesn't change the user's saves or settings; and it quits what it started and confirms a clean exit. A sleep step in this test also falls under TEST-6. Nothing else may start an emulator binary on a Thor. |
| TEST-8 | **Emulation.** QEMU user mode runs the image's ARM programs at level 3. A fake emulator, a small script that follows the launcher contract and can exit with any code, crash or hang on demand, tests Home in a virtual display at level 1. A full virtual boot may cover boot order, `asgard.yml` precedence and updates keeping user data. A pass in emulation earns at most 🧪, and MUST NOT be taken as proof that an image boots on a Thor. |
| TEST-9 | Test files and test ROMs MUST NOT ship in the image. |
| TEST-10 | Not tested here: emulator internals (only how each integrates, per GAME-8), exact screenshots, and exact current draw in automation (gauge noise is about ±20 mA). Emulation can't cover sleep, Adreno and Turnip, the panels, touch, the pad MCU, the ADSP gyro, audio, charging, storage or OpenABL: those stay at levels 4 and 5. |
