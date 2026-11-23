"""Writing the audiobook one chapter at a time, as the voice finishes each (#723, LW-01).

`BookWriter` writes a chapter's MP3 and subtitles as soon as the app hands it the
chapter's chunks, then rewrites the book's read-along file so that it lists exactly the
chapters whose files are complete; `finish` adds the M4B and the book's subtitles when the
settings ask for them, and the read-along file naming the M4B. The files are byte for byte
the ones `write_audiobook` writes for the same chapters: chapters come in document order,
the timeline places them one after another in whole samples, and a chapter's first chunk
joins nothing, so an earlier chapter never changes when a later one is added.

Every file is put in place as `write_audiobook` puts it (`.<name>.partial`, then a rename;
no half file is ever seen). `vouch` hears of each file before its rename, so the app can
record it first: a killed job leaves only whole chapters its record names.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import tempfile
from collections.abc import Collection, Iterator, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

from sci2audio import __version__
from sci2audio.output import readalong, subtitles
from sci2audio.output.ffmpeg import Ffmpeg, find_ffmpeg
from sci2audio.output.model import BookInfo, Chapter, OutputSettings, Spoken, Written
from sci2audio.output.timeline import Timeline, plan_timeline
from sci2audio.output.wav import ChunkAudio, ChunkAudioError
from sci2audio.output.write import (
    Vouch,
    _atomic,
    _check_cover,
    _feed,
    _ffmetadata,
    _inspect_all,
    _m4b_args,
    _mp3_args,
    _partial,
    _trim_joins,
    audiobook_targets,
)


@dataclass(frozen=True)
class ChapterAudio:
    """A chapter as output placed it: its chunks and their audio after the join trims, so
    the read-along file and the M4B need not read the chunk files' samples again."""

    number: int  # counted from 1 among the book's planned chapters
    title: str
    spoken: tuple[Spoken, ...]
    audio: tuple[ChunkAudio, ...]


