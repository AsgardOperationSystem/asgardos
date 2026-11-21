# OTA updates from GitHub releases

Status: built and host-tested (2026-11-21); not checked on a Thor. The release key pair isn't made yet
(`scripts/release --keygen`), so no release is signed and no Thor offers one.

The Thor finds a newer Asgard release on GitHub, offers it, downloads it, checks it and stages it. It installs
through the existing boot-time installer (`packages/sysutils/busybox/scripts/init`), which takes any `*.tar` in
`/storage/.update` at the next boot.

## Decisions (the user, 2026-11-21)

- **Pre-releases count.** Every release so far is a pre-release, and GitHub's "latest release" ignores them. A
  "Pre-releases" setting (`asgard.update.prerelease`) defaults to on until 1.0.
- **Releases are signed.** The sha256 comes from the same release as the file, so it only catches a corrupted
  download. A signature made with a key that isn't on GitHub also catches a tampered release. It's part of this
  feature, not a follow-up.
- **Battery:** the restart to install is offered only on the charger or at 30 % or more. The download itself isn't
  restricted.
- **Check at boot:** on by default, with a setting to turn it off (`asgard.update.check_at_boot`).

## What a release must hold

- **A tag** `vX.Y.Z`. Other tags (the old `v20261120`) are ignored.
- **The files:** `AsgardOS-<DEVICE>.<ARCH>-X.Y.Z.tar`, its `.sha256` and its `.sig`.
- **The signature** is Ed25519 over the `.tar`, made with `openssl pkeyutl -sign -rawin`. openssl 3.6.3 and curl
  are already in the image, so this needs no new dependency.
- **The private key** stays on the build node, outside the repo and backed up off it. The public key ships in the
  image as `/usr/share/asgard/release-key.pem`.
- **A new `scripts/release`** signs the `.tar` and writes the `.sha256`. It doesn't upload: publishing stays a manual
  `gh release` step that needs the user's go.
- **Losing the key** means a new key ships in an update signed by the old one. Without the old key, users would have
  to update by hand once.

## Parts

### `asgard-update` (`packages/asgard/sources/asgard-update.py`)

**`check`**
- Reads `GET https://api.github.com/repos/AsgardOperationSystem/asgardos/releases` with a generic User-Agent and no
  device data.
- Considers only `vX.Y.Z` tags newer than `OS_VERSION` in `/etc/os-release`, compared as numbers.
- Skips drafts, pre-releases when the setting is off, versions the user chose to skip, and releases missing any of
  the three files.
- Writes the highest match (version, size, URLs, the first lines of the notes) to `/run/asgard-update.json`, or
  `{}` if there's nothing.
- `asgard.update.repo` overrides the URL. That's for tests.

**`download`**
- Refuses if `/storage` has less than about twice the `.tar`'s size free, because the installer unpacks
  KERNEL+SYSTEM next to it.
- Downloads with `curl -C -` into `/storage/.update/<name>.part`, so a dropped connection or a sleep resumes it.
  Progress goes to `/run/asgard-update-progress.json`.
- **Checks sha256, then the signature.** Only when both match does it rename the `.part` to `.tar` (UPD-2). If
  either fails, it deletes the `.part` and reports which one failed.
- Never restarts the Thor.

**`cancel`**
- Stops the download and deletes the `.part`.

### `asgard-update-check.service`

- A oneshot after `network-online`, with a timeout. If there's no network at boot, it tries once more when Wi-Fi
  connects, then stops for that boot. It never shows an error.
- Skipped when `asgard.update.check_at_boot` is `0`.

### Home (`Main.qml`)

- When `/run/asgard-update.json` names a version and Home is in front (never over a game), Home asks once per boot:
  "Asgard X.Y.Z is available": **Download** / **Later** / **Skip this version**.
- A skipped version is saved under `/storage/.config/asgard`.
- Download starts the same flow as Settings.

### Settings > Updates (`Settings.qml`)

- **Check for updates (OTA)** runs `check` and shows the result with its release notes.
- **Download** shows progress with Cancel, then "Ready to install".
- **Restart and install** asks for confirmation (SET-3). It's offered only on the charger or at 30 % or more, and it
  warns when a game is open in the background (UPD-3).
- **Settings:** check at boot, pre-releases.
- **A `.tar` copied in by hand** is offered as it is today.

## Spec and docs (in the same commit as the code)

- **SET-3:** also covers a downloaded update, the battery condition and the two settings.
- **New UPD-9:** the check (what it reads, that it sends nothing about the device, when it runs, how to turn it off).
- **New UPD-10:** a download becomes a `.tar` only after its sha256 and its signature match the built-in key, and
  nothing restarts without a yes.
- **New DEV rule:** the release format above, and that releases are signed with `scripts/release`.
- **`docs/features.md`:** 🧪 until checked on a Thor.
- **Also:** `docs/changes.md`, `docs/testing.md`, and a wiki Update page (DEV-20).

## Tests

**Host:**
- **Picking a release** from saved API responses: pre-release on and off, date tag, draft, a missing `.sig` or
  `.sha256`, same version, older version, a skipped version, `0.0.10` above `0.0.9`.
- **Downloading** against a local `http.server`:
  - **Good file:** becomes a `.tar`.
  - **Bad sha256:** nothing is staged.
  - **Good sha256 but a signature from another key:** nothing is staged.
  - **Interrupted:** only a `.part` is left, and the next run resumes it.
  - **Not enough space:** refused.
  - **Cancel:** the `.part` is removed.
- **Home and Settings** through `home_harness`: the prompt and its three answers, the progress row, the battery
  condition on the restart row, and that the existing hand-copied `.tar` offer still works.

**On the Thor** (needs the user's go for that run):
- Point `asgard.update.repo` at a fake `0.0.2` served from `server`, signed with a test key. Check, download and
  stage it without restarting, then remove it.
- The real install from a real release comes with the next release after this ships.

## Order

1. Wait for the in-progress Settings and Home changes to be committed.
2. Create the key pair; the user stores the private key.
3. `scripts/release`.
4. `asgard-update` with its tests.
5. The service.
6. Settings and Home with their tests.
7. Spec and docs.
8. A Thor check with the fake release.
