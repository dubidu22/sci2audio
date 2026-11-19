#!/usr/bin/env bash
# Makes sci2audio-<version>-sources.tar for the release (#215, D-798): the complete source of
# the GPL and LGPL programs the installers carry besides sci2audio itself (whose source is
# the sdist): FFmpeg and LAME as built by build.sh, espeak-ng as espeakng-loader bundles it,
# and build.sh with sources.env. Each archive is checked against its pinned SHA-256.
#
#   bash packaging/ffmpeg/sources_archive.sh <version> <downloads folder> <output folder>
set -euo pipefail

version="$1"
mkdir -p "$2" "$3"
downloads=$(cd "$2" && pwd)
out=$(cd "$3" && pwd)
here=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=packaging/ffmpeg/sources.env
source "$here/sources.env"

sha256() {
  if command -v sha256sum > /dev/null; then sha256sum "$1"; else shasum -a 256 "$1"; fi |
    cut -d " " -f 1
}
same() {  # file expected
  found=$(sha256 "$1")
  if [ "$found" != "$2" ]; then
    echo "$(basename "$1"): SHA-256 $found, expected $2" >&2
    exit 1
  fi
}

ffmpeg="ffmpeg-$FFMPEG_VERSION.tar.xz"
lame="lame-$LAME_VERSION.tar.gz"
espeak="espeak-ng-$ESPEAK_NG_VERSION.tar"
[ -f "$downloads/$ffmpeg" ] || curl -fsSL --retry 4 -o "$downloads/$ffmpeg" "$FFMPEG_URL"
[ -f "$downloads/$lame" ] || curl -fsSL --retry 4 -o "$downloads/$lame" "$LAME_URL"
same "$downloads/$ffmpeg" "$FFMPEG_SHA256"
same "$downloads/$lame" "$LAME_SHA256"
if [ ! -f "$downloads/$espeak" ]; then
  clone=$(mktemp -d)
  git -c advice.detachedHead=false clone --quiet --no-checkout "$ESPEAK_NG_GIT" "$clone"
  git -C "$clone" archive --format=tar --prefix="espeak-ng-$ESPEAK_NG_VERSION/" \
    "$ESPEAK_NG_COMMIT" > "$downloads/$espeak"
  rm -rf "$clone"
fi
same "$downloads/$espeak" "$ESPEAK_NG_SHA256"

stage=$(mktemp -d)
name="sci2audio-$version-sources"
mkdir -p "$stage/$name"
cp "$downloads/$ffmpeg" "$downloads/$lame" "$downloads/$espeak" "$stage/$name/"
cp "$here/build.sh" "$here/sources.env" "$stage/$name/"
cat > "$stage/$name/README.txt" <<TEXT
The source of the free programs inside the sci2audio $version installers, besides
sci2audio itself (sci2audio-$version.tar.gz on the same release page):

- $ffmpeg and $lame: the ffmpeg program in the installers
  (LGPL-2.1-or-later), built by build.sh exactly as the installers workflow builds it:
    bash build.sh <folder holding the two archives> <output folder>
- $espeak: espeak-ng $ESPEAK_NG_VERSION (GPL-3.0-or-later), commit $ESPEAK_NG_COMMIT,
  as espeakng-loader bundles it (its own build script builds it from that tag).

sources.env names each archive's address and SHA-256.
TEXT
tar -cf "$out/$name.tar" -C "$stage" "$name"
rm -rf "$stage"
echo "$out/$name.tar: $(sha256 "$out/$name.tar")"
