#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# Copyright (c) 2026 Osilvfe <osilvfe@gmail.com>
#
# Compatibility entry point for the build scripts. Dependencies are now
# submodules pinned in pins.env; prepare-sources.sh checks them out and
# applies the local patch series.
set -eu
CDPATH=

project_dir=$(cd -- "$(dirname -- "$0")/.." && pwd)
exec "$project_dir/scripts/prepare-sources.sh"
