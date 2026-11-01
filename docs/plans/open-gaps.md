# Open gaps

What to do about each row of `SPEC.md`'s known gaps, and the problems found alongside them that no rule covers. `SPEC.md`
section 16 says what's wrong; this says what's planned. Covering every rule with a check on 2026-11-01 found most of these.
None has been fixed here, and most were found by reading code or running it on a host, not on a Thor.

The test named in each row has a `# gap:` header, so `./test.sh` reports it as GAP. When a fix lands, the test starts passing
and `./test.sh` fails until its header and the row in `SPEC.md` are removed. A recommendation here is a starting point: the
owner decides between fixing the tree and changing the rule, and the rule never changes just to make a test pass.

## Fix the tree

Small, and the rule is right.

| Rule | Fix | Test |
|---|---|---|
| SET-3 | Give `PowerMenu.qml` the confirmation Settings has. A mistap on the power button restarts the Thor today. SET-3 sits in the Settings section, so this needs the owner to agree it covers Home's menu too. | `test_power_menu_confirm.py` |
| CFG-13 | Teach `parse_yaml` the inline form. Today the spec's own example sets `wifi={ssid: x}` and no error shows. | `test_asgard_yml_inline.py` |
| CFG-9 | Make `optionRow` follow `get_setting`'s order. Display only: the game already gets the right value, and the row misnames it. | `test_option_row_scope.py` |
| LOOK-3 | Run the grid's scroll and the card's settle off `Theme`, so the Animations setting stops them. | `test_look_motion.py` |
| BAT-5 | Leave out the average current for an activity too short to mean anything. The rule doesn't set a length: a few minutes fits its wording. | `test_battery_short_activity.py` |
| EMU-4 | Remove the `AdvanceMame` registration from `cps1`, `cps2` and `cps3`, since picking it can't start. Add `desmume` and `gpsp` to section 14's core list, because the image ships them. | `test_emulator_start_scripts.py`, `test_emulator_core_list.py` |
| DEV-7 | Delete the four unused files in `packages/linux/patches/mainline`. | `test_gap_kernel_patch_files.sh` |
| DEV-11 | Build the release under `build/`, not `target/`. | `test_gap_release_dir.sh` |
| EMU-6 | Add the other 16 standalone packages to `docs/plans/emulator-versions.md`. Documentation only. | `test_emulator_versions_plan.py` |

## New work

| Rule | What it takes | Test |
|---|---|---|
| HOME-2 | A Recently played row on the home tab. `backend.recent` already has the data, and no QML reads it. Needs a design choice on where it sits, and a device check of how it looks. | `test_home_recently_played.py` |
| MENU-5 | Decide how Home's menu reaches PPSSPP, ARMSX2, AetherSX2 and Flycast, which open their own (MENU-3). Then change MENU-3 and add a test: this row has none. | None yet |

## Probably change the rule

Check these before fixing the tree, because the rule itself looks wrong or too strict.

| Rule | Why | Check first | Test |
|---|---|---|---|
| KERN-1 | It names the SY7758 driver, but no Thor device tree binds it, only the Ayaneo Pocket trees. | What drives the Thor's backlight, in the device tree and on a Thor. | `test_kernel_sy7758_thor.py` |
| EMU-3 | Five inherited packages name their start script differently. Renaming them costs cherry-picks, which DEV-5 protects. | Whether the rule can list them as exceptions. | `test_emulator_names.py` |
| CFG-5 | `asgardos.bottomscreen.type` came from the fork's rename, and is what COMP-3 documents. Renaming these keys now would need a conversion under UPD-4. | Whether the rule should only apply from now on. | `test_setting_names.py` |
| DEV-17 | `asgard-motiond.py` needs `dbussy`, and `asgard-gamma` is C, both for good reasons. | Whether the rule should allow a recipe's package and a compiled helper. | `test_gap_service_languages.sh` |
| AUD-2 | The +1.3 dB comes from the strictest reading: the largest boost plus the summed mixer gains. | Whether that preset can clip in practice. If so, lower it or add the limiter. | `test_eq_headroom.py` |

## The owner decides

