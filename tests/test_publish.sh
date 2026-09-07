#!/bin/bash
# Publish only to a temporary local bare repository, never a network remote.
set -euo pipefail
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
WORK=$(mktemp -d)
trap 'rm -rf -- "$WORK"' EXIT
mkdir -p "$WORK/source/flatpak" "$WORK/payload" "$WORK/repo"
printf '%s\n' 'release fixture' > "$WORK/payload/fixture.txt"
cp "$ROOT/flatpak/publish.sh" "$WORK/source/flatpak/publish.sh"
git init -q --bare "$WORK/remote.git"
git -C "$WORK/source" init -q
git -C "$WORK/source" remote add origin "$WORK/remote.git"
ostree --repo="$WORK/repo" init --mode=archive
COMMIT=$(ostree --repo="$WORK/repo" commit --branch=app/test/x86_64/stable --tree="dir=$WORK/payload" --subject='fixture')
ostree --repo="$WORK/repo" summary --update
bash "$WORK/source/flatpak/publish.sh" "$WORK/repo"
git clone -q --branch gh-pages "$WORK/remote.git" "$WORK/published"
# Git transports the served objects, but not OSTree's empty local directories.
mkdir -p "$WORK/published/flatpak-repo"/{refs/remotes,refs/mirrors,tmp,extensions}
ostree --repo="$WORK/published/flatpak-repo" fsck
[[ $(ostree --repo="$WORK/published/flatpak-repo" rev-parse app/test/x86_64/stable) == "$COMMIT" ]]
# A repeat with no changes succeeds without treating arbitrary commit errors
# as success, and a corrupt source must stop before it changes the remote.
bash "$WORK/source/flatpak/publish.sh" "$WORK/repo"
BEFORE=$(git --git-dir="$WORK/remote.git" rev-parse gh-pages)
rm "$WORK/repo/objects/${COMMIT:0:2}/${COMMIT:2}.commit"
if bash "$WORK/source/flatpak/publish.sh" "$WORK/repo"; then
    echo 'Corrupt OSTree source unexpectedly published' >&2
    exit 1
fi
[[ $(git --git-dir="$WORK/remote.git" rev-parse gh-pages) == "$BEFORE" ]]
echo 'Publication integrity tests passed.'
