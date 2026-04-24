#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAMP="$(date +%Y%m%d_%H%M%S)"
ARCHIVE_ROOT="${ROOT_DIR}/backups/repo_hygiene/${STAMP}"

mkdir -p "${ARCHIVE_ROOT}/root" "${ARCHIVE_ROOT}/config" "${ARCHIVE_ROOT}/dashboard" "${ARCHIVE_ROOT}/data"

move_if_exists() {
    local source="$1"
    local target_dir="$2"
    if [ -e "${source}" ]; then
        mv "${source}" "${target_dir}/"
        printf 'archived %s -> %s\n' "${source#${ROOT_DIR}/}" "${target_dir#${ROOT_DIR}/}/"
    fi
}

archive_root_pattern() {
    local pattern="$1"
    shopt -s nullglob
    for path in "${ROOT_DIR}"/${pattern}; do
        if [ -e "${path}" ]; then
            move_if_exists "${path}" "${ARCHIVE_ROOT}/root"
        fi
    done
    shopt -u nullglob
}

# Root-level env snapshots and backup copies only.
archive_root_pattern ".env.backup*"
archive_root_pattern "*.bak"
archive_root_pattern "*.bak.*"
archive_root_pattern "*.bak_*"
archive_root_pattern "*.backup"
archive_root_pattern "*.backup.*"
archive_root_pattern "*.manual_backup"
archive_root_pattern "*.backup_fix"

# Known generated backup copies outside the repo root.
move_if_exists "${ROOT_DIR}/config/config.py.backup" "${ARCHIVE_ROOT}/config"
move_if_exists "${ROOT_DIR}/config/gate4_scaled_microscopic.json.backup" "${ARCHIVE_ROOT}/config"
move_if_exists "${ROOT_DIR}/dashboard/server.py.backup" "${ARCHIVE_ROOT}/dashboard"

shopt -s nullglob
for path in "${ROOT_DIR}"/data/gate4_consumer_state.json.bak.*; do
    move_if_exists "${path}" "${ARCHIVE_ROOT}/data"
done
shopt -u nullglob

if [ -z "$(find "${ARCHIVE_ROOT}" -type f -print -quit)" ]; then
    rmdir "${ARCHIVE_ROOT}/root" "${ARCHIVE_ROOT}/config" "${ARCHIVE_ROOT}/dashboard" "${ARCHIVE_ROOT}/data" "${ARCHIVE_ROOT}" 2>/dev/null || true
    echo "no backup snapshots found"
fi