| Rule | Decision | Test |
|---|---|---|
| EMU-1 | Bring `pico-8` back, or record that it's an exception. No doc says why it went. | `test_emulator_fork_systems.py` |
| DEV-3 | Delete `debug/disp-rsc-dump` from the kernel repo. That's a remote change, and this was read from a local ref that may be stale. | `test_gap_kernel_debug_branch.sh` |
| DEV-2 | Remove 87 other devices' quirks and the branches for other SoCs in one pass, or as each is touched. A bulk removal needs care: some SM8550 files are symlinks into other platforms' directories, such as `095-force_zink` into `SM8750`. | `test_gap_other_devices.sh`, `test_gap_other_devices_recipes.sh` |
| DEV-11 | Whether `docs/supported-emulators.md` stays tracked, since a build regenerates it. | `test_gap_emulators_doc.sh` |

## Waiting on something else

| Rule | Waiting on | Test |
|---|---|---|
| DEV-9, DEV-15 | The public move replaces the LAN hosts and URLs. | `test_gap_lan_checkout.sh`, `test_gap_lan_urls.sh` |
| DEV-9 | `docs/plans/rocknix-sources.md`. It now counts thirteen packages, not ten. | `test_gap_rocknix_downloads.sh` |
| DEV-11 | A Go package's cache directories: `docs/plans/autotdp.md`, side note. | `test_gap_go_cache.sh` |

## Found alongside, with no rule

None of these has a test. Each should get a rule or a fix.

| Problem | Why it matters | Where |
|---|---|---|
| The UFS disk was lost during or after the sleep that started at 22:07:26 on 2026-11-01. Reads failed, `/storage` went `emergency_ro`, and suspend then failed 216 times. A reboot brought it back, with the journal recovered and two orphaned files cleared. Cause unknown. | Goal 1. If it can recur, it risks lost data, and only one occurrence has been seen. Before any reboot, save `dmesg` over SSH, because it doesn't reach the disk. | `thor/logs/ufs-failure-20261101-*.txt` and that boot's freeze report |
| `./build.sh stage` takes the alphabetically first `.tar` in `build/target`, and nothing clears older ones. | It can send an old image after a build on a later date. | `build.sh:13` |
| `chksysconfig` copies all of `/usr/config` over `/storage/.config` if `system.cfg` or RetroArch's files are missing or empty. | Goal 1: one missing file resets every emulator's settings at boot. It has a backup it doesn't use for this case. | `packages/asgardos/sources/scripts/chksysconfig` |
| Light sleep applies now, but with `mem_sleep_default=s2idle` the kernel maps `mem` and `freeze` to the same state. | PWR-11 offers a choice that changes nothing. Remove it, or decide what it should do. | `kernel/power/main.c`, `device/options` |
| An unhandled exception in `thor_text_input.py`, such as `swaymsg` missing, exits 1, which TXT-2 defines as cancelled, not failed. | A game sees a failure as the user cancelling. | `thor_text_input.py` |
| `asgard-perf-profile.sh cpu` exits 1 when no autotune is set. | Nothing reads the code today. | Its last line |
| `get_setting` needs bash 5.3: `local -a BASH_REMATCH` leaves the match empty on 5.2. The image ships 5.3, and tests strip the declaration for the host's 5.2. | A bash downgrade would quietly break every setting lookup. | `packages/asgardos/profile.d/001-functions` |

## Still to check on a Thor

- Rerun `./test-device.sh root@<thor>` after a sleep. 79 checks passed on 2026-11-01 on image `1e10fb2`, and 9 skipped: 8 need a sleep this boot, and one needs bypass charging on.
- `docs/human-checks.md` hasn't been done.
- Not yet on a device, because they weren't in that image: PWR-11, PWR-10, BAT-2's alarm, GAME-2's Quit, CFG-4's writer, UPD-4's merge, GPU-3's freedreno choice, CFG-11, LOG-2's short report and the screens-on command. Each is ✅-eligible only after that (TEST-5).
- GPU-3: compare a few OpenGL games on Zink and freedreno before changing the default.
- The tests haven't been reviewed for overlap, and the path-rewriting helper is repeated in several of them.
