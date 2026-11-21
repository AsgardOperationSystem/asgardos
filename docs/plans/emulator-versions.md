# Emulator versions (2026-10-31)

Goal: know how far each standalone emulator is behind upstream, and bump the cheap ones first.

## Where they are

Each standalone emulator is a package `packages/emulators/standalone/<name>/package.mk`. The version is
`PKG_VERSION`: a release tag (`2026.1.0`) or a commit sha with the tag in a trailing comment (`# tag v0.2.1`).
`PKG_SITE` is the upstream repo. Patches sit in the package's `patches/`; check them against a new version with
`patch -p1 --dry-run` (ROCKNIX applies them with fuzz, so `git apply` lies).

Exceptions:
- `duckstation-sa` downloads upstream's AppImage: `PKG_VERSION` is the release name without the `v` (`0.1-10998`).
- `aethersx2-sa`, `drastic-sa`: prebuilt, closed source, tarballs from `ROCKNIX/packages` (see `rocknix-sources.md`).
- `eden-sa`: upstream is Forgejo (`git.eden-emu.dev`), not GitHub.
- Libretro cores (`packages/emulators/libretro/`) are not covered here.

## Status (checked 2026-10-31)

| Emulator | Package | Ours | Latest upstream | Gap |
|---|---|---|---|---|
| Azahar | `azahar-sa` | 2126.2 (with a local bump for azahar#2407) | 2126.2 (2026-10-08) | ✅ current |
| Eden | `eden-sa` | v0.2.1 | v0.2.1 (2026-06-01) | ✅ latest release; master has moved on |
| Eden Duo | `eden-duo-sa` | 1.3.2.2 | v1.3.2.2 (2026-10-24) | ✅ |
| Dolphin | `dolphin-sa` | 2609 (2026-09-23) | 2609a | ⚠️ point release behind |
| PPSSPP | `ppsspp-sa` | v1.20.2 | v1.20.4 (2026-05) | ⚠️ 2 patch releases behind |
| ARMSX2 | `armsx2-sa` | 2.8.4 | 2.9.1 (2026-10-28) | ⚠️ minor release behind |
| DuckStation | `duckstation-sa` | 0.1-10998 | 0.1-12083 | ❌ ~1,100 builds behind |
| RPCS3 | `rpcs3-sa` | commit of 2026-08-10 | v0.0.43 (2026-09-30) | ❌ 787 commits behind |
| Vita3K | `vita3k-sa` | commit of 2026-04-06 | continuous (2026-10-30) | ❌ 299 commits behind |
| Cemu | `cemu-sa` | commit of 2026-04-22 | v2.6, plus master | ❌ 199 commits behind |
| xemu | `xemu-sa` | commit of 2026-08-01 | v0.8.139 (2026-10-21) | ⚠️ 71 commits behind |
| melonDS | `melonds-sa` | recent commit | 1.1, plus master | ✅ 2 commits behind |
| Flycast | `flycast-sa` | v2.7 | v2.7 | ✅ |
| gopher64 | `gopher64-sa` | v1.1.42 | v1.1.42 | ✅ |
| ares | `ares-sa` | v148 | v148 | ✅ |
| ScummVM | `scummvm-sa` | 2026.1.0 | 2026.4.0 | ⚠️ 3 releases behind |
| GZDoom | `gzdoom-sa` | g4.14.2 | g4.14.2 | ✅ |
| Amiberry | `amiberry` | commit of 2023-12 | v8.5.0 (2026-10-27) | ❌ ~3 years (4,975 commits) |
| GBA DS | `gba-ds-sa` | v1.5.6 (added 2026-11-21) | v1.5.6 (2026-11-19) | ✅ (its mGBA, `gba-ds-mgba`, is the commit its `scripts/mgba-options.sh` names: bump the two together) |

Not checked: mupen64plus, hatari, the other small standalones.

## Plan

1. **Cheap bumps** (not started): PPSSPP v1.20.4, Dolphin 2609a, ARMSX2 2.9.1, ScummVM 2026.4.0.
2. **Big jumps**, one at a time, on the Thor before the next: DuckStation, RPCS3, Vita3K, Cemu, xemu. Expect patch
   rework.
3. **Amiberry**: 3 years behind; decide whether we still ship it before spending a rebase on it.

## How to check next time

From the tree root (needs `gh` logged in). `latest` is upstream's latest GitHub release; `behind` is how many commits
a pinned sha is behind the default branch (a sha on a release tag still shows commits since that tag, so compare
the tag first).

```sh
for pf in packages/emulators/standalone/*/package.mk; do
  ver=$(sed -n 's/^PKG_VERSION="\([^"]*\)".*/\1/p' "$pf" | head -1)
  repo=$(sed -n 's|^PKG_SITE="https://github.com/\([^/"]*/[^/"]*\)/*".*|\1|p' "$pf" | head -1)
  [ -n "$repo" ] || continue
  latest=$(gh api "repos/$repo/releases/latest" --jq .tag_name 2>/dev/null) || latest=-
  behind=-; [ ${#ver} = 40 ] && { behind=$(gh api "repos/$repo/compare/$ver...HEAD" --jq .ahead_by 2>/dev/null) || behind=-; }
  printf '%-22s %-42s latest=%-14s behind=%s\n' "$(basename "$(dirname "$pf")")" "$ver" "$latest" "$behind"
done
```

Eden (Forgejo) and Dolphin (tags only, no GitHub releases):

```sh
curl -s 'https://git.eden-emu.dev/api/v1/repos/eden-emu/eden/releases?limit=3' | jq -r '.[] | .tag_name + " " + .published_at[:10]'
gh api repos/dolphin-emu/dolphin/tags --jq '.[0:3][].name'
```

DuckStation's GitHub release is a rolling `latest`; its newest build number is the newest tag:
`gh api repos/stenzek/duckstation/tags --jq '.[0].name'`.
