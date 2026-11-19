#!/usr/bin/env bash
# Makes sci2audio-<version>-sources.tar for the release (#215, D-798): the complete source of
# the GPL and LGPL programs the installers carry besides sci2audio itself (whose source is
# the sdist): FFmpeg and LAME as built by build.sh, espeak-ng as espeakng-loader bundles it,
# the AppImage runtime with the libfuse and squashfuse it links (#635 F3), and build.sh with
# sources.env. Each archive is checked against its pinned SHA-256.
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

archive() {  # git url, commit, name (no .tar): `git archive` of that commit, as a person can repeat
  if [ ! -f "$downloads/$3.tar" ]; then
    clone=$(mktemp -d)
    git -c advice.detachedHead=false clone --quiet --no-checkout "$1" "$clone"
    git -C "$clone" archive --format=tar --prefix="$3/" "$2" > "$downloads/$3.tar"
    rm -rf "$clone"
  fi
}

ffmpeg="ffmpeg-$FFMPEG_VERSION.tar.xz"
lame="lame-$LAME_VERSION.tar.gz"
espeak="espeak-ng-$ESPEAK_NG_VERSION.tar"
runtime="type2-runtime-$APPIMAGE_RUNTIME_VERSION.tar"
fuse="fuse-$LIBFUSE_VERSION.tar.xz"
squashfuse="squashfuse-$SQUASHFUSE_VERSION.tar"
[ -f "$downloads/$ffmpeg" ] || curl -fsSL --retry 4 -o "$downloads/$ffmpeg" "$FFMPEG_URL"
[ -f "$downloads/$lame" ] || curl -fsSL --retry 4 -o "$downloads/$lame" "$LAME_URL"
[ -f "$downloads/$fuse" ] || curl -fsSL --retry 4 -o "$downloads/$fuse" "$LIBFUSE_URL"
archive "$ESPEAK_NG_GIT" "$ESPEAK_NG_COMMIT" "espeak-ng-$ESPEAK_NG_VERSION"
archive "$APPIMAGE_RUNTIME_GIT" "$APPIMAGE_RUNTIME_COMMIT" "type2-runtime-$APPIMAGE_RUNTIME_VERSION"
archive "$SQUASHFUSE_GIT" "$SQUASHFUSE_COMMIT" "squashfuse-$SQUASHFUSE_VERSION"
same "$downloads/$ffmpeg" "$FFMPEG_SHA256"
same "$downloads/$lame" "$LAME_SHA256"
same "$downloads/$espeak" "$ESPEAK_NG_SHA256"
same "$downloads/$runtime" "$APPIMAGE_RUNTIME_SOURCE_SHA256"
same "$downloads/$fuse" "$LIBFUSE_SHA256"
same "$downloads/$squashfuse" "$SQUASHFUSE_SHA256"

stage=$(mktemp -d)
name="sci2audio-$version-sources"
mkdir -p "$stage/$name"
for file in "$ffmpeg" "$lame" "$espeak" "$runtime" "$fuse" "$squashfuse"; do
  cp "$downloads/$file" "$stage/$name/"
done
cp "$here/build.sh" "$here/sources.env" "$stage/$name/"
cat > "$stage/$name/README.txt" <<TEXT
The source of the free programs inside the sci2audio $version installers, besides
sci2audio itself (sci2audio-$version.tar.gz on the same release page):

- $ffmpeg and $lame: the ffmpeg program in the installers
  (LGPL-2.1-or-later), built by build.sh exactly as the installers workflow builds it:
    bash build.sh <folder holding the two archives> <output folder>
- $espeak: espeak-ng $ESPEAK_NG_VERSION (GPL-3.0-or-later), commit $ESPEAK_NG_COMMIT,
  as espeakng-loader bundles it (its own build script builds it from that tag).
- $runtime: the AppImage type-2 runtime $APPIMAGE_RUNTIME_VERSION (MIT), commit
  $APPIMAGE_RUNTIME_COMMIT, which starts the Linux AppImage. Its
  scripts/common/install-dependencies.sh builds it with the two below, statically
  linked, and its patches/ hold the change it makes to libfuse:
  - $fuse: libfuse $LIBFUSE_VERSION (the library: LGPL-2.1-only);
  - $squashfuse: squashfuse $SQUASHFUSE_VERSION (BSD-2-Clause), commit $SQUASHFUSE_COMMIT.

sources.env names each archive's address and SHA-256.
TEXT
tar -cf "$out/$name.tar" -C "$stage" "$name"
rm -rf "$stage"
echo "$out/$name.tar: $(sha256 "$out/$name.tar")"
