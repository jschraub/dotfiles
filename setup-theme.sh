#!/usr/bin/env bash
# Portable, user-only appearance deployment. Package installs live in setup.sh.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$SCRIPT_DIR/scripts/apply_theme.py" "$@"
