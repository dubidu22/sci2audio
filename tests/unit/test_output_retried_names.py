"""A name the file system refuses is retried, never over a person's file (#493, CRIT-02).

APFS refuses a name holding a code point its own Unicode table does not know yet (EILSEQ),
and a Mac's table can be older than Python's, which `names.clean` follows. CI's Mac is
current, so the refusal is made by a fake `os.open` (`output_helpers.refuse_newer_names`).
"""

from __future__ import annotations

import errno
import os
import unicodedata
from dataclasses import replace
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st
from output_helpers import NEWER, make_job, refuse_newer_names

from sci2audio.output import OutputSettings, audiobook_targets, names, write_audiobook


def no_newer(folder: Path) -> list[str]:
    """Every name in `folder`, checked to hold no newer character."""
    found = sorted(path.name for path in folder.iterdir())
    assert not [name for name in found if NEWER in name], found
    return found


# ---- the names -----------------------------------------------------------------------------


def test_older_keeps_what_unicode_3_2_had_and_spaces_the_rest() -> None:
    alpha = "\N{GREEK SMALL LETTER ALPHA}"
    assert names.older(f"Café {NEWER} € {alpha}") == f"Café   € {alpha}"
    assert names.retried(f"{NEWER} Wobble", "audiobook") == "Wobble"
    assert names.retried(NEWER, "audiobook") == "audiobook"


@given(st.text())
def test_a_retried_name_holds_only_old_characters_and_is_clean(title: str) -> None:
    name = names.retried(title, "audiobook")
    assert names.clean(name, "audiobook") == name
    assert all(unicodedata.ucd_3_2_0.category(c) != "Cn" for c in name)
    assert names.older(name) == name  # so it is never tried again


def test_an_ordinary_name_is_never_tried(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    asked = refuse_newer_names(monkeypatch)
    assert not names.refused(tmp_path, "A Study of Tones.readalong.json")
    assert not names.refused(tmp_path, "Café über \N{GREEK SMALL LETTER ALPHA}.mp3")
    assert asked == []
    assert list(tmp_path.iterdir()) == []


def test_a_newer_name_is_tried_and_leaves_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert not names.refused(tmp_path, f"{NEWER} ok.mp3")  # this file system accepts it
    assert list(tmp_path.iterdir()) == []
    asked = refuse_newer_names(monkeypatch)
    assert names.refused(tmp_path, f"{NEWER} no.mp3")
    assert asked == [f".{NEWER} no.mp3.partial"]
    assert list(tmp_path.iterdir()) == []


def test_the_probe_never_touches_a_file_that_is_there(tmp_path: Path) -> None:
    there = tmp_path / f".{NEWER} x.mp3.partial"
    there.write_bytes(b"someone's")
    assert not names.refused(tmp_path, f"{NEWER} x.mp3")
    assert there.read_bytes() == b"someone's"


def test_other_errors_are_no_refusal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A missing folder or a denied one: writing fails later as it always did."""
    assert not names.refused(tmp_path / "missing", f"{NEWER}.mp3")

    def denied(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise OSError(errno.EACCES, "denied")

    monkeypatch.setattr(os, "open", denied)
    assert not names.refused(tmp_path, f"{NEWER}.mp3")


# ---- the audiobook -------------------------------------------------------------------------

SETTINGS = OutputSettings(subtitles=True)


def test_the_targets_retry_the_book_and_each_chapter_the_folder_refuses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    refuse_newer_names(monkeypatch)
    titles = [f"{NEWER} Intro", "Methods", f"Results {NEWER}"]
    named = audiobook_targets(tmp_path, f"Tones {NEWER}", titles, SETTINGS)
    assert [p.name for p in named.mp3s] == [
        "Tones - 01 Intro.mp3",
        "Tones - 02 Methods.mp3",
        "Tones - 03 Results.mp3",
    ]
    assert named.m4b == tmp_path / "Tones.m4b"
    assert named.readalong == tmp_path / "Tones.readalong.json"
    assert [p.name for p in named.subtitles][-2:] == ["Tones.srt", "Tones.vtt"]
    assert list(tmp_path.iterdir()) == []  # the probes are gone


def test_the_targets_keep_a_name_the_folder_accepts(tmp_path: Path) -> None:
    named = audiobook_targets(tmp_path, f"Tones {NEWER}", [f"{NEWER} Intro"], SETTINGS)
    assert named.readalong.name == f"Tones {NEWER}.readalong.json"
    assert named.mp3s[0].name == f"Tones {NEWER} - 01 {NEWER} Intro.mp3"


def test_an_audiobook_whose_names_are_refused_is_written_under_the_retried_names(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    job = make_job(tmp_path / "job", titles=(f"{NEWER} Intro", "Methods", "Results"))
    book = replace(job.book, title=f"{NEWER} Tones")
    refuse_newer_names(monkeypatch)
    out = tmp_path / "out"
    written = write_audiobook(job.folder, out, job.chapters, job.spoken, book, SETTINGS)
    assert written.readalong.name == "Tones.readalong.json"
    assert written.mp3s[0].name == "Tones - 01 Intro.mp3"
    assert len(no_newer(out)) == 3 + 1 + 8 + 1  # MP3s, M4B, subtitles, read-along


def test_a_retried_name_never_replaces_a_file_that_is_there(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CRIT-02: the person's own "Tones.m4b" in the folder stays byte for byte, and nothing
    of this run is left beside it."""
    job = make_job(tmp_path / "job")
    book = replace(job.book, title=f"{NEWER} Tones")
    out = tmp_path / "out"
    out.mkdir()
    (out / "Tones.m4b").write_bytes(b"the person's own file")
    refuse_newer_names(monkeypatch)
    with pytest.raises(FileExistsError, match=r"Tones\.m4b"):
        write_audiobook(job.folder, out, job.chapters, job.spoken, book, SETTINGS)
    assert (out / "Tones.m4b").read_bytes() == b"the person's own file"
    assert no_newer(out) == ["Tones.m4b"]
