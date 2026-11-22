#!/usr/bin/env bash
# Cron entry point: fetch every camera from the API, detect traffic on
# ../screenshot/<name>.png and POST current_status back.
#   */5 * * * * /path/to/traffic-live/cron_detect.sh
set -euo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
api="${LIVE_TRAFFIC_API:-https://thordang-mcp-orchestrator.hf.space/vinfast/api/live-traffic}"
lock="$root/.cron_detect.lock"

# Skip this run if the previous one is still going
mkdir "$lock" 2>/dev/null || exit 0
trap 'rmdir "$lock"' EXIT

# Optional $1: JSON string or file to use instead of fetching from the API
if [[ $# -gt 0 ]]; then
  LIVE_TRAFFIC_API="$api" "$root/detect_traffic.sh" "$1" >/dev/null 2>&1
else
  curl -fsS --max-time 30 "$api" | LIVE_TRAFFIC_API="$api" "$root/detect_traffic.sh" - >/dev/null 2>&1
fi
