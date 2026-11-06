#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
venv="$root/.venv"

# System python3 has no Pillow, so keep it in a venv next to the script
[[ -x $venv/bin/python ]] || python3 -m venv "$venv"
"$venv/bin/python" -c 'import PIL' 2>/dev/null || "$venv/bin/python" -m pip install --quiet --disable-pip-version-check pillow

exec "$venv/bin/python" "$root/detect_traffic.py" "$@"
