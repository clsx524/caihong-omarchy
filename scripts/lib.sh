#!/bin/bash
# Shared dependency map for the caihong-omarchy source tooling.
#
# The variable prefixes match build/dependencies.resolved.env, which the
# existing build scripts read. Plain case statements keep this compatible
# with the bash 3.2 shipped by macOS.

DEP_NAMES=(
  caihong-linux-rootfs
  linux
  omarchy
  omarchy-pkgs
  libcamera
  plasma-camera
  libssc
  qcom-va-driver
  power-profiles-daemon
  qbootctl
  mkbootimg
  caihong-toolbox
)

dep_path() {
  case $1 in
    caihong-linux-rootfs) echo caihong-linux-rootfs ;;
    linux) echo linux ;;
    omarchy) echo omarchy ;;
    omarchy-pkgs) echo omarchy-pkgs ;;
    libcamera) echo external/libcamera ;;
    plasma-camera) echo external/plasma-camera ;;
    libssc) echo external/libssc ;;
    qcom-va-driver) echo external/qcom-va-driver ;;
    power-profiles-daemon) echo external/power-profiles-daemon ;;
    qbootctl) echo external/qbootctl ;;
    mkbootimg) echo external/mkbootimg ;;
    caihong-toolbox) echo external/caihong-toolbox ;;
    *) return 1 ;;
  esac
}

dep_var() {
  case $1 in
    caihong-linux-rootfs) echo CAIHONG_LINUX_ROOTFS ;;
    linux) echo LINUX ;;
    omarchy) echo OMARCHY ;;
    omarchy-pkgs) echo OMARCHY_PKGS ;;
    libcamera) echo LIBCAMERA ;;
    plasma-camera) echo PLASMA_CAMERA ;;
    libssc) echo LIBSSC ;;
    qcom-va-driver) echo QCOM_VA ;;
    power-profiles-daemon) echo POWER_PROFILES_DAEMON ;;
    qbootctl) echo QBOOTCTL ;;
    mkbootimg) echo MKBOOTIMG ;;
    caihong-toolbox) echo TOOLBOX ;;
    *) return 1 ;;
  esac
}

dep_commit() {
  local var
  var="$(dep_var "$1")_COMMIT"
  printf '%s\n' "${!var}"
}

dep_tree() {
  local var
  var="$(dep_var "$1")_TREE"
  printf '%s\n' "${!var}"
}

ensure_git_identity() {
  local root=$1
  if [[ -z $(git -C "$root" config user.email 2>/dev/null) ]]; then
    export GIT_COMMITTER_NAME=${GIT_COMMITTER_NAME:-caihong-build}
    export GIT_COMMITTER_EMAIL=${GIT_COMMITTER_EMAIL:-caihong-build@localhost}
  fi
}

require_case_sensitive() {
  local root=$1 probe
  probe=$(mktemp -d)
  : > "$probe/CaseProbe"
  if [[ -e $probe/caseprobe ]]; then
    rm -rf "$probe"
    cat >&2 <<'EOF'
error: the source tree is on a case-insensitive filesystem.

The kernel contains paths that differ only by case (for example
net/netfilter/xt_HL.c and net/netfilter/xt_hl.c). Git cannot check out or
apply patches reliably there.

Run this on a case-sensitive filesystem: a case-sensitive APFS volume, or the
build container's volume (see docs/build.md).
EOF
    return 1
  fi
  rm -rf "$probe"
}

apply_series() {
  local root=$1 dep=$2 dir=$3
  local series="$root/patches/$dep/series"
  [[ -f $series ]] || return 0
  local patch
  while IFS= read -r patch; do
    [[ -z $patch || $patch == \#* ]] && continue
    git -C "$dir" am --3way "$root/patches/$dep/$patch"
  done < "$series"
}
