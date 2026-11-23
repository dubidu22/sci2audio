"""Writing the audiobook one chapter at a time (#723, LW-01): each chapter's files are
complete as soon as its speech is, and the result is the book `write_audiobook` writes."""

from __future__ import annotations

import hashlib
from pathlib import Path

from output_helpers import Job, make_job

from sci2audio.output import OutputSettings, write_audiobook

ALL = OutputSettings(subtitles=True)


def hashes(folder: Path) -> dict[str, str]:
    return {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(folder.iterdir())
    }


def written_whole(job: Job, out: Path, settings: OutputSettings = ALL) -> dict[str, str]:
    write_audiobook(job.folder, out, job.chapters, job.spoken, job.book, settings)
    return hashes(out)


def test_write_audiobook_output_is_pinned_before_the_split(tmp_path: Path) -> None:
    """Characterisation: the same input gives the same bytes in every file, so the
    chapter-by-chapter writer below can be held to byte equality with it."""
    job = make_job(tmp_path / "job")
    first = written_whole(job, tmp_path / "one")
    assert first == written_whole(job, tmp_path / "two")
    assert list(first) == sorted(
        [
            "A Study of Tones - 01 Introduction.mp3",
            "A Study of Tones - 01 Introduction.srt",
            "A Study of Tones - 01 Introduction.vtt",
            "A Study of Tones - 02 Methods; data = 1 # 2.mp3",
            "A Study of Tones - 02 Methods; data = 1 # 2.srt",
            "A Study of Tones - 02 Methods; data = 1 # 2.vtt",
            "A Study of Tones - 03 Results.mp3",
            "A Study of Tones - 03 Results.srt",
            "A Study of Tones - 03 Results.vtt",
            "A Study of Tones.m4b",
            "A Study of Tones.readalong.json",
            "A Study of Tones.srt",
            "A Study of Tones.vtt",
        ]
    )
