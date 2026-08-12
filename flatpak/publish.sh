#!/bin/bash
set -euo pipefail

# Publish the Flatpak release repository to the gh-pages branch, so
# https://crhy.github.io/spacedupdate/flatpak-repo serves it as a static
# OSTree remote. Clients then run:
#   flatpak --user remote-add --if-not-exists spacedupdate \
#       https://crhy.github.io/spacedupdate/flatpak-repo
#   flatpak --user install spacedupdate org.spacedlinux.SpacedUpdate
#
# Usage: bash flatpak/publish.sh [flatpak-build/repo]
# Publishes the current directory's Git history plus the built repository.

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
REPO="${1:-$ROOT/flatpak-build/repo}"
WORK="${TMPDIR:-/tmp}/spacedupdate-gh-pages"

test -d "$REPO/refs" || {
    echo "Build the repository first: bash flatpak/build.sh" >&2
    exit 1
}

rm -rf "$WORK"
mkdir -p "$WORK"
cd "$WORK"
if git clone --branch gh-pages --single-branch "$ROOT" . 2>/dev/null; then
    :
else
    git init -b gh-pages
    git remote add origin "$(git -C "$ROOT" remote get-url origin 2>/dev/null || echo https://github.com/crhy/spacedupdate.git)"
fi

rm -rf flatpak-repo
cp -a "$REPO" flatpak-repo
find flatpak-repo -name '*.commit' -delete
git add -A
git -c user.name="Spaced Linux Release" \
   -c user.email="release@spaced" \
   commit -m "Flatpak release repository: $(date -u +%Y-%m-%d)" || true
git push origin gh-pages

echo "Published Flatpak repository at https://crhy.github.io/spacedupdate/flatpak-repo"