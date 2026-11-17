# caihong-omarchy

Build system and local changes for running Omarchy on the OnePlus Pad 2
(Caihong). Upstream projects are submodules pinned to exact commits; every
local change lives in this repository as a patch series, never as a commit in
a dependency.

## Layout

| Path | Contents |
| --- | --- |
| `caihong-linux-rootfs/` | Build system submodule (`Osilvfe/caihong-linux-rootfs`) |
| `linux/` | Kernel submodule (`Osilvfe/linux`) |
| `omarchy/` | Omarchy submodule (`omacom/omarchy`) |
| `omarchy-pkgs/` | Omarchy PKGBUILDs submodule (`omacom/omarchy-pkgs`) |
| `external/` | Camera, SSC, VA-API, PPD, qbootctl, mkbootimg, toolbox submodules |
| `patches/<dep>/series` | Ordered patch list for one dependency |
| `patches/<dep>/*.patch` | `git format-patch` output |
| `pins.env` | Upstream commit and expected post-patch tree hash per dependency |
| `scripts/` | Source preparation, patch refresh, verification, update tooling |
| `docs/build.md` | Build and image instructions |

## Quick start

```sh
git clone --recurse-submodules https://github.com/clsx524/caihong-omarchy.git
cd caihong-omarchy
scripts/prepare-sources.sh
```

`prepare-sources.sh` checks every submodule out at its pinned commit, applies
`patches/<dep>/series` with `git am --3way`, verifies the resulting tree hash
against `pins.env`, and writes `build/dependencies.resolved.env` for the build
scripts.

The build scripts live in `caihong-linux-rootfs/scripts/`. They resolve the
kernel and external component trees from the superproject root, so run them
from the submodule:

```sh
caihong-linux-rootfs/scripts/build-kernel-release.sh
```

The kernel tree contains paths that differ only by case (`xt_HL.c` and
`xt_hl.c`). Run the source tooling on a case-sensitive filesystem: a
case-sensitive APFS volume, or the build container's volume. The scripts
refuse to run on a case-insensitive filesystem.

## Patch workflow

Local changes are exported from a dependency working tree:

```sh
# In the submodule, commit the changes in logical groups on top of the pin.
git -C omarchy checkout -b work <pin>
git -C omarchy commit ...
scripts/refresh-patches.sh omarchy
```

`refresh-patches.sh` re-exports `<pin>..HEAD` into `patches/<dep>/`, rewrites
`series`, updates the tree hash in `pins.env`, and resets the submodule to the
pin. The superproject commit then contains only the pin and the patches.

Verify a series from a clean checkout:

```sh
scripts/verify-patches.sh
```

## Updating upstream

```sh
scripts/update-dep.sh omarchy <new-ref>
```

The script fetches, checks out the new ref, and replays the series with
`git am --3way`. On conflict it stops at the failing patch:

```sh
git -C omarchy status
git -C omarchy am --show-current-patch=diff
# edit the conflicted files
git -C omarchy add <files>
git -C omarchy am --continue
scripts/refresh-patches.sh omarchy
scripts/verify-patches.sh
```

Never use `git am --skip`; it silently drops a change. Never edit a `.patch`
file by hand; edit the tree and re-export. If upstream already contains a
change, `git cherry <new-pin> HEAD <patch-commit>` reports `-`; drop that
patch from `series` and note it in the superproject commit.

For a series with several conflicts, rebase instead of replaying:

```sh
git -C omarchy checkout -B work <old-pin>
git -C omarchy am --3way patches/omarchy/*.patch
git -C omarchy rebase --onto <new-pin> <old-pin> work
git -C omarchy range-diff <old-pin>..<old-tip> <new-pin>..work
scripts/refresh-patches.sh omarchy
```

`range-diff` shows how each patch changed; the tree hash only proves that the
series applied.

## Credits

This project is mostly glue around other people's work. Thanks to:

- [Omarchy](https://omarchy.org) by DHH and contributors — the desktop.
- [caihong-linux-rootfs](https://github.com/Osilvfe/caihong-linux-rootfs) — the rootfs build system, with contributions from Ahaan (Unnho).
- [linux](https://github.com/Osilvfe/linux) — the Caihong kernel tree, with contributions from xianfei and others.
- [libcamera](https://libcamera.org) — the camera stack.
- [libssc](https://codeberg.org/DylanVanAssche/libssc) by Dylan Van Assche — Qualcomm sensor core.
- [plasma-camera](https://invent.kde.org/plasma-mobile/plasma-camera) — the KDE camera app.
- [qcom-va-driver](https://github.com/radxa-pkg/qcom-va-driver) by Christopher Obbard and Radxa — VA-API.
- [power-profiles-daemon](https://gitlab.freedesktop.org/upower/power-profiles-daemon) — power profiles.
- [qbootctl](https://github.com/linux-msm/qbootctl) by Caleb Connolly — boot slot control.
- [mkbootimg](https://android.googlesource.com/platform/system/tools/mkbootimg) — Android boot images.
- [AudioReach](https://github.com/AudioReach/audioreach-topology) — audio topology.
- The Linux kernel community.

## License

The build system and tooling are GPL-2.0-only; see [LICENSE](LICENSE).
Dependency submodules and the patch series retain their upstream licenses; see
[THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md). Bundled firmware remains
subject to vendor terms.

## Invariants

- Submodule gitlinks always point at upstream commits.
- The build system is a submodule too; local changes to it are patches.
- `git -C <dep> status --porcelain` is empty in the committed state.
- `pins.env` records the expected tree hash after the series; a mismatch is a
  hard failure.
- A clean apply is not proof of correctness: build and boot-test the result.
