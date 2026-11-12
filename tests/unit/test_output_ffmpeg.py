"""The output stage with the real, bundled ffmpeg on a few seconds of generated audio (#69).

These stay in the fast suite on purpose (#69 plan, point C): they prove on every PR, on all
three systems, that the ffmpeg imageio-ffmpeg bundles writes MP3 and M4B with chapters,
cover and the AI label, and that the timing is exact. Files are read back by parsing
`ffmpeg -i` and `ffmpeg -f ffmetadata` output (the wheel ships no ffprobe).
"""

from __future__ import annotations

import itertools
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest
from output_helpers import (
    RATE,
    chapters_of,
    decoded_samples,
    ffmetadata,
    ffmpeg_exe,
    make_job,
    streams,
    tags_of,
)

from sci2audio.output import AI_LABEL, OutputSettings, read_readalong, write_audiobook
from sci2audio.output.ffmpeg import LOCAL_ONLY, Ffmpeg, FfmpegError, find_ffmpeg
from sci2audio.output.timeline import plan_timeline


@pytest.fixture
def cover(tmp_path: Path) -> Path:
    path = tmp_path / "cover.jpg"
    subprocess.run(
        [
            ffmpeg_exe(),
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=blue:s=32x32",
            "-frames:v",
            "1",
            str(path),
        ],
        check=True,
    )
    return path


def test_writes_m4b_and_mp3s_with_exact_chapters_tags_and_cover(
    tmp_path: Path, cover: Path
) -> None:
    job = make_job(tmp_path / "job", cover=cover)
    settings = OutputSettings()
    written = write_audiobook(job.folder, tmp_path / "out", job.chapters, job.spoken, job.book)
    frames = [n for chapter in ((4800, 2400), (3600,), (2400, 1200, 6000)) for n in chapter]
    timeline = plan_timeline(job.chapters, job.spoken, frames, RATE, settings)

    assert written.m4b is not None
    assert written.m4b.name == "A Study of Tones.m4b"
    assert [p.name for p in written.mp3s] == [
        "A Study of Tones - 01 Introduction.mp3",
        "A Study of Tones - 02 Methods; data = 1 # 2.mp3",
        "A Study of Tones - 03 Results.mp3",
    ]

    # M4B: chapter marks exact to the sample, tags with the AI label, AAC audio and a cover
    meta = ffmetadata(written.m4b)
    assert chapters_of(meta) == [(c.start, c.end, c.title) for c in timeline.chapters]
    tags = tags_of(meta)
    assert tags["title"] == "A Study of Tones"
    assert tags["artist"] == "Ada Lovelace; Alan Turing"
    assert tags["comment"] == AI_LABEL
    assert decoded_samples(written.m4b) == timeline.total
    lines = streams(written.m4b)
    assert any("Audio: aac" in line and f"{RATE} Hz" in line and "(eng)" in line for line in lines)
    assert any("attached pic" in line for line in lines)

    # MP3s: one per chapter, exact length, title, track number and the AI label each
    for index, (mp3, chapter) in enumerate(zip(written.mp3s, timeline.chapters, strict=True)):
        tags = tags_of(ffmetadata(mp3))
        assert tags["title"] == chapter.title
        assert tags["album"] == "A Study of Tones"
        assert tags["track"] == f"{index + 1}/3"
        assert tags["comment"] == AI_LABEL
        assert decoded_samples(mp3) == chapter.end - chapter.start
        lines = streams(mp3)
        assert any("Audio: mp3" in line and f"{RATE} Hz" in line for line in lines)
        assert any("attached pic" in line for line in lines)

    # the read-along file names the files and matches the timeline
    data = read_readalong(written.readalong)
    assert data.m4b == written.m4b.name
    assert [c.mp3 for c in data.chapters] == [p.name for p in written.mp3s]
    assert data.duration == round(timeline.total / RATE, 3)
    assert sorted(p.name for p in (tmp_path / "out").iterdir()) == sorted(
        [written.m4b.name, *(p.name for p in written.mp3s), written.readalong.name]
    )


def test_mp3_only_and_m4b_only(tmp_path: Path) -> None:
    job = make_job(tmp_path / "job", frames=((2400,), (2400,)))
    only_mp3 = write_audiobook(
        job.folder, tmp_path / "a", job.chapters, job.spoken, job.book, OutputSettings(m4b=False)
    )
    assert only_mp3.m4b is None
    assert len(only_mp3.mp3s) == 2
    assert read_readalong(only_mp3.readalong).m4b is None
    only_m4b = write_audiobook(
        job.folder, tmp_path / "b", job.chapters, job.spoken, job.book, OutputSettings(mp3=False)
    )
    assert only_m4b.mp3s == ()
    assert [c.mp3 for c in read_readalong(only_m4b.readalong).chapters] == [None, None]
    assert only_m4b.m4b is not None
    assert len(chapters_of(ffmetadata(only_m4b.m4b))) == 2


def test_a_rerun_with_overwrite_writes_identical_files(tmp_path: Path) -> None:
    """Resume (#71) reruns output on its own folder: the result must not depend on the run."""
    job = make_job(tmp_path / "job", frames=((2400, 1200), (2400,)))
    out = tmp_path / "out"
    first = write_audiobook(job.folder, out, job.chapters, job.spoken, job.book)
    before = {p.name: p.read_bytes() for p in out.iterdir()}
    second = write_audiobook(job.folder, out, job.chapters, job.spoken, job.book, overwrite=True)
    assert second == first
    assert {p.name: p.read_bytes() for p in out.iterdir()} == before


def test_every_ffmpeg_input_is_limited_to_local_files(tmp_path: Path, cover: Path) -> None:
    """No network (CLAUDE.md): each `-i` is preceded by the file,pipe protocol whitelist."""
    commands: list[list[str]] = []
    real = Ffmpeg(find_ffmpeg())

    class Recording(Ffmpeg):
        def run(self, args, feed=()):  # type: ignore[no-untyped-def]
            commands.append(list(args))
            return real.run(args, feed)

    job = make_job(tmp_path / "job", frames=((2400,), (2400,)), cover=cover)
    write_audiobook(
        job.folder, tmp_path / "out", job.chapters, job.spoken, job.book, ffmpeg=Recording(real.exe)
    )
    assert len(commands) == 3  # two MP3s and the M4B
    for args in commands:
        inputs = [i for i, arg in enumerate(args) if arg == "-i"]
        assert inputs
        for before, at in zip([0, *inputs], inputs, strict=False):
            options = args[before:at]
            pairs = list(itertools.pairwise(options))
            assert LOCAL_ONLY in pairs, args


def test_ffmpeg_refuses_a_network_address(tmp_path: Path) -> None:
    """The whitelist stops ffmpeg before it connects anywhere (port 9 is never contacted)."""
    with pytest.raises(FfmpegError, match=r"(?i)protocol|whitelist"):
        Ffmpeg(find_ffmpeg()).run(
            [*LOCAL_ONLY, "-i", "http://127.0.0.1:9/a.wav", "-f", "null", "-"]
        )


def test_percent_signs_in_names_are_taken_literally(tmp_path: Path) -> None:
    """ffmpeg reads "%d" in some file names as a number pattern; ours must stay literal."""
    cover = tmp_path / "cover%d 100%.jpg"
    subprocess.run(
        [
            ffmpeg_exe(),
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=red:s=16x16",
            "-frames:v",
            "1",
            "-update",
            "1",
            str(cover),
        ],
        check=True,
    )
    job = make_job(tmp_path / "job", frames=((2400,), (1200,)), titles=("50% done", "x"))
    book = replace(job.book, title="100% Science", cover=cover)
    written = write_audiobook(job.folder, tmp_path / "out%03d", job.chapters, job.spoken, book)
    assert written.m4b == tmp_path / "out%03d" / "100% Science.m4b"
    assert written.mp3s[0].name == "100% Science - 01 50% done.mp3"
    assert any("attached pic" in line for line in streams(written.m4b))
    assert tags_of(ffmetadata(written.mp3s[0]))["title"] == "50% done"
