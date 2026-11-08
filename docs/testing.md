# Testing Asgard OS

How we check that `SPEC.md` still holds. A test is an automated or recorded check that a spec rule holds, and that
fails when the rule is broken. `./test.sh` runs the host tests.

## Levels, cheapest first

A check belongs at the lowest level that can catch the problem.

| Level | Runs | Catches | Examples |
|---|---|---|---|
| 1. Host logic | This machine, every commit | Parsing, state machines, calculations, how Home handles a game | `test_*`, Asgard Home offscreen, the fake emulator |
| 2. Tree checks | This machine, every commit | Rules visible in the source | No update path calls `updateabl` (UPD-5), no new LAN hosts (DEV-15), no `LOCAL_WIFI_*` (DEV-16) |
| 3. Image checks | After a build, before staging | A bad image, before it reaches a Thor | The boot entry names a kernel and DTB that exist, no test files or personal paths, a file list diff against the last image, the image's programs under QEMU user mode |
| 4. Device checks | A Thor over SSH, after an update | Hardware and integration problems | Services up, both screens and the pad present, the launch test, an RTC-timed sleep that checks collapse and resume |
| 5. Human checks | On a Thor, recorded per release or feature | What a script can't judge | Touch feel, picture quality, the emulator sleep test, drain under PWR-2's method |

**Build order:** the tree checks; image checks; read-only device checks; the fake emulator; the launch test. A full
virtual boot comes last, if at all.

Where each level lives:

- Levels 1 to 3 are `packages/asgard/sources/test_*`, run by `./test.sh`. An image check needs a build in `build/` and reads
  whichever one is there, which may be older than the source. Asgard Home runs offscreen on the Qt in the build's toolchain,
  through `tools/test/home_harness.py`, with system commands stubbed. `test_fake_emulator.py` has the fake emulator.
- Level 4 is `./test-device.sh root@<thor>`. A check that has no evidence yet, such as one needing a sleep this boot, reports
  SKIP.
- Level 5 is `docs/human-checks.md`.

A test with a `# gap:` header fails today because of a row in `SPEC.md`'s known gaps. `./test.sh` reports it as GAP, and
fails if it starts passing, so the header and the row get removed together. `./test.sh` also fails if a spec rule has no check
at any level. A rule counted there may have only part of it checked: a test's header says which part, and the rest sits at a
higher level. A device or human check counts as written, not as passed, until someone runs it.

`./test.sh` runs 8 tests at a time, or `-j <n>` or `TEST_JOBS`, and `-j 1` runs them one at a time. Results print in file order
however the tests finish. Each test gets its own folder, `build/test/runs/<run>/<test>/` (`TEST_PREFIX` moves `build/test/runs`),
with its `output.log` and the `tmp/` that is its `TMPDIR`, so tests and simultaneous runs can't collide. A run that fails keeps
its folder and names it at the end. A test waits on a deadline, not a count of tries, and listens on its own port, not a real one.

Tests have no CI: `./test.sh` is run by hand. QEMU isn't installed on the build node. The emulator sleep test is still to do
for most emulators (`docs/adding-an-emulator.md` §4).

## Rules

| ID | Rule |
|---|---|
| TEST-1 | Every test cites the spec rule it checks (`# spec: PWR-5`). A test with no rule points to a gap in the spec, or isn't needed. |
| TEST-2 | A new test must be seen failing once: break the code, watch it go red, restore the code. |
| TEST-3 | A test changes only if it missed the code being wrong, or if the spec changes in the same commit. Never change a test just to get a pass. |
| TEST-4 | No silent skips. A test that can't run, such as for a missing tool, reports as skipped with the reason. It doesn't crash or count as a pass. |
| TEST-5 | Status follows the level. Levels 1 to 3 earn at most 🧪. ✅ needs level 4 or 5. |
| TEST-6 | Device checks are read-only and stop if `/run/thor-playing.txt` shows a game. Anything that sleeps, restarts or changes the device needs an idle Thor and its owner's go for that run. |
| TEST-7 | **Launch test.** It may start a game on a Thor only if all of these hold: no game shows in `/run/thor-playing.txt`, including one held by Back to Home; it goes through `runemu.sh`; it uses a homebrew ROM we may redistribute; it doesn't change the user's saves or settings; and it quits what it started and confirms a clean exit. A sleep step in this test also falls under TEST-6. Nothing else may start an emulator binary on a Thor. |
| TEST-8 | **Emulation.** QEMU user mode runs the image's ARM programs at level 3. A fake emulator, a small script that follows the launcher contract and can exit with any code, crash or hang on demand, tests Home in a virtual display at level 1. A full virtual boot may cover boot order, `asgard.yml` precedence and updates keeping user data. A pass in emulation earns at most 🧪, and isn't proof that an image boots on a Thor. |
| TEST-9 | Test files and test ROMs don't ship in the image. |
| TEST-10 | Not tested here: emulator internals (only how each integrates), exact screenshots, and exact current draw in automation (gauge noise is about ±20 mA). Emulation can't cover sleep, Adreno and Turnip, the panels, touch, the pad MCU, the ADSP gyro, audio, charging, storage or OpenABL: those stay at levels 4 and 5. |
