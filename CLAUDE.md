# Asgard OS

Linux gaming OS for the AYN Thor, a fork of ROCKNIX. Read these before changing anything:

- **`SPEC.md`: what Asgard OS is.** Work inside it. If a task would break a rule there, stop and ask. If the spec
  changes, it changes in the same commit as the code; never edit it just to make a change fit.
- `README.md`: what Asgard is, how to get and build it. What works today is in `docs/features.md` and
  `docs/emulators.md`; layout and build details in `docs/development.md`.
- `docs/testing.md`: how it's tested. Run the host tests with `./test.sh`, and say so if one was skipped.

## Before calling work done

- **Status is earned on the device.** A feature is ✅ in `docs/features.md` (or `docs/emulators.md`) only after it was checked on a real Thor. Built, or
  tested on a host or against a fake, is 🧪.
- **Say what was and wasn't checked.** Never report something as working from a build alone.
- **Logic gets a host test.** A bug fix adds the check that would have caught it.
- **Investigate first.** Search `docs/`, then the projects in the README's credits. Don't re-test what's recorded as ruled out.
- **Commit messages explain** what was broken, why, and what changed, with the spec rule if one applies. One change per commit.
- **Docs move with the code**, in the same commit: the status in `docs/features.md` / `docs/emulators.md`, `docs/changes.md`, `SPEC.md`.
- **Stay in scope.** No unrequested refactors, renames, new daemons or dependencies.

Machine-specific notes, and the rules for handling a specific device, belong in `CLAUDE.local.md` (git-ignored).
