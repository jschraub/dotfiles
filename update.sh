#!/usr/bin/env bash
# Routine updates only; initial installation remains ./setup.sh.
set -euo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec python3 -B "$root/scripts/update_desktop.py" "$@"
