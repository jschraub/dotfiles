#!/usr/bin/env bash
# Read-only drift audit. See SETUP-AUDIT.md for coverage and exit codes.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$SCRIPT_DIR/scripts/check_setup.py" "$@"