def chapter_fingerprint(
    book: BookInfo,
    title: str,
    number: int,
    count: int,
    spoken: Sequence[Spoken],
    settings: OutputSettings,
) -> str:
    """A SHA-256 of everything that decides the bytes of a chapter's files: a chapter file
    whose fingerprint is the same is the file this run would write."""
    cover = None
    if book.cover is not None:
        try:
            cover = hashlib.sha256(book.cover.read_bytes()).hexdigest()
        except OSError:
            cover = "unreadable"
    data = {
        "sci2audio": __version__,
        "book": [book.title, list(book.authors), book.language, cover],
        "chapter": [title, number, count],
        "settings": asdict(settings),
        "chunks": [
            [
                s.chunk.file,
                s.chunk.duration,
                [s.chunk.span.block, s.chunk.span.start, s.chunk.span.end],
                str(s.pause),
                s.text,
                s.continues,
            ]
            for s in spoken
        ],
    }
    text = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class BookWriter:
    """Writes one book's files into `out_folder`, chapter by chapter (see the module).

    `titles` are the titles of every chapter the book is planned to have, in document
    order: they fix every file's name (`audiobook_targets`) and each MP3's track number.
    An existing target is replaced only with `overwrite` or when it is in `keep` (files
    the caller vouches for: its own from an earlier run). Raises as `write_audiobook` does.
    """

    def __init__(
        self,
        job_folder: Path,
        out_folder: Path,
        book: BookInfo,
        titles: Sequence[str],
        settings: OutputSettings | None = None,
        *,
        ffmpeg: Ffmpeg | None = None,
        overwrite: bool = False,
        keep: Collection[Path] = (),
        vouch: Vouch | None = None,
    ) -> None:
        if not titles:
            raise ValueError("a book needs at least one chapter")
        self.job_folder = job_folder
        self.book = book
        self.titles = tuple(titles)
        self.settings = settings or OutputSettings()
        self.cover = _check_cover(book.cover)
        self.run = ffmpeg or Ffmpeg(find_ffmpeg())  # before anything on disk changes
        self.overwrite = overwrite
        self.vouch = vouch
        out_folder = out_folder.absolute()
        out_folder.mkdir(parents=True, exist_ok=True)
        self.targets = audiobook_targets(out_folder, book.title, self.titles, self.settings)
        self._keep = {Path(p).absolute() for p in keep}
        everything = [
            *self.targets.mp3s,
            *([self.targets.m4b] if self.targets.m4b else []),
            *self.targets.subtitles,
            self.targets.readalong,
        ]
        if not overwrite and (
            existing := [t.name for t in everything if t not in self._keep and t.exists()]
        ):
            raise FileExistsError(f"output files exist already, not replacing them: {existing}")
        for target in everything:  # left behind by a run that was killed outright
            _partial(target).unlink(missing_ok=True)
        # the read-along file vouches for the audio: until the first chapter is added
        # again, an old one must not name files this run may replace
        self.targets.readalong.unlink(missing_ok=True)
        self._ours: set[Path] = set()
        self.chapters: list[ChapterAudio] = []
        self.subtitles: list[Path] = []

    def fingerprint(self, number: int, spoken: Sequence[Spoken]) -> str:
        """`chapter_fingerprint` of chapter `number` of this book."""
        return chapter_fingerprint(
            self.book, self.titles[number - 1], number, len(self.titles), spoken, self.settings
        )

    def mp3(self, number: int) -> Path | None:
        return self.targets.mp3s[number - 1] if self.targets.mp3s else None

    def chapter_subtitles(self, number: int) -> tuple[Path, ...]:
        """Chapter `number`'s `.srt` and `.vtt` (none without subtitles or MP3s)."""
        if not (self.settings.subtitles and self.targets.mp3s):
            return ()
        pair = self.targets.subtitles[2 * (number - 1) : 2 * number]
        return tuple(pair)

    def add(self, number: int, spoken: Sequence[Spoken], *, written: bool = False) -> ChapterAudio:
        """Chapter `number` (counted from 1 in `titles`): write its MP3 and subtitles, then
        the read-along file of every chapter so far. With `written`, its files are already
        in place from an earlier run (the caller checked them): only the read-along file
        is written. Chapters must come in document order."""
        if not 1 <= number <= len(self.titles):
            raise ValueError(f"there is no chapter {number} of {len(self.titles)}")
        if self.chapters and number <= self.chapters[-1].number:
            raise ValueError(f"chapter {number} comes after chapter {self.chapters[-1].number}")
        if not spoken:
            raise ValueError("there is nothing to write: no audio chunks")
        audio = _trim_joins(
            _inspect_all(self.job_folder, spoken), [Chapter(self.titles[number - 1], 0)], spoken
        )
        if self.chapters and audio[0].rate != self.chapters[0].audio[0].rate:
            rates = sorted({audio[0].rate, self.chapters[0].audio[0].rate})
            raise ChunkAudioError(f"audio chunks must share one sample rate, found {rates} Hz")
        chapter = ChapterAudio(number, self.titles[number - 1], tuple(spoken), tuple(audio))
        timeline, all_spoken, all_audio = self._timeline([*self.chapters, chapter])
        index = len(self.chapters)
        if not written:
            target = self.mp3(number)
            placed = timeline.chapters[index]
            if target is not None:
                with self._atomic(target) as partial:
                    self.run.run(
                        _mp3_args(
                            timeline,
                            placed,
                            number,
                            len(self.titles),
                            self.book,
                            self.settings,
                            self.cover,
                            partial,
                        ),
                        _feed(timeline, all_audio, placed.first, placed.stop),
                    )
            self._write_subtitles(timeline, all_spoken, self.chapter_subtitles(number), index)
        self.chapters.append(chapter)
        self.subtitles.extend(self.chapter_subtitles(number))
        if self.targets.mp3s:  # without MP3s nothing is playable before the M4B
            self._write_readalong(timeline, all_spoken, None)
        return chapter

    def finish(self) -> Written:
        """The M4B and the book's subtitles when the settings ask for them, then the
        read-along file of the whole book; the files of this book."""
        if not self.chapters:
            raise ValueError("there is nothing to write: no chapter was added")
        timeline, all_spoken, all_audio = self._timeline(self.chapters)
        m4b = self.targets.m4b
        if m4b is not None:
            with self._atomic(m4b) as partial, tempfile.TemporaryDirectory() as temp:
                meta = Path(temp) / "chapters.txt"
                meta.write_text(_ffmetadata(timeline, self.book), encoding="utf-8")
                self.run.run(
                    _m4b_args(timeline, self.book, self.settings, self.cover, meta, partial),
                    _feed(timeline, all_audio, 0, len(all_spoken)),
                )
            if self.settings.subtitles:
                book_pair = tuple(self.targets.subtitles[-2:])
                self._write_subtitles(timeline, all_spoken, book_pair, None)
                self.subtitles.extend(book_pair)
        self._write_readalong(timeline, all_spoken, m4b.name if m4b else None)
        mp3s = tuple(p for c in self.chapters if (p := self.mp3(c.number)) is not None)
        return Written(m4b, mp3s, self.targets.readalong, tuple(self.subtitles))

    def _timeline(
        self, chapters: Sequence[ChapterAudio]
    ) -> tuple[Timeline, list[Spoken], list[ChunkAudio]]:
        spoken: list[Spoken] = []
        audio: list[ChunkAudio] = []
        firsts: list[Chapter] = []
        for chapter in chapters:
            firsts.append(Chapter(chapter.title, len(spoken)))
            spoken.extend(chapter.spoken)
            audio.extend(chapter.audio)
        timeline = plan_timeline(
            firsts, spoken, [a.kept for a in audio], audio[0].rate, self.settings
        )
        return timeline, spoken, audio

    def _write_subtitles(
        self,
        timeline: Timeline,
        spoken: Sequence[Spoken],
        pair: Sequence[Path],
        chapter: int | None,
    ) -> None:
        if not pair:
            return
        cues = subtitles.cues(timeline, spoken, chapter)
        srt, vtt = pair
        for target, text in ((srt, subtitles.to_srt(cues)), (vtt, subtitles.to_vtt(cues))):
            with self._atomic(target) as partial:
                partial.write_text(text, encoding="utf-8", newline="\n")

    def _write_readalong(
        self, timeline: Timeline, spoken: Sequence[Spoken], m4b: str | None
    ) -> None:
        names = [p.name for c in self.chapters if (p := self.mp3(c.number)) is not None]
        data = readalong.build(timeline, spoken, m4b, names or None)
        with self._atomic(self.targets.readalong) as partial:
            partial.write_text(readalong.to_json(data), encoding="utf-8")

    @contextlib.contextmanager
    def _atomic(self, target: Path) -> Iterator[Path]:
        """`write._atomic`; a file this writer put in place, or one in `keep`, is its own
        to replace."""
        replace = self.overwrite or target in self._ours or target in self._keep
        with _atomic(target, replace, self.vouch) as partial:
            yield partial
        self._ours.add(target)
