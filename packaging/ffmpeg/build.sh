#!/usr/bin/env bash
# Builds the audio-only FFmpeg that sci2audio's installers bundle (#215, D-798).
#
#   bash packaging/ffmpeg/build.sh <downloads folder> <output folder>
#
# It is LGPL-2.1-or-later (FFmpeg without --enable-gpl) with LAME (LGPL-2.0-or-later)
# linked in statically, so its complete source is the two archives named in sources.env
# and this script. It holds only what sci2audio's output layer runs (output/ffmpeg.py,
# app/audio.py): 16-bit PCM from a pipe, encoded to MP3 (LAME) or AAC in an M4B (ipod),
# chapters and tags from an ffmetadata file, a JPEG or PNG cover copied in and decoded
# once to check it; and what the fast tests use to read the results back and to make
# test covers (MP3, M4B, SRT and WebVTT in; raw PCM, ffmetadata, SRT and images out; the lavfi
# colour source), so the same tests run against this build (D-798). Files and pipes only:
# no network protocol is built in.
# Runs on Linux and macOS, and on Windows in an MSYS2 MinGW64 shell.
set -euo pipefail

downloads=$(cd "$1" && pwd)
mkdir -p "$2"
out=$(cd "$2" && pwd)
here=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=packaging/ffmpeg/sources.env
source "$here/sources.env"

sha256() {  # file: its SHA-256 (sha256sum on Linux and MSYS2, shasum on macOS)
  if command -v sha256sum > /dev/null; then sha256sum "$1"; else shasum -a 256 "$1"; fi |
    cut -d " " -f 1
}
fetch() {  # url sha256 file
  if [ ! -f "$downloads/$3" ]; then curl -fsSL --retry 4 -o "$downloads/$3" "$1"; fi
  found=$(sha256 "$downloads/$3")
  if [ "$found" != "$2" ]; then
    echo "$3: SHA-256 $found, expected $2" >&2
    exit 1
  fi
}
fetch "$FFMPEG_URL" "$FFMPEG_SHA256" "ffmpeg-$FFMPEG_VERSION.tar.xz"
fetch "$LAME_URL" "$LAME_SHA256" "lame-$LAME_VERSION.tar.gz"

work=$(mktemp -d)
prefix="$work/prefix"
jobs=$(getconf _NPROCESSORS_ONLN 2>/dev/null || echo 2)

tar -xzf "$downloads/lame-$LAME_VERSION.tar.gz" -C "$work"
(
  cd "$work/lame-$LAME_VERSION"
  ./configure --prefix="$prefix" --disable-shared --enable-static --disable-frontend \
    --disable-decoder --disable-gtktest --disable-dependency-tracking
  make -j"$jobs"
  make install
)

extra_ldflags="-L$prefix/lib"
case "$(uname -s)" in
  MINGW* | MSYS*) extra_ldflags="$extra_ldflags -static" ;;  # no MinGW DLLs beside it
esac

tar -xJf "$downloads/ffmpeg-$FFMPEG_VERSION.tar.xz" -C "$work"
(
  cd "$work/ffmpeg-$FFMPEG_VERSION"
  ./configure \
    --prefix="$prefix" \
    --disable-everything --disable-autodetect --disable-network --disable-doc \
    --disable-debug --disable-ffplay --disable-ffprobe --disable-x86asm \
    --enable-static --disable-shared --enable-small \
    --enable-libmp3lame --enable-zlib \
    --extra-cflags="-I$prefix/include" --extra-ldflags="$extra_ldflags" \
    --enable-protocol=file,pipe \
    --enable-demuxer=pcm_s16le,ffmetadata,image2,image_jpeg_pipe,image_png_pipe,mjpeg \
    --enable-muxer=mp3,ipod,null \
    --enable-decoder=pcm_s16le,mjpeg,png \
    --enable-encoder=libmp3lame,aac,wrapped_avframe \
    --enable-parser=mjpeg,png \
    --enable-filter=aresample,aformat,anull,null,format,scale \
    --enable-demuxer=mov,mp3,srt,webvtt,wav \
    --enable-muxer=pcm_s16le,ffmetadata,srt,image2,wav \
    --enable-decoder=aac,mp3float,subrip,webvtt,wrapped_avframe \
    --enable-encoder=pcm_s16le,mjpeg,png,srt,subrip \
    --enable-parser=aac,mpegaudio \
    --enable-indev=lavfi --enable-filter=color,buffer,buffersink,abuffer,abuffersink \
    --enable-swresample --enable-swscale
  make -j"$jobs"
  make install
)

exe=ffmpeg
case "$(uname -s)" in MINGW* | MSYS*) exe=ffmpeg.exe ;; esac
cp "$prefix/bin/$exe" "$out/$exe"
# the licences that travel with the program (the bundle's licenses/ffmpeg folder)
mkdir -p "$out/licenses"
cp "$work/ffmpeg-$FFMPEG_VERSION/COPYING.LGPLv2.1" "$out/licenses/FFmpeg-COPYING.LGPLv2.1"
cp "$work/ffmpeg-$FFMPEG_VERSION/LICENSE.md" "$out/licenses/FFmpeg-LICENSE.md"
cp "$work/lame-$LAME_VERSION/COPYING" "$out/licenses/LAME-COPYING"
"$out/$exe" -hide_banner -buildconf > "$out/licenses/FFmpeg-configuration.txt"
"$out/$exe" -hide_banner -version | head -n 1
rm -rf "$work"
