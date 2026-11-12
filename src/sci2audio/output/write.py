"""Writing the audiobook: one MP3 per chapter, one M4B with chapter marks, the read-along file.

The chunks' samples are streamed into ffmpeg (no temporary WAV), once per chapter for the
MP3s and once for the whole book for the M4B, with silence for the pauses; the timeline says
where everything lies, so chapter marks and read-along times are exact to the sample.

Every file is written under a temporary name (`.<name>.partial`) in the output folder and
renamed when complete; on any error the partial file is removed, so no half-written file is
left (#10). Existing files are only replaced with `overwrite=True`. The read-along file is
written last: when it exists, every audio file it names is complete.
"""

from __future__ import annotations

import contextlib
import os
import sys
import tempfile
from collections.abc import Iterator, Sequence
from pathlib import Path

from sci2audio import __version__
from sci2audio.output import names, readalong
from sci2audio.output.ffmpeg import LOCAL_ONLY, Ffmpeg, find_ffmpeg
from sci2audio.output.model import BookInfo, Chapter, OutputSettings, Spoken, Written
from sci2audio.output.timeline import ChapterRange, Timeline, check_chapters, plan_timeline
from sci2audio.output.wav import ChunkAudio, ChunkAudioError, frames_of, inspect, silence

AI_LABEL = f"AI-generated audio: text-to-speech made with sci2audio {__version__}."
GENRE = "Audiobook"
# ISO 639-2 codes for the audio stream's language tag; anything else is "und" (undetermined)
_ISO_639_2 = {
    "de": "deu",
    "en": "eng",
    "es": "spa",
    "fr": "fra",
    "it": "ita",
    "nl": "nld",
    "pl": "pol",
    "pt": "por",
}
_JPEG, _PNG = b"\xff\xd8\xff", b"\x89PNG\r\n\x1a\n"


def write_audiobook(
    job_folder: Path,
    out_folder: Path,
    chapters: Sequence[Chapter],
    spoken: Sequence[Spoken],
    book: BookInfo,
    settings: OutputSettings | None = None,
    *,
    ffmpeg: Ffmpeg | None = None,
    overwrite: bool = False,
) -> Written:
    """Write the audiobook of `spoken` into `out_folder` and return the files written.

    Chunk files are relative to `job_folder` (core `AudioChunk.file`) and must be 16-bit mono
    PCM WAV at one sample rate. Raises ValueError for bad input (before anything is written),
    FileExistsError if a target exists and `overwrite` is false, ChunkAudioError if a chunk
    file vanishes or changes during the run, FfmpegError or OSError if writing fails.
    """
    settings = settings or OutputSettings()
    check_chapters(chapters, len(spoken))
    audio = _inspect_all(job_folder, spoken)
    cover = _check_cover(book.cover)
    timeline = plan_timeline(chapters, spoken, [a.frames for a in audio], audio[0].rate, settings)

    run = ffmpeg or Ffmpeg(find_ffmpeg())  # before anything on disk changes

    out_folder = out_folder.absolute()  # ffmpeg gets absolute paths, never "name:" lookalikes
    out_folder.mkdir(parents=True, exist_ok=True)
    base = names.book_name(book.title)
    m4b = out_folder / f"{base}.m4b" if settings.m4b else None
    mp3s = (
        [
            out_folder / names.chapter_file(base, n, len(chapters), c.title)
            for n, c in enumerate(chapters, start=1)
        ]
        if settings.mp3
        else []
    )
    json_file = out_folder / f"{base}.readalong.json"
    targets = [*mp3s, *([m4b] if m4b else []), json_file]
    if not overwrite and (existing := [t.name for t in targets if t.exists()]):
        raise FileExistsError(f"output files exist already, not replacing them: {existing}")
    for target in targets:  # left behind by a run that was killed outright
        _partial(target).unlink(missing_ok=True)
    # the read-along file vouches for the audio: an old one must not outlive a failed rerun
    json_file.unlink(missing_ok=True)

    for chapter, target in zip(timeline.chapters, mp3s, strict=False):
        with _atomic(target, overwrite) as partial:
            run.run(
                _mp3_args(timeline, chapter, len(chapters), book, settings, cover, partial),
                _feed(timeline, audio, chapter.first, chapter.stop),
            )
    if m4b is not None:
        with _atomic(m4b, overwrite) as partial, tempfile.TemporaryDirectory() as temp:
            meta = Path(temp) / "chapters.txt"
            meta.write_text(_ffmetadata(timeline, book), encoding="utf-8")
            run.run(
                _m4b_args(timeline, book, settings, cover, meta, partial),
                _feed(timeline, audio, 0, len(spoken)),
            )
    data = readalong.build(
        timeline, spoken, m4b.name if m4b else None, [p.name for p in mp3s] if mp3s else None
    )
    with _atomic(json_file, overwrite) as partial:
        partial.write_text(readalong.to_json(data), encoding="utf-8")
    return Written(m4b, tuple(mp3s), json_file)


def _inspect_all(job_folder: Path, spoken: Sequence[Spoken]) -> list[ChunkAudio]:
    audio = [inspect(job_folder / s.chunk.file) for s in spoken]
    rates = sorted({a.rate for a in audio})
    if len(rates) > 1:
        raise ChunkAudioError(f"audio chunks must share one sample rate, found {rates} Hz")
    return audio


