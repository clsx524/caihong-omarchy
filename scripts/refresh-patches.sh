#!/bin/bash
# Re-export patches/<dep>/series from the commits applied above the pin.
#
# Run this after resolving an upstream update. The submodule is reset to the
# pin afterwards, so the committed state never carries local commits.
set -euo pipefail

root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
# shellcheck source=scripts/lib.sh
source "$root/scripts/lib.sh"
# shellcheck source=pins.env
source "$root/pins.env"

ensure_git_identity "$root"

dep=${1:?usage: refresh-patches.sh <dependency>}
path=$(dep_path "$dep") || { printf 'unknown dependency: %s\n' "$dep" >&2; exit 1; }
var=$(dep_var "$dep")
commit=$(dep_commit "$dep")
dir="$root/$path"

if ! git -C "$dir" merge-base --is-ancestor "$commit" HEAD; then
  printf 'error: %s HEAD does not contain the pin %s\n' "$dep" "$commit" >&2
  exit 1
fi
if [[ $(git -C "$dir" rev-parse HEAD) == "$commit" ]]; then
  printf 'error: %s has no applied commits above the pin\n' "$dep" >&2
  exit 1
fi

rm -f "$root/patches/$dep"/*.patch
git -C "$dir" format-patch --binary --from="$PATCH_AUTHOR" -o "$root/patches/$dep" "$commit"..HEAD
ls -1 "$root/patches/$dep"/*.patch | xargs -n1 basename > "$root/patches/$dep/series"

tree=$(git -C "$dir" rev-parse HEAD^{tree})
sed -i.bak "s/^${var}_TREE=.*/${var}_TREE=${tree}/" "$root/pins.env"
rm -f "$root/pins.env.bak"

printf '%s: %s patches, tree %s\n' "$dep" "$(wc -l < "$root/patches/$dep/series")" "$tree"
git -C "$dir" reset --hard "$commit"
