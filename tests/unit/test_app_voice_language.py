"""The voice a job speaks with follows the document's language (#211, D-468, D-469, D-471):
the chosen voice if it speaks that language, else the language's default voice; a missing
voice pack stops the job before any speech; each voice's chunks carry its own version."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from audio_fakes import FakeVoice
from test_app_audio_job import small_pdf

from sci2audio.app import JobError, JobSettings, VoiceSource, run_audio_job
from sci2audio.app.voice import primary_language

GERMAN = "dm_fake"


def bilingual(voice: FakeVoice, installed: frozenset[str] | None = None) -> VoiceSource:
    """The fake voice with a German voice added, shaped like the Kokoro source."""
    return VoiceSource(
        engine="fake",
        version=voice.version,
        make=voice.make,
        voices=("af_heart", "bm_george", GERMAN),
        default_voice="af_heart",
        release=voice.release,
        languages={"af_heart": "en-US", "bm_george": "en-GB", GERMAN: "de-DE"},
        defaults={"en": "af_heart", "de": GERMAN},
        versions={GERMAN: "fake-de-1"},
        installed=(lambda v: True) if installed is None else (lambda v: v in installed),
    )


def run(folder: Path, source: VoiceSource, **settings: object):  # type: ignore[no-untyped-def]
    pdf = small_pdf(folder, "Die Messung lief drei Jahre.", "Sie ist abgeschlossen.")
    job_settings = JobSettings(output_folder=folder / "out", **settings)  # type: ignore[arg-type]
    return run_audio_job(pdf, job_settings, folder / "work", voice=source, overwrite=True)


@pytest.mark.parametrize(
    ("chosen", "language", "spoken"),
    [
        ("", "en", "af_heart"),
        ("", "en-GB", "af_heart"),
        ("bm_george", "en", "bm_george"),
        (GERMAN, "en", "af_heart"),  # a German voice does not read English
        ("", "de", GERMAN),
        ("", "de-AT", GERMAN),
        ("bm_george", "de", GERMAN),  # nor an English voice German
        (GERMAN, "de-DE", GERMAN),
        ("", "fr", "af_heart"),  # no French voice: as before #211
        ("bm_george", "fr", "bm_george"),
        (GERMAN, "fr", GERMAN),
    ],
)
def test_the_voice_follows_the_language(chosen: str, language: str, spoken: str) -> None:
    assert bilingual(FakeVoice()).voice_for(chosen, language) == spoken


def test_primary_language() -> None:
    assert [primary_language(t) for t in ("de-DE", "EN", " de ", "")] == ["de", "en", "de", ""]


def test_a_source_naming_unknown_voices_is_refused() -> None:
    with pytest.raises(ValueError, match=r"\['dm_nobody'\]"):
        replace(bilingual(FakeVoice()), defaults={"de": "dm_nobody"})


def test_a_german_document_is_read_by_the_german_voice(tmp_path: Path) -> None:
    voice = FakeVoice()
    run(tmp_path, bilingual(voice), language="de", voice="af_heart")
    assert {v for _, v, _ in voice.spoken} == {GERMAN}
    english = FakeVoice()
    run(tmp_path, bilingual(english), language="en")
    assert {v for _, v, _ in english.spoken} == {"af_heart"}


def test_a_missing_german_pack_stops_the_job_before_any_speech(tmp_path: Path) -> None:
    voice = FakeVoice()
    source = bilingual(voice, installed=frozenset({"af_heart", "bm_george"}))
    with pytest.raises(JobError, match=r"the voice is not set up: .*dm_fake.*language de"):
        run(tmp_path, source, language="de")
    assert voice.made == 0
    assert not (tmp_path / "out").exists()
    run(tmp_path, source, language="en")  # English still works without it
    assert voice.spoken


def test_each_voice_keys_its_chunks_with_its_own_version(tmp_path: Path) -> None:
    first = FakeVoice()
    run(tmp_path, bilingual(first), language="de")
    assert len(first.spoken) == 2
    english_changed = FakeVoice(version="fake-2")  # only the English voices' version moves
    job = run(tmp_path, bilingual(english_changed), language="de")
    assert english_changed.spoken == []
    assert job.reused == 2
    german_changed = FakeVoice()
    source = replace(bilingual(german_changed), versions={GERMAN: "fake-de-2"})
    run(tmp_path, source, language="de")
    assert len(german_changed.spoken) == 2
