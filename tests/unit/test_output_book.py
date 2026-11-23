"""The whole book as one file, built on request from the chapters already spoken (#725,
LW-03): an M4B byte for byte the one `BookWriter.finish` writes, or one MP3 with ID3 chapter
marks (`CHAP`/`CTOC`) carrying the chapter files' tags and cover."""

from __future__ import annotations

import hashlib
from pathlib import Path

from output_helpers import Job, make_job
from test_output_chapters import ALL, by_chapter, cover_file, hashes

from sci2audio.output import write_audiobook


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_finish_writes_the_m4b_it_wrote_before_the_book_file_split(tmp_path: Path) -> None:
    """Characterisation: `finish`'s M4B and the book's subtitles are the files
    `write_audiobook` writes, so moving the M4B into `write_book_file` is held to them."""
    job: Job = make_job(tmp_path / "job", cover=cover_file(tmp_path))
    write_audiobook(job.folder, tmp_path / "whole", job.chapters, job.spoken, job.book, ALL)
    whole = hashes(tmp_path / "whole")
    written = by_chapter(job, tmp_path / "parts", ALL).finish()
    assert written.m4b is not None
    for name in ("A Study of Tones.m4b", "A Study of Tones.srt", "A Study of Tones.vtt"):
        assert sha(tmp_path / "parts" / name) == whole[name]
