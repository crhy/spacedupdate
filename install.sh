#!/bin/bash
set -euo pipefail

# Install Spaced Update into the running Spaced Linux system.
# Usage: sudo ./install.sh
# Backs up existing files to /root/spaced-update-backup first.

DEST_PY=/usr/lib/spaced-linux
DEST_BIN=/usr/local/bin
DEST_APP=/usr/share/applications
DEST_ICON=/usr/share/icons/hicolor/512x512/apps
DEST_POLKIT=/usr/share/polkit-1/actions
BACKUP=/root/spaced-update-backup

mkdir -p "$BACKUP"
copy() {
    src=$1; dst=$2
    if [ -e "$dst" ]; then
        cp -a "$dst" "$BACKUP/$(basename "$dst").bak.$(date +%s)"
    fi
    install -m 0755 "$src" "$dst"
}

copy src/spaced-update.py        "$DEST_PY/spaced-update.py"
copy src/spaced-update-helper    "$DEST_PY/spaced-update-helper"
copy bin/spaced-update           "$DEST_BIN/spaced-update"
install -m 0644 data/spaced-update.desktop "$DEST_APP/spaced-update.desktop"
install -Dm0644 data/icons/org.spacedlinux.SpacedUpdate.png "$DEST_ICON/org.spacedlinux.SpacedUpdate.png"
install -m 0644 data/com.spacedlinux.update.policy "$DEST_POLKIT/com.spacedlinux.update.policy"

echo "Installed. Run: spaced-update"
