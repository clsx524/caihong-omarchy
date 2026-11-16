#!/bin/bash
# Apply every series to a clean worktree at its pin and compare tree hashes.
#
# This catches patches that apply with fuzz but change semantics: the tree
# hash in pins.env is the contract.
set -euo pipefail

root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
# shellcheck source=scripts/lib.sh
source "$root/scripts/lib.sh"
# shellcheck source=pins.env
source "$root/pins.env"

ensure_git_identity "$root"
require_case_sensitive "$root"

for dep in "${DEP_NAMES[@]}"; do
  path=$(dep_path "$dep")
  dir="$root/$path"
  commit=$(dep_commit "$dep")
  tree=$(dep_tree "$dep")

  tmp=$(mktemp -d)
  git -C "$dir" worktree add --detach "$tmp" "$commit" >/dev/null
  apply_series "$root" "$dep" "$tmp"
  actual=$(git -C "$tmp" rev-parse HEAD^{tree})
  git -C "$dir" worktree remove --force "$tmp"

  if [[ $actual != "$tree" ]]; then
    printf 'error: %s tree %s != expected %s\n' "$dep" "$actual" "$tree" >&2
    exit 1
  fi
  printf '%-24s ok %s\n' "$dep" "$actual"
done
