# Cutting the ROCKNIX download ties (2026-10-30)

Goal: no build download depends on ROCKNIX's GitHub. Today ten packages and the fallback mirror still do; if ROCKNIX
moves or deletes a file, a clean build breaks (a `build/sources` cache hides it until then).

**Status (2026-10-31):** private copies of the six ROCKNIX source repos are in the `asgardos` GitLab group, but the
tree isn't repointed at them, because private GitLab redirects anonymous downloads to its sign-in page.
Where the mirror should live is undecided, so the plan below is only one option.

## What still fetches from ROCKNIX

Package paths are relative to `packages/`.

ROCKNIX's own projects (forkable into the `asgardos` GitLab group):

| Package | URL |
|---|---|
| `apps/rocknix-hotkey` | `github.com/ROCKNIX/rocknix-hotkey` |
| `apps/commander` | `github.com/ROCKNIX/commander` |
| `apps/jstest-sdl` | `github.com/ROCKNIX/jstest-sdl` |
| `linux-firmware/extra-firmware` | `github.com/ROCKNIX/extra-firmware` |
| `tools/sound/soundfont-generaluser` | `github.com/ROCKNIX/generaluser-gs` (their copy) |

Files ROCKNIX hosts in `github.com/ROCKNIX/packages` (just need a copy we control):

| Package | File |
|---|---|
| `emulators/standalone/aethersx2-sa` | `aethersx2.tar.gz` (prebuilt, closed source) |
| `emulators/standalone/drastic-sa` | `drastic.tar.gz` (prebuilt, closed source) |
| `compress/cabextract` | `cabextract.tar.xz` (upstream's source, their copy) |
| `apps/portmaster` | `compat.tar.gz` (`COMPAT_URL`; PortMaster itself comes from PortsMaster) |
| `emulators/libretro/idtech-lr` | `doom.tar.gz` (`PKG_DOOM_SHAREWARE`) |

Plus `DISTRO_MIRROR` in `distribution/options`: `github.com/ROCKNIX/distribution-sources/releases/download/sources-v2`,
the fallback `scripts/get_archive` tries (`${DISTRO_MIRROR}/<source file name>`) when a package's own URL fails.

## Plan

1. **LAN mirror** (not started): serve a directory over HTTP on `server` (nginx), flat (one directory of source
   files, the names `scripts/get_archive` asks for), seeded from our `build/sources/*/`. Point `DISTRO_MIRROR` at it. That alone covers every package
   above as long as the original URL keeps failing over to the mirror, and keeps old versions buildable.
2. **Repoint the five `ROCKNIX/packages` files** at the mirror directly, so a build doesn't depend on GitHub at all
   for them (`PKG_URL`, `COMPAT_URL`, `PKG_DOOM_SHAREWARE`; cabextract back to cabextract.org.uk).
3. **Fork the five ROCKNIX projects** into `asgardos/` only when we want to change one; until then the mirror holds
   the tarballs.

Check: with the mirror up, block github.com in the build container and fetch these packages into an empty `build/sources`.
