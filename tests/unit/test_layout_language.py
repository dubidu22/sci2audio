"""The document's language: the job's setting, the file's own, or a guess from the text
(#219, D-494 to D-498).

The guess counts common German and English function words over the whole text; the corpus
files are guessed right with their tags removed, short or mixed texts fall back to English
with a warning, and the person's setting always wins.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from textwrap import wrap

import pytest
from core_strategies import contents
from hypothesis import given
from pdf_maker import Text, make_pdf
from syrupy.assertion import SnapshotAssertion

from sci2audio.app import JobSettings, kokoro_voice, language_warning, run_script_job
from sci2audio.app.job import EXTRACTORS
from sci2audio.core import Content, LanguageSource, Metadata
from sci2audio.extraction import read_text
from sci2audio.layout import COMMON_WORDS, LayoutSettings, build_document, guess_language
from sci2audio.layout.language import choose_language
from sci2audio.voices import DEFAULT_VOICES

pytestmark = pytest.mark.timeout(120)

CORPUS = Path(__file__).resolve().parents[1] / "corpus"
ENGLISH_CORPUS = sorted(
    path
    for folder in ("papers", "epub", "markdown", "text")
    for path in (CORPUS / folder).iterdir()
    if path.suffix in EXTRACTORS and "beispiel" not in path.name
)
GERMAN_CORPUS = [
    CORPUS / "markdown" / "sci2audio-beispiel-notiz.md",
    CORPUS / "text" / "sci2audio-beispiel-text.txt",
]

# Own sentences, about 70 words each.
GERMAN = (
    "Die Studie untersucht, wie schnell Menschen einem gesprochenen Artikel folgen können. "
    "Dabei wurden die Teilnehmenden in zwei Gruppen eingeteilt, und jede Gruppe hörte den "
    "Text mit einer anderen Geschwindigkeit. Die Ergebnisse zeigen, dass die meisten "
    "Hörenden auch bei schnellerem Sprechen noch folgen, wenn die Sätze kurz sind und "
    "die Zahlen nicht zu dicht stehen. Für die nächste Studie wollen wir mehr Texte prüfen."
)
ENGLISH = (
    "The study looks at how quickly people can follow a paper that is read aloud. The "
    "listeners were split into two groups, and each group heard the text at a different "
    "speed. The results show that most of them can still follow at the faster speed when "
    "the sentences are short and the numbers are not too dense. For the next study we "
    "would like to test more texts, both with and without footnotes."
)


def content_of(text: str, language: str = "") -> Content:
    content = read_text(text.encode("utf-8"), "note.txt")
    return dataclasses.replace(content, metadata=Metadata(language=language))


def untagged(path: Path) -> Content:
    content = EXTRACTORS[path.suffix](path)
    return dataclasses.replace(content, metadata=dataclasses.replace(content.metadata, language=""))


# ---- the guess --------------------------------------------------------------------------


def test_the_word_lists_never_count_a_word_for_both_languages() -> None:
    assert not COMMON_WORDS["de"] & COMMON_WORDS["en"]
    # common in both languages, so in neither list
    assert not {"in", "an", "so", "was", "will", "also", "man", "am", "as"} & (
        COMMON_WORDS["de"] | COMMON_WORDS["en"]
    )


def test_german_and_english_prose_are_told_apart() -> None:
    assert guess_language(content_of(GERMAN)).language == "de"
    assert guess_language(content_of(ENGLISH)).language == "en"


def test_the_guess_counts_every_word_and_the_common_ones() -> None:
    guess = guess_language(content_of("Der Hund und die Katze. The dog and the cat. 42 x2"))
    # words are runs of letters ("x2" gives "x"); "Der", "und", "die" / "The", "and", "the"
    assert (guess.words, guess.german, guess.english) == (11, 3, 3)
    assert guess.language == ""  # six common words are too few, and they are even


def test_too_little_text_does_not_tell() -> None:
    short = "Die Katze schläft auf dem Sofa, und der Hund wartet vor der Tür."
    guess = guess_language(content_of(short))
    assert guess.german > 3 * guess.english
    assert guess.german + guess.english < LayoutSettings().language_words
    assert guess.language == ""


def test_a_mixed_text_does_not_tell() -> None:
    assert guess_language(content_of(f"{GERMAN}\n\n{ENGLISH}")).language == ""


def test_the_thresholds_come_from_the_settings() -> None:
    short = content_of("Die Katze schläft auf dem Sofa, und der Hund wartet vor der Tür.")
    assert guess_language(short, LayoutSettings(language_words=5)).language == "de"
    mixed = content_of(f"{GERMAN}\n\n{ENGLISH}")
    assert guess_language(mixed, LayoutSettings(language_ratio=0.5)).language in {"de", "en"}


@pytest.mark.parametrize("path", ENGLISH_CORPUS, ids=[p.name for p in ENGLISH_CORPUS])
def test_every_english_corpus_file_without_its_tag_is_guessed_english(path: Path) -> None:
    document = build_document(untagged(path))
    assert (document.language, document.language_source) == ("en", LanguageSource.TEXT)
    guess = document.language_guess
    assert guess is not None
    assert guess.german * 50 < guess.english


@pytest.mark.parametrize("path", GERMAN_CORPUS, ids=[p.name for p in GERMAN_CORPUS])
def test_the_german_samples_without_their_tag_are_guessed_german(path: Path) -> None:
    document = build_document(untagged(path))
    assert (document.language, document.language_source) == ("de", LanguageSource.TEXT)


@given(contents())
def test_the_guess_never_fails_and_fits_its_counts(content: Content) -> None:
    guess = guess_language(content)
    settings = LayoutSettings()
    assert guess.german + guess.english <= guess.words
    told = guess.german + guess.english >= settings.language_words
    if guess.language == "de":
        assert told
        assert guess.german >= settings.language_ratio * guess.english
    elif guess.language == "en":
        assert told
        assert guess.english >= settings.language_ratio * guess.german
    assert guess_language(content) == guess  # deterministic


@given(contents())
def test_layout_always_records_where_the_language_came_from(content: Content) -> None:
    document = build_document(content)
    assert document.language_source is not None
    assert document.language_guess is not None  # no setting: the text was looked at
    assert build_document(content, LayoutSettings(language="fr")).language_source == "setting"


# ---- who wins (D-496) -------------------------------------------------------------------


def test_the_setting_wins_and_the_text_is_not_looked_at() -> None:
    chosen = choose_language(content_of(GERMAN, "de"), LayoutSettings(language="en-GB"))
    assert chosen == ("en-GB", LanguageSource.SETTING, None)


def test_the_file_wins_when_its_text_agrees_or_does_not_tell() -> None:
    for text, stated in ((GERMAN, "de-AT"), (ENGLISH, "en-GB"), ("Kurz.", "de"), ("Short.", "en")):
        language, source, guess = choose_language(content_of(text, stated), LayoutSettings())
        assert (language, source) == (stated, LanguageSource.FILE)
        assert guess is not None


def test_a_clear_text_overrules_a_file_that_states_the_other_language() -> None:
    """One of four tagged German arXiv PDFs measured says "en" (#219)."""
    language, source, _ = choose_language(content_of(GERMAN, "en-US"), LayoutSettings())
    assert (language, source) == ("de", LanguageSource.TEXT)
    language, source, _ = choose_language(content_of(ENGLISH, "de-DE"), LayoutSettings())
    assert (language, source) == ("en", LanguageSource.TEXT)


def test_a_language_the_text_cannot_tell_is_never_overruled() -> None:
    language, source, _ = choose_language(content_of(GERMAN, "fr"), LayoutSettings())
    assert (language, source) == ("fr", LanguageSource.FILE)


def test_nothing_stated_and_nothing_told_is_english() -> None:
    language, source, guess = choose_language(content_of("Kurz."), LayoutSettings())
    assert (language, source) == ("en", LanguageSource.FALLBACK)
    assert guess is not None
    assert guess.language == ""


# ---- the job: report, warnings, voice ---------------------------------------------------


def german_pdf() -> bytes:
    """A page of German prose without a language tag, wrapped at about 80 characters."""
    lines = [Text("Einleitung", 72, 80, size=14)]
    lines += [Text(line, 72, 110 + 14 * k, size=10) for k, line in enumerate(wrap(GERMAN, 80))]
    return make_pdf(lines)


def test_an_untagged_german_pdf_is_read_in_german(tmp_path: Path) -> None:
    source = tmp_path / "studie.pdf"
    source.write_bytes(german_pdf())
    job = run_script_job(source, JobSettings(), tmp_path / "work")
    document = job.result.document
    assert document.content.metadata.language == ""
    assert (document.language, document.language_source) == ("de", LanguageSource.TEXT)
    assert job.report.warnings == ()
    # the German rules run as for a job set to German (D-474), the German voice reads (D-469)
    chosen = run_script_job(
        source, JobSettings(language="de", output_folder=tmp_path / "set"), tmp_path / "w2"
    )
    assert job.result.run.not_run == chosen.result.run.not_run
    assert job.files.script.read_text(encoding="utf-8") == chosen.files.script.read_text(
        encoding="utf-8"
    )
    assert kokoro_voice(tmp_path).voice_for("", document.language) == DEFAULT_VOICES["de"]
    data = json.loads(job.files.report_json.read_text(encoding="utf-8"))
    assert data["language"] == "de"
    assert data["language_source"] == "text"
    assert data["language_guess"]["language"] == "de"
    markdown = job.files.report_markdown.read_text(encoding="utf-8")
    assert "Language: de, guessed from the text (" in markdown


def test_the_report_says_where_the_language_came_from(tmp_path: Path) -> None:
    source = tmp_path / "note.md"
    source.write_text(f"---\nlang: en-GB\n---\n\n{ENGLISH}\n", encoding="utf-8")
    stated = run_script_job(source, JobSettings(), tmp_path / "a", overwrite=True)
    assert "Language: en-GB, as the file states." in (
        stated.files.report_markdown.read_text(encoding="utf-8")
    )
    chosen = run_script_job(source, JobSettings(language="de"), tmp_path / "b", overwrite=True)
    report = chosen.files.report_markdown.read_text(encoding="utf-8")
    assert "Language: de, chosen in the settings." in report
    assert (
        json.loads(chosen.files.report_json.read_text(encoding="utf-8"))["language_guess"] is None
    )


def test_a_text_that_does_not_tell_is_english_with_a_warning(tmp_path: Path) -> None:
    source = tmp_path / "kurz.txt"
    source.write_text("Ein kurzer Satz.\n", encoding="utf-8")
    job = run_script_job(source, JobSettings(), tmp_path / "work")
    assert job.result.document.language == "en"
    (warning,) = job.report.warnings
    assert warning.startswith("sci2audio could not tell from the text whether it is English")
    assert "--language de" in warning
    markdown = job.files.report_markdown.read_text(encoding="utf-8")
    assert "the text does not show whether it is English or German" in markdown
    assert warning in markdown


def test_a_file_tag_overruled_by_its_text_is_a_warning() -> None:
    document = build_document(content_of(GERMAN, "en"))
    assert language_warning(document) == (
        "The file says its language is en, but its text is German, so it is read in German. "
        "To read it as en, set the language to en."
    )
    assert language_warning(build_document(content_of(GERMAN))) is None  # a clear guess
    assert language_warning(build_document(content_of(GERMAN, "de"))) is None


@pytest.mark.parametrize("path", GERMAN_CORPUS, ids=[p.stem for p in GERMAN_CORPUS])
def test_the_german_samples_scripts_are_as_recorded(
    path: Path, tmp_path: Path, snapshot: SnapshotAssertion
) -> None:
    """The German samples' listening scripts under today's German rules (golden files)."""
    job = run_script_job(path, JobSettings(output_folder=tmp_path), tmp_path / "work")
    assert job.files.script.read_text(encoding="utf-8") == snapshot
