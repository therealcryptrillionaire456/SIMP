#!/bin/bash
# Compatibility shim. Canonical startup now lives in ../startall.sh.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec bash "${ROOT_DIR}/startall.sh" "$@"
