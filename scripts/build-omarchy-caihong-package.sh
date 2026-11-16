#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
set -eu
CDPATH=
umask 022

project_dir=$(cd -- "$(dirname -- "$0")/.." && pwd)
release_dir=${1:-${RELEASE_DIR:-"$project_dir/release"}}
version=${OMARCHY_CAIHONG_VERSION:-0.20261114}
[ "$#" -le 1 ] || { echo "usage: $0 [RELEASE_DIR]" >&2; exit 2; }
case "$version" in
	''|*[!A-Za-z0-9.+_]*) echo "invalid OMARCHY_CAIHONG_VERSION" >&2; exit 2 ;;
esac
[ "$(uname -s)" = Linux ] && [ "$(uname -m)" = aarch64 ] || {
	echo "build omarchy-caihong in native Linux/aarch64 (no device access required)" >&2
	exit 1
}
for tool in bsdtar zstd python3 sha256sum; do
	command -v "$tool" >/dev/null 2>&1 || { echo "missing tool: $tool" >&2; exit 1; }
done

mkdir -p "$release_dir"
release_dir=$(cd -- "$release_dir" && pwd)
name="omarchy-caihong-$version-1-aarch64.pkg.tar.zst"
output="$release_dir/$name"
stage=$(mktemp -d "${TMPDIR:-/tmp}/omarchy-caihong-package.XXXXXX")
cleanup()
{
	rm -rf -- "$stage"
	rm -f -- "$output.new"
}
trap cleanup EXIT HUP INT TERM
install -d -m 0755 "$stage/usr/lib/omarchy/caihong"
for operation in setup-boot setup-system setup-user update-verify update-takeover \
	provision-prepare provision-commit provision-verify \
	reset-prepare reset-verify reset-commit reset-rollback luks-slots; do
	# Each dispatch target is a regular executable, never a symlink to a
	# generic dispatcher or a PATH-resolved hook.
	install -m 0755 "$project_dir/packaging/omarchy-caihong/lifecycle" \
		"$stage/usr/lib/omarchy/caihong/$operation"
done
install -D -m 0644 "$project_dir/packaging/omarchy-caihong/hyprland.lua" \
	"$stage/usr/share/omarchy-caihong/hyprland.lua"
install -D -m 0644 "$project_dir/packaging/omarchy-caihong/sddm-hyprland.conf" \
	"$stage/etc/sddm.conf.d/90-caihong-hyprland.conf"
install -D -m 0644 "$project_dir/packaging/omarchy-caihong/uwsm-env" \
	"$stage/usr/share/uwsm/env.d/20-caihong"

size=$(du -sb "$stage/usr" "$stage/etc" | awk '{size += $1} END {print size}')
builddate=${SOURCE_DATE_EPOCH:-$(date +%s)}
case "$builddate" in
	''|*[!0-9]*) echo "invalid SOURCE_DATE_EPOCH" >&2; exit 2 ;;
esac
cat > "$stage/.PKGINFO" <<EOF
pkgname = omarchy-caihong
pkgbase = omarchy-caihong
pkgver = $version-1
pkgdesc = Omarchy lifecycle integration for OnePlus Pad 2 Caihong direct-root Linux
url = https://github.com/Osilvfe/caihong-linux-rootfs
builddate = $builddate
packager = Caihong Omarchy integration
size = $size
arch = aarch64
license = GPL-2.0-only
depend = python
depend = linux-caihong
depend = linux-caihong-boot-verifier=1
depend = caihong-platform
depend = sddm
depend = systemd
depend = uwsm
backup = etc/sddm.conf.d/90-caihong-hyprland.conf
EOF
# Match the native caihong-platform archive/mtree conventions. No .INSTALL:
# package installation stages files only, even in a disposable offline root.
find "$stage" -exec touch -h -d "@$builddate" {} +
bsdtar --uid 0 --gid 0 --format=mtree \
	--options='!all,use-set,type,uid,gid,mode,time,size,sha256,link' \
	-czf "$stage/.MTREE" -C "$stage" .PKGINFO etc usr
bsdtar --uid 0 --gid 0 --uname root --gname root \
	-cf "$stage/package.tar" -C "$stage" .PKGINFO .MTREE etc usr
zstd -q -T"${ZSTD_THREADS:-1}" -15 -f "$stage/package.tar" -o "$output.new"
mv -- "$output.new" "$output"
printf '%s\n' "$name" > "$release_dir/OMARCHY_CAIHONG_PACKAGE"
echo "created pacman package: $output"
sha256sum "$output"
