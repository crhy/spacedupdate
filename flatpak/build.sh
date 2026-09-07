#!/bin/bash
set -euo pipefail

# Build the Spaced Update Flatpak release into ./repo (an OSTree repository
# suitable for publishing to GitHub Pages).
#
# Usage: bash flatpak/build.sh
# Requires: flatpak and either flatpak-builder or org.flatpak.Builder.
#
# A failed builder or export must stop the release, even if partial files exist.

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
  if [ -n "${SPACED_THEME_SOURCE:-}" ]; then
    mkdir -p flatpak/themes
    cp -a "$SPACED_THEME_SOURCE"/Spaced-* flatpak/themes/
  else
    echo "Syncing pinned Spaced themes from crhy/spaced…"
    tarball=$(mktemp)
    stage=$(mktemp -d)
    trap 'rm -f -- "$tarball"; rm -rf -- "$stage"' EXIT
    theme_ref=${SPACED_THEME_REF:-033116984fad104f337777ad1439b2c2648711d9}
    curl --fail --location --retry 3 -o "$tarball" "https://github.com/crhy/spaced/archive/$theme_ref.tar.gz"
    tar -xzf "$tarball" -C "$stage"
    mkdir -p flatpak/themes
    cp -a "$stage"/*/overlays/usr/share/themes/Spaced-* flatpak/themes/
    rm -rf "$tarball" "$stage"
    trap - EXIT
  fi
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
    flatpak run org.flatpak.Builder \
        --user \
        --force-clean \
        --ccache \
        --default-branch=stable \
        --repo="$REPO" \
        "$STAGE" \
        "$ROOT/flatpak/org.spacedlinux.SpacedUpdate.json"
fi

ostree --repo="$REPO" fsck
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
