# Licensing

caihong-omarchy's own build scripts, tooling, and documentation are licensed
under GPL-2.0-only unless a file states another SPDX license. The full text is
in [LICENSE](LICENSE).

The dependency submodules are separate works, pinned at the commits in
`pins.env`, and remain under their upstream licenses. The patch series under
`patches/` modify those works and are distributed under the same terms as the
files they change.

| Component | Path | License |
| --- | --- | --- |
| Linux kernel | `linux/` | GPL-2.0 WITH Linux-syscall-note |
| Omarchy | `omarchy/` | MIT |
| Omarchy PKGBUILDs | `omarchy-pkgs/` | MIT |
| libcamera | `external/libcamera/` | LGPL-2.1-or-later (core); IPA modules under their own licenses |
| plasma-camera | `external/plasma-camera/` | GPL-3.0-or-later; includes BSD-3-Clause and LGPL components |
| libssc | `external/libssc/` | GPL-3.0-or-later |
| qcom-va-driver | `external/qcom-va-driver/` | MIT |
| power-profiles-daemon | `external/power-profiles-daemon/` | GPL-3.0-or-later |
| qbootctl | `external/qbootctl/` | GPL-3.0 |
| mkbootimg | `external/mkbootimg/` | Apache-2.0 |
| caihong-toolbox | `external/caihong-toolbox/` | No license file in the pinned tree |
| audioreach-topology | `external/audioreach-topology/` | BSD-3-Clause |
| Device firmware | `firmware/`, `firmware-assets/` | Vendor terms; not covered by the GPL |

The kernel patches under `patches/linux/` are GPL-2.0-only. The Omarchy and
Omarchy PKGBUILDs patches are distributed under the MIT license of those
projects.
