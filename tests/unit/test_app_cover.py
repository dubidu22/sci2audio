"""The cover in the audio job (#73, OU-01, D-313): the file's own cover is written to the
working folder and goes into every MP3 and the M4B. A file without one, a cover that cannot
be read, and a full disk while writing it all give an audiobook without a cover, never a
failed job (tests.md: fault injection for file writing)."""

from __future__ import annotations

import errno
import zipfile
from pathlib import Path

import pytest
from audio_fakes import FakeVoice
from epub_maker import Item, make_epub
from output_helpers import streams
from pdf_maker import Text, make_pdf

from sci2audio.app import JobSettings, run_audio_job
from sci2audio.app import audio as audio_module
from sci2audio.app import files as files_module
from sci2audio.extraction import Cover
from sci2audio.output import find_ffmpeg

CORPUS = Path(__file__).resolve().parents[1] / "corpus"
TIME_MACHINE = CORPUS / "epub" / "wells-the-time-machine.epub"


def cover_jpeg() -> bytes:
    """A real JPEG for ffmpeg to embed: the corpus EPUB's own cover."""
    with zipfile.ZipFile(TIME_MACHINE) as archive:
        return archive.read("epub/images/cover.jpg")


def small_epub(folder: Path, cover: bytes | None = None) -> Path:
    items = []
    if cover is not None:
        items.append(Item("cover", "cover.jpg", "image/jpeg", "cover-image", cover, False))
    path = folder / "book.epub"
    path.write_bytes(make_epub("<p>A short book.</p><p>It has two lines.</p>", items=items))
    return path


def small_pdf(folder: Path) -> Path:
    path = folder / "note.pdf"
    path.write_bytes(make_pdf([Text("A short note.", 72, 100, size=11)]))
    return path


def run(source: Path, folder: Path, overwrite: bool = False):  # type: ignore[no-untyped-def]
    settings = JobSettings(output_folder=folder / "out")
    voice = FakeVoice().source()
    return run_audio_job(source, settings, folder / "work", voice=voice, overwrite=overwrite)


def covers(folder: Path) -> list[str]:
    return sorted(p.name for p in (folder / "work").iterdir() if "cover" in p.name)


def has_cover(path: Path) -> bool:
    return any("attached pic" in line for line in streams(path))


def test_an_epub_cover_goes_into_every_file(tmp_path: Path) -> None:
    image = cover_jpeg()
    job = run(small_epub(tmp_path, image), tmp_path)
    assert covers(tmp_path) == ["cover.jpg"]
    assert (tmp_path / "work" / "cover.jpg").read_bytes() == image
    assert job.written.m4b is not None
    assert has_cover(job.written.m4b)
    assert job.written.mp3s
    assert all(has_cover(mp3) for mp3 in job.written.mp3s)


def test_a_pdf_cover_is_its_first_page_as_png(tmp_path: Path) -> None:
    job = run(small_pdf(tmp_path), tmp_path)
    assert covers(tmp_path) == ["cover.png"]
    assert (tmp_path / "work" / "cover.png").read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    assert job.written.m4b is not None
    assert has_cover(job.written.m4b)


def test_an_epub_without_a_cover_gives_files_without_one(tmp_path: Path) -> None:
    job = run(small_epub(tmp_path), tmp_path)
    assert covers(tmp_path) == []
    assert job.written.m4b is not None
    assert not has_cover(job.written.m4b)


def test_a_cover_left_by_an_earlier_run_is_never_used(tmp_path: Path) -> None:
    run(small_pdf(tmp_path), tmp_path)
    assert covers(tmp_path) == ["cover.png"]
    run(small_epub(tmp_path, cover_jpeg()), tmp_path)
    assert covers(tmp_path) == ["cover.jpg"]
    job = run(small_epub(tmp_path), tmp_path, overwrite=True)
    assert covers(tmp_path) == []
    assert job.written.m4b is not None
    assert not has_cover(job.written.m4b)


