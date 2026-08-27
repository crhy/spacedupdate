#!/bin/bash
set -euo pipefail

# Build the Spaced Update Flatpak release into ./repo (an OSTree repository
# suitable for publishing to GitHub Pages).
#
# Usage: bash flatpak/build.sh
# Requires: flatpak and either flatpak-builder or org.flatpak.Builder.
#
# The Builder app builds every module reliably, but its final in-sandbox
# command check resolves /app against the Builder's own app tree and always
# reports the app command as missing. The exported stage is correct, so the
# finish and export steps run here on the host.

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"

# The release version lives in VERSION and must match APP_VERSION in the
# source.
version=$(cat VERSION)
grep -q "APP_VERSION = \"$version\"" src/spaced-update.py || {
    echo "Version mismatch: VERSION ($version) != APP_VERSION in src/spaced-update.py." >&2
    exit 1
}

# The bundled themes are generated from the crhy/spaced tree, not committed
# here. Sync them before building when the local copy is missing.
if [ ! -d flatpak/themes/Spaced-Dark ]; then
    echo "Syncing Spaced themes from crhy/spaced…"
    tarball=$(mktemp)
    stage=$(mktemp -d)
    curl -sL -o "$tarball" https://github.com/crhy/spaced/archive/refs/heads/main.tar.gz
    tar -xzf "$tarball" -C "$stage"
    mkdir -p flatpak/themes
    mv "$stage"/*/overlays/usr/share/themes/Spaced-* flatpak/themes/ 2>/dev/null || true
    rm -rf "$tarball" "$stage"
    [ -d flatpak/themes/Spaced-Dark ] || {
        echo "Theme sync failed: extract overlays/usr/share/themes/Spaced-* from crhy/spaced into flatpak/themes/." >&2
        exit 1
    }
fi

BUILD="${BUILD_DIR:-$ROOT/flatpak-build}"
REPO="$BUILD/repo"
STAGE="$BUILD/stage"

rm -rf "$STAGE"
mkdir -p "$BUILD" "$REPO" "$STAGE"

if command -v flatpak-builder >/dev/null 2>&1; then
    flatpak-builder \
        --user \
        --force-clean \
        --ccache \
        --default-branch=stable \
        --repo="$REPO" \
        "$STAGE" \
        "$ROOT/flatpak/org.spacedlinux.SpacedUpdate.json"
else
    set +e
    flatpak run org.flatpak.Builder \
        --user \
        --force-clean \
        --ccache \
        --repo="$REPO" \
        "$STAGE" \
        "$ROOT/flatpak/org.spacedlinux.SpacedUpdate.json"
    builder_status=$?
    set -e
    if [ "$builder_status" -ne 0 ] && [ ! -f "$STAGE/files/bin/spaced-update" ]; then
        echo "Module build failed (stage incomplete); see the Builder output above." >&2
        exit 1
    fi

    flatpak build-finish \
        --command=spaced-update \
        --share=network \
        --socket=x11 \
        --socket=wayland \
        --device=dri \
        --filesystem=home \
        --talk-name=org.freedesktop.Flatpak \
        --system-talk-name=org.freedesktop.PolicyKit1 \
        "$STAGE"

    rm -f "$REPO/refs/heads/app/org.spacedlinux.SpacedUpdate/x86_64/stable"
    flatpak build-export --no-update-summary "$REPO" "$STAGE" stable
fi

flatpak build-update-repo --generate-static-deltas "$REPO"

bundle="$ROOT/SpacedUpdate-${version}-x86_64.flatpak"
flatpak build-bundle \
    --arch=x86_64 \
    --repo-url=https://crhy.github.io/spacedbazaar/flatpak-repo/ \
    --runtime-repo=https://flathub.org/repo/flathub.flatpakrepo \
    "$REPO" "$bundle" org.spacedlinux.SpacedUpdate stable

test -s "$STAGE/files/share/metainfo/org.spacedlinux.SpacedUpdate.metainfo.xml"
test -s "$STAGE/files/share/icons/hicolor/512x512/apps/org.spacedlinux.SpacedUpdate.png"

echo "Repository ready at: $REPO"
echo "Bundle ready at: $bundle"
