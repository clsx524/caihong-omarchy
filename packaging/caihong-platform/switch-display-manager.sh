#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# Copyright (c) 2026 Osilvfe <osilvfe@gmail.com>
#
# Select SDDM on existing Arch Linux ARM installations that used Plasma Login
# Manager.  Image builders enable SDDM directly; this migration only applies
# to incremental platform package updates and never restarts a live session.

set -eu
CDPATH=

root=${CAIHONG_PLATFORM_ROOT:-/}
systemctl_tool=${CAIHONG_SYSTEMCTL:-systemctl}
case $root in
	/|/*) ;;
	*) echo "invalid CAIHONG_PLATFORM_ROOT: $root" >&2; exit 2 ;;
esac

if [ "${CAIHONG_PLATFORM_SKIP_DISPLAY_MANAGER:-0}" = 1 ]; then
	exit 0
fi

# Only the incremental update installer is allowed to change the selection.
# Offline image builds install and enable SDDM themselves.
if [ "${CAIHONG_PLATFORM_UPDATE_INSTALL:-0}" != 1 ]; then
	exit 0
fi
if [ "${CAIHONG_PLATFORM_IMAGE_BUILD:-0}" = 1 ] ||
	[ -e "$root/run/caihong/offline-rootfs-build" ]; then
	exit 0
fi

if [ ! -x "$root/usr/bin/pacman" ]; then
	# The platform package is also used for non-Arch distributions.  Leave
	# their display manager alone.
	exit 0
fi

run_systemctl()
{
	if [ "$root" = / ]; then
		"$systemctl_tool" "$@"
	else
		"$systemctl_tool" --root="$root" "$@"
	fi
}

alias=$root/etc/systemd/system/display-manager.service

# A display manager can be enabled without updating display-manager.service,
# for example `systemctl enable ly.service`.  Treat any explicitly enabled
# third-party manager as an administrator choice even if the alias still points
# at the distribution default.
for unit in \
	gdm.service gdm3.service lightdm.service ly.service greetd.service \
	lemurs.service lxdm.service nodm.service slim.service wdm.service \
	xdm.service cosmic-greeter.service; do
	if run_systemctl is-enabled --quiet "$unit" >/dev/null 2>&1; then
		echo "keeping administrator-enabled display manager: $unit" >&2
		exit 0
	fi
done

# Never override a display manager that the administrator selected through the
# display-manager.service alias.  Only the stock PLM selection, an empty
# selection, or an existing SDDM selection is managed automatically.
if [ -L "$alias" ]; then
	target=$(readlink -- "$alias")
	case $target in
		sddm.service|*/sddm.service|plasmalogin.service|*/plasmalogin.service) ;;
		*)
			echo "keeping administrator-selected display manager: $target" >&2
			exit 0
			;;
	esac
elif [ -e "$alias" ]; then
	echo "keeping administrator-provided display-manager.service" >&2
	exit 0
fi

if [ ! -e "$root/usr/lib/systemd/system/sddm.service" ]; then
	echo "sddm.service is missing; install the sddm dependency" >&2
	exit 1
fi

# Disable the old unit as well as replacing its alias: PLM may also have been
# enabled directly under a target's wants directory.  Do not stop either manager.
if [ -e "$root/usr/lib/systemd/system/plasmalogin.service" ] ||
	run_systemctl is-enabled --quiet plasmalogin.service >/dev/null 2>&1; then
	run_systemctl disable plasmalogin.service >/dev/null
fi

# SDDM and PLM share the display-manager.service alias.  Keep an existing SDDM
# alias intact, but remove a stale PLM alias before asking systemctl to enable.
if [ -L "$alias" ]; then
	case $(readlink -- "$alias") in
		plasmalogin.service|*/plasmalogin.service) rm -f -- "$alias" ;;
	esac
fi
run_systemctl enable sddm.service >/dev/null

echo "SDDM is now the selected display manager" >&2