DAMAGED = [
    pytest.param(b"\xff\xd8\xff" + b"junk" * 100, id="jpeg-signature-then-junk"),
    pytest.param(b"\x89PNG\r\n\x1a\n" + b"junk" * 100, id="png-signature-then-junk"),
    pytest.param(None, id="jpeg-cut-to-2000-bytes"),
]


@pytest.mark.parametrize("image", DAMAGED)
def test_a_damaged_cover_is_dropped_before_any_speech(tmp_path: Path, image: bytes | None) -> None:
    """A good signature over damaged data passes `Cover`; ffmpeg would refuse it at the
    first MP3, after all the speech. It is checked first and left out (D-313)."""
    data = cover_jpeg()[:2000] if image is None else image
    seen: list[list[str]] = []

    def watch(text: str) -> bool:  # called before each chunk is spoken
        seen.append(covers(tmp_path))
        return False

    settings = JobSettings(output_folder=tmp_path / "out")
    job = run_audio_job(
        small_epub(tmp_path, data), settings, tmp_path / "work", voice=FakeVoice(watch).source()
    )
    assert seen
    assert seen[0] == []  # gone before the first chunk was spoken
    assert covers(tmp_path) == []
    assert job.written.m4b is not None
    assert not has_cover(job.written.m4b)
    assert all(not has_cover(mp3) for mp3 in job.written.mp3s)


def test_a_cover_ffmpeg_can_decode_is_kept(tmp_path: Path) -> None:
    (tmp_path / "cover.jpg").write_bytes(cover_jpeg())
    assert (
        audio_module.usable_cover(tmp_path / "cover.jpg", find_ffmpeg()) == tmp_path / "cover.jpg"
    )
    assert audio_module.usable_cover(None, find_ffmpeg()) is None
    assert audio_module.usable_cover(tmp_path / "cover.jpg", tmp_path / "no-ffmpeg") is None
    assert not (tmp_path / "cover.jpg").exists()


def test_a_cover_function_that_fails_gives_no_cover(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(path: Path) -> Cover | None:
        raise RuntimeError("a bug in the cover code")

    monkeypatch.setitem(audio_module.COVERS, ".epub", broken)  # type: ignore[index]
    job = run(small_epub(tmp_path, cover_jpeg()), tmp_path)
    assert covers(tmp_path) == []
    assert job.written.m4b is not None
    assert not has_cover(job.written.m4b)


def test_a_full_disk_while_writing_the_cover_gives_no_cover_and_no_half_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = files_module._write_partial

    def full(partial: Path, content: str | bytes) -> None:
        if "cover" in partial.name:
            assert isinstance(content, bytes)
            real(partial, content[: len(content) // 2])
            raise OSError(errno.ENOSPC, "No space left on device")
        real(partial, content)

    monkeypatch.setattr(files_module, "_write_partial", full)
    job = run(small_epub(tmp_path, cover_jpeg()), tmp_path)
    assert covers(tmp_path) == []  # neither the cover nor its partial file
    assert job.written.m4b is not None
    assert not has_cover(job.written.m4b)
    assert job.record.is_file()


def test_a_file_type_without_covers_gives_none(tmp_path: Path) -> None:
    (tmp_path / "work").mkdir()
    (tmp_path / "work" / "cover.png").write_bytes(b"old")
    assert audio_module.write_cover(tmp_path / "notes.md", tmp_path / "work") is None
    assert covers(tmp_path) == []


def test_bytes_are_written_whole_and_an_existing_file_only_when_asked(tmp_path: Path) -> None:
    target = tmp_path / "data.bin"
    files_module.write_bytes_atomically(target, b"\x00\xff\r\n", overwrite=False)
    assert target.read_bytes() == b"\x00\xff\r\n"  # as given: no line-end translation
    with pytest.raises(FileExistsError):
        files_module.write_bytes_atomically(target, b"new", overwrite=False)
    files_module.write_bytes_atomically(target, b"new", overwrite=True)
    assert target.read_bytes() == b"new"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["data.bin"]