def _check_cover(cover: Path | None) -> Path | None:
    if cover is None:
        return None
    try:
        with cover.open("rb") as f:
            head = f.read(8)
    except OSError as error:
        raise ValueError(f"cannot read the cover image {cover}: {error}") from None
    if not (head.startswith(_JPEG) or head.startswith(_PNG)):
        raise ValueError(f"the cover image must be a JPEG or PNG file: {cover}")
    return cover.absolute()


def _partial(target: Path) -> Path:
    return target.with_name(f".{target.name}.partial")


@contextlib.contextmanager
def _atomic(target: Path, overwrite: bool) -> Iterator[Path]:
    """Yield a temporary path next to `target`; move it to `target` if the block succeeds,
    remove it if anything goes wrong."""
    partial = _partial(target)
    try:
        yield partial
        _commit(partial, target, overwrite)
    except BaseException:
        with contextlib.suppress(OSError):
            partial.unlink(missing_ok=True)
        raise


def _commit(partial: Path, target: Path, overwrite: bool) -> None:
    """Move the finished file into place. Without `overwrite`, a file that appeared at the
    target since the start of the run is never replaced (FileExistsError)."""
    if overwrite:
        os.replace(partial, target)
    elif sys.platform == "win32":
        os.rename(partial, target)  # refuses an existing target on Windows
    else:
        try:
            os.link(partial, target)  # refuses an existing target
        except FileExistsError:
            raise
        except OSError:  # no hard links here (FAT, some network drives): check, then rename
            if target.exists():
                raise FileExistsError(f"output file appeared during the run: {target}") from None
            os.rename(partial, target)
        else:
            partial.unlink()


def _feed(
    timeline: Timeline, audio: Sequence[ChunkAudio], first: int, stop: int
) -> Iterator[bytes]:
    """The samples of chunks `first` up to `stop`, each after its pause."""
    for placed, chunk in zip(timeline.chunks[first:stop], audio[first:stop], strict=True):
        yield from silence(placed.start - placed.pause_start)
        yield from frames_of(chunk)


def _pcm_input(timeline: Timeline) -> list[str]:
    rate = str(timeline.rate)
    return [*LOCAL_ONLY, "-f", "s16le", "-ar", rate, "-ac", "1", "-i", "pipe:0"]


def _tags(book: BookInfo) -> dict[str, str]:
    return {
        "album": book.title,
        "artist": "; ".join(book.authors),
        "genre": GENRE,
        "comment": AI_LABEL,
    }


def _language(book: BookInfo) -> str:
    return _ISO_639_2.get(book.language.split("-")[0].casefold(), "und")


def _metadata_args(tags: dict[str, str]) -> list[str]:
    args = []
    for key, value in tags.items():
        if value:
            args += ["-metadata", f"{key}={_one_line(value)}"]
    return args


def _mp3_args(
    timeline: Timeline,
    chapter: ChapterRange,
    count: int,
    book: BookInfo,
    settings: OutputSettings,
    cover: Path | None,
    partial: Path,
) -> list[str]:
    args = _pcm_input(timeline)
    if cover is not None:
        args += [*LOCAL_ONLY, "-i", str(cover)]
    args += ["-map", "0:a"]
    if cover is not None:
        args += ["-map", "1:v", "-c:v", "copy", "-disposition:v:0", "attached_pic"]
        args += ["-metadata:s:v", "title=Cover", "-metadata:s:v", "comment=Cover (front)"]
    args += ["-c:a", "libmp3lame", "-b:a", settings.mp3_bitrate, "-id3v2_version", "3"]
    tags = {
        "title": chapter.title,
        **_tags(book),
        "track": f"{chapter.index + 1}/{count}",
        "language": _language(book),
    }
    return [*args, *_metadata_args(tags), "-f", "mp3", "-y", str(partial)]


def _m4b_args(
    timeline: Timeline,
    book: BookInfo,
    settings: OutputSettings,
    cover: Path | None,
    meta: Path,
    partial: Path,
) -> list[str]:
    args = [*_pcm_input(timeline), *LOCAL_ONLY, "-f", "ffmetadata", "-i", str(meta)]
    if cover is not None:
        args += [*LOCAL_ONLY, "-i", str(cover)]
    args += ["-map", "0:a"]
    if cover is not None:
        args += ["-map", "2:v", "-c:v", "copy", "-disposition:v:0", "attached_pic"]
    args += ["-map_metadata", "1", "-map_chapters", "1"]
    args += ["-c:a", "aac", "-b:a", settings.aac_bitrate]
    args += ["-metadata:s:a:0", f"language={_language(book)}", "-movflags", "+faststart"]
    return [*args, "-f", "ipod", "-y", str(partial)]


def _ffmetadata(timeline: Timeline, book: BookInfo) -> str:
    """ffmpeg's metadata file: the book's tags and one CHAPTER per chapter, in samples."""
    lines = [";FFMETADATA1"]
    for key, value in {"title": book.title, **_tags(book)}.items():
        if value:
            lines.append(f"{key}={_escape(value)}")
    for chapter in timeline.chapters:
        lines += [
            "[CHAPTER]",
            f"TIMEBASE=1/{timeline.rate}",
            f"START={chapter.start}",
            f"END={chapter.end}",
            f"title={_escape(chapter.title)}",
        ]
    return "\n".join(lines) + "\n"


def _one_line(value: str) -> str:
    return " ".join(value.split())


def _escape(value: str) -> str:
    """Escape the characters the ffmetadata format treats specially."""
    text = _one_line(value)
    for special in ("\\", "=", ";", "#"):
        text = text.replace(special, "\\" + special)
    return text
