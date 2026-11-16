#!/bin/bash
# Move one dependency to a new upstream ref and replay its series.
#
# On conflict the script stops with the failing patch; resolve it in the
# submodule, continue with git am --continue, then record the new pin with
# scripts/refresh-patches.sh <dependency>.
set -euo pipefail

root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
# shellcheck source=scripts/lib.sh
source "$root/scripts/lib.sh"
# shellcheck source=pins.env
source "$root/pins.env"

ensure_git_identity "$root"

dep=${1:?usage: update-dep.sh <dependency> <ref>}
ref=${2:?usage: update-dep.sh <dependency> <ref>}
path=$(dep_path "$dep") || { printf 'unknown dependency: %s\n' "$dep" >&2; exit 1; }
dir="$root/$path"

git -C "$dir" fetch origin
git -C "$dir" checkout --detach "$ref"

if [[ -f "$root/patches/$dep/series" ]]; then
  while IFS= read -r patch; do
    [[ -z $patch || $patch == \#* ]] && continue
    if ! git -C "$dir" am --3way "$root/patches/$dep/$patch"; then
      cat >&2 <<EOF
conflict: $dep failed at $patch

Resolve the conflict in $dir, then:
  git -C $dir add <files>
  git -C $dir am --continue

When the series applies, record the new pin:
  scripts/refresh-patches.sh $dep
EOF
      exit 1
    fi
  done < "$root/patches/$dep/series"
fi

printf '%s: series applied on %s\n' "$dep" "$(git -C "$dir" rev-parse HEAD)"
printf 'record the new pin with: scripts/refresh-patches.sh %s\n' "$dep"
