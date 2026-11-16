#!/bin/bash
# Check out every dependency at its pinned commit and apply the local series.
#
# The submodules stay at upstream commits; the only local changes are the
# patches under patches/<dep>/. The resulting tree hash must match pins.env.
set -euo pipefail

root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
# shellcheck source=scripts/lib.sh
source "$root/scripts/lib.sh"
# shellcheck source=pins.env
source "$root/pins.env"

ensure_git_identity "$root"
require_case_sensitive "$root"

if [[ -f "$root/.gitmodules" ]]; then
  git -C "$root" submodule update --init --recursive
fi

mkdir -p "$root/build"
resolved="$root/build/dependencies.resolved.env"
: > "$resolved"

for dep in "${DEP_NAMES[@]}"; do
  path=$(dep_path "$dep")
  dir="$root/$path"
  commit=$(dep_commit "$dep")
  tree=$(dep_tree "$dep")

  if [[ -n $(git -C "$dir" status --porcelain --untracked-files=no) ]]; then
    printf 'error: %s has uncommitted changes; commit or discard them first\n' "$dep" >&2
    exit 1
  fi

  git -C "$dir" checkout --detach "$commit"
  git -C "$dir" reset --hard
  git -C "$dir" clean -fd
  apply_series "$root" "$dep" "$dir"

  actual=$(git -C "$dir" rev-parse HEAD^{tree})
  if [[ $actual != "$tree" ]]; then
    printf 'error: %s tree %s != expected %s\n' "$dep" "$actual" "$tree" >&2
    exit 1
  fi

  var=$(dep_var "$dep")
  url=$(git -C "$dir" remote get-url origin)
  {
    printf '%s_REPOSITORY=%s\n' "$var" "$url"
    printf '%s_REF=%s\n' "$var" "$commit"
    printf '%s_COMMIT=%s\n' "$var" "$commit"
  } >> "$resolved"

  printf '%-24s %s\n' "$dep" "$actual"
done
