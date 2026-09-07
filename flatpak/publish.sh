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

test -d "$REPO/refs" || {
    echo "Build the repository first: bash flatpak/build.sh" >&2
    exit 1
}

ostree --repo="$REPO" fsck
WORK=$(mktemp -d "${TMPDIR:-/tmp}/spacedupdate-gh-pages.XXXXXX")
trap 'rm -rf -- "$WORK"' EXIT
cd "$WORK"
URL=$(git -C "$ROOT" remote get-url origin 2>/dev/null || echo https://github.com/crhy/spacedupdate.git)
# Distinguish a missing publication branch from a network/authentication error.
branches=$(git ls-remote --heads "$URL" gh-pages)
if [[ -n $branches ]]; then
    git clone --branch gh-pages --single-branch "$URL" .
else
    git init -b gh-pages
    git remote add origin "$URL"
fi

rm -rf flatpak-repo
cp -a "$REPO" flatpak-repo
# OSTree commit objects are part of the repository, including when the files
# happen to end in .commit. Removing them leaves refs pointing at missing data.
ostree --repo=flatpak-repo fsck
git add -A
if ! git diff --cached --quiet; then
    git -c user.name="Spaced Linux Release" \
   -c user.email="release@spaced" \
       commit -m "Flatpak release repository: $(date -u +%Y-%m-%d)"
fi
git push origin gh-pages

echo "Published Flatpak repository at https://crhy.github.io/spacedupdate/flatpak-repo"
