#!/usr/bin/env bash
set -euo pipefail

dir='/Users/thodang/Pictures/Snagit/live'
captured="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/captured"

if [[ ! -d $dir ]]; then
  echo "Source dir not found: $dir" >&2
  exit 1
fi

mkdir -p "$captured"

i=0
# Oldest first by mtime; ls skips dotfiles such as .DS_Store
ls -1tr "$dir" | while IFS= read -r name; do
  [[ -f $dir/$name ]] || continue
  # Not ((i++)): it returns 1 when i is 0 and trips set -e
  i=$((i + 1))
  # One mv renames and moves, so an unprocessed source l_*.png is never overwritten
  mv -f -- "$dir/$name" "$captured/l_$i.png"
done
