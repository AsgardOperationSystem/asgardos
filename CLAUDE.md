# Asgard OS

Linux gaming OS for the AYN Thor, a fork of ROCKNIX. Read these before changing anything:

- **`SPEC.md`: what must stay true.** Work inside it. If a task would break a requirement, stop and ask; if the spec
  changes, it changes in the same commit as the code. Section 2 (safety boundaries) needs explicit approval every time.
- `README.md`: layout, build, and what works today.

Before calling work done, go through `SPEC.md` section 10. In particular, never mark something as working unless it
was checked on a real Thor, and say what was and wasn't checked.

Host tests live next to their sources in `packages/asgard/sources/` (`test_*`); each one's header says how to run it.
Machine-specific notes belong in `CLAUDE.local.md` (git-ignored), not here.
