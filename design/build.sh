#!/usr/bin/env bash
# Rebuild assets/*.svg (and the generated blocks in README.md) from design/data.json.
#
# Needs python3 with `pip install fonttools uharfbuzz` and the static Geist / Geist Mono
# TTFs in $GEIST_DIR (default ~/.fonts). See design/README.md.
set -euo pipefail
D="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$D/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

for g in hero metrics cards; do
  python3 "$D/$g.py" "$TMP"
done

mkdir -p "$ROOT/assets"
for s in "$TMP"/*.svg; do
  out="$ROOT/assets/$(basename "$s")"
  python3 "$D/outline.py" "$s" "$out" >/dev/null
  python3 "$D/compact.py" "$out"
done

python3 "$D/readme.py" "$ROOT/README.md"
