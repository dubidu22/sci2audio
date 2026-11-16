"""Sentence boundaries of the listening script against hand-checked sentences (D-715, D-719).

The sentence files and the list of known errors are in `tests/sentences/` (README.md there);
the metric is `sentence_metric.py`. The gate: every error the script makes on a set is listed
in `known-errors.toml`, and every listed error still happens, so a fix shrinks the list. The
natural sets (corpus files) also keep their precision and recall above the floors.
"""

from __future__ import annotations

import tomllib
from collections import Counter
from functools import cache
from pathlib import Path

import pytest
from sentence_metric import (
    Score,
    Truth,
    Words,
    compare,
    key,
    read_truth,
    score_file,
    script_of,
    stress_source,
    system_words,
)

pytestmark = pytest.mark.timeout(180)

TESTS = Path(__file__).resolve().parents[1]
SENTENCES = TESTS / "sentences"
CORPUS = TESTS / "corpus"
# the natural sets: a sentence file per corpus file
NATURAL = {
    "acl2023-hardt-ellipsis": "papers/acl2023-hardt-ellipsis.pdf",
    "acl2023-chi-plue": "papers/acl2023-chi-plue.pdf",
    "arxiv2017-maass-privacyscore": "papers/arxiv2017-maass-privacyscore.pdf",
    "sci2audio-sample-plain": "text/sci2audio-sample-plain.txt",
    "sci2audio-sample-note": "markdown/sci2audio-sample-note.md",
    "sci2audio-beispiel-text": "text/sci2audio-beispiel-text.txt",
    "sci2audio-beispiel-notiz": "markdown/sci2audio-beispiel-notiz.md",
}
STRESS = ("stress-en", "stress-de")  # written for sci2audio, read from a text file made of them
MIN_COVERAGE = 0.9  # below this share of compared gaps the truth no longer fits the file
KNOWN = tomllib.loads((SENTENCES / "known-errors.toml").read_text(encoding="utf-8"))
CLASSES = {
    "layout-split", "layout-join", "abbreviation", "ordinal", "initial", "label", "citation",
    "quote", "lowercase-start", "heading-number", "other",
}  # fmt: skip


@cache
def scored(name: str, tmp: Path | None = None) -> tuple[str, Score]:
    """A set's language (two letters) and score; a stress set is read from a text file."""
    truth = SENTENCES / f"{name}.txt"
    if name in NATURAL:
        language, score = score_file(truth, CORPUS / NATURAL[name])
    else:
        assert tmp is not None
        source = tmp / f"{name}.txt"
        source.write_text(stress_source(truth), encoding="utf-8")
        language, score = score_file(truth, source)
    return language.split("-", 1)[0], score


@pytest.fixture(scope="module")
def stress_folder(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return tmp_path_factory.mktemp("stress")


def _score(name: str, folder: Path) -> tuple[str, Score]:
    return scored(name, None if name in NATURAL else folder)


# --- the gate ---


def test_every_sentence_file_is_a_set() -> None:
    files = {path.stem for path in SENTENCES.glob("*.txt")}
    assert files == set(NATURAL) | set(STRESS)


def test_known_errors_are_well_formed() -> None:
    sets = set(NATURAL) | set(STRESS)
    for entry in KNOWN["error"]:
        assert set(entry) == {"file", "kind", "at", "class", "issue", "why"}, entry
        assert entry["file"] in sets, entry
        assert entry["kind"] in {"FP", "FN"}, entry
        assert entry["class"] in CLASSES, entry
        assert isinstance(entry["issue"], int), entry
        assert entry["issue"] > 0, entry
        assert " | " in entry["at"], entry
    assert set(KNOWN["floors"]) == {"en", "de"}


@pytest.mark.parametrize("name", [*NATURAL, *STRESS])
def test_the_errors_are_the_known_ones(name: str, stress_folder: Path) -> None:
    """Every error is listed in known-errors.toml, and every listed one still happens."""
    _, score = _score(name, stress_folder)
    found = Counter((error.kind, error.at) for error in score.errors)
    listed = Counter((e["kind"], e["at"]) for e in KNOWN["error"] if e["file"] == name)
    new = sorted((found - listed).elements())
    gone = sorted((listed - found).elements())
    assert not new, f"{name}: errors not in known-errors.toml (fix or list them): {new}"
    assert not gone, f"{name}: listed errors that no longer happen (remove them): {gone}"


@pytest.mark.parametrize("name", [*NATURAL, *STRESS])
def test_the_truth_still_fits_the_file(name: str, stress_folder: Path) -> None:
    """Most of the truth's gaps can be compared: if not, the file or its reading changed and
    the truth needs a look (or the alignment lost its way)."""
    _, score = _score(name, stress_folder)
    assert score.coverage >= MIN_COVERAGE, f"{name}: coverage {score.coverage:.3f}"


@pytest.mark.parametrize("language", ["en", "de"])
def test_natural_sets_stay_above_the_floors(language: str, stress_folder: Path) -> None:
    total = Score()
    for name in NATURAL:
        set_language, score = _score(name, stress_folder)
        if set_language == language:
            total.add(score)
    floor = KNOWN["floors"][language]
    print(
        f"{language}: precision {total.precision:.4f}, recall {total.recall:.4f} "
        f"({total.hits} found, {total.false_positives} extra, {total.false_negatives} missed)"
    )
    assert total.hits > 0
    assert total.precision >= floor["precision"]
    assert total.recall >= floor["recall"]


# --- the metric itself ---


def _truth(tmp_path: Path, text: str) -> Truth:
    path = tmp_path / "t.txt"
    path.write_text(text, encoding="utf-8")
    return read_truth(path)


def _words(text: str, starts: set[int], blocks: tuple[int, ...] = ()) -> Words:
    keys = [key(word) for word in text.split()]
    first = [i == 0 or i in blocks for i in range(len(keys))]
    return Words(keys, [(0, i) for i in range(len(keys))], first, starts)


def test_key_ignores_case_punctuation_and_ligatures() -> None:
    assert key("“Eﬃcient,”") == key("efficient") == "efficient"
    assert key("end.¹") == "end1"
    assert key("\u2013") == ""


def test_truth_lines_starts_optional_starts_and_gaps(tmp_path: Path) -> None:
    truth = _truth(
        tmp_path,
        "# comment\n@page 1\nOne two three.\n~ four five.\nSix \u2013 seven.\n---\nEight nine.\n",
    )
    assert " ".join(truth.words) == "One two three. four five. Six seven. Eight nine."
    assert truth.starts == {0, 5, 7}
    assert truth.optional == {3}
    assert truth.segments == [(0, 7), (7, 9)]


def test_a_line_without_words_hands_its_start_on(tmp_path: Path) -> None:
    truth = _truth(tmp_path, "One two.\n\u2013\n~ three four.\n")
    assert truth.starts == {0, 2}  # the stronger kind wins
    assert truth.optional == set()


def test_a_tilde_needs_its_space(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="'~ '"):
        _truth(tmp_path, "One.\n~two.\n")


def test_compare_counts_hits_extra_and_missed_starts(tmp_path: Path) -> None:
    truth = _truth(tmp_path, "Aa bb cc.\nDd ee ff.\nGg hh ii.\n")
    # the script starts at "dd" and at "hh", not at "gg"
    words = _words("aa bb cc dd ee ff gg hh ii", {0, 3, 7})
    score = compare(truth, words)
    assert score.hits == 1
    assert [(e.kind, e.at) for e in score.errors] == [
        ("FN", "cc. Dd ee ff. | Gg hh ii."),
        ("FP", "Dd ee ff. Gg | hh ii."),
    ]
    assert score.precision == 0.5
    assert score.recall == 0.5


def test_optional_starts_count_neither_way(tmp_path: Path) -> None:
    truth = _truth(tmp_path, "Aa bb cc\n~ dd ee ff.\n~ gg hh ii.\n")
    score = compare(truth, _words("aa bb cc dd ee ff gg hh ii", {0, 3}))
    assert score.hits == 0
    assert not score.errors
    assert score.compared == 8


def test_an_extra_start_at_a_block_start_is_a_layout_error(tmp_path: Path) -> None:
    truth = _truth(tmp_path, "Aa bb cc dd ee ff.\n")
    score = compare(truth, _words("aa bb cc dd ee ff", {0, 3}, blocks=(3,)))
    assert [(e.kind, e.layout) for e in score.errors] == [("FP", True)]


def test_only_gaps_inside_a_long_enough_match_are_compared(tmp_path: Path) -> None:
    # "xx" is not in the script: the gaps next to it are not compared; nor are those of a
    # match shorter than MIN_RUN
    truth = _truth(tmp_path, "Aa bb cc.\nXx dd ee ff.\n---\nGg hh.\n")
    score = compare(truth, _words("aa bb cc dd ee ff gg hh", {0, 3, 6}))
    assert score.compared == 4  # aa|bb, bb|cc, dd|ee, ee|ff
    assert not score.errors


def test_segments_are_aligned_in_any_order(tmp_path: Path) -> None:
    truth = _truth(tmp_path, "Gg hh ii jj.\n---\nAa bb cc.\nDd ee ff.\n")
    score = compare(truth, _words("aa bb cc dd ee ff gg hh ii jj", {0, 3, 6}))
    assert score.hits == 1
    assert not score.errors


def test_the_script_side_joins_line_end_hyphens_and_maps_starts(tmp_path: Path) -> None:
    source = tmp_path / "s.txt"
    source.write_text("The ellip-\nsis is here. It ends.\n\nA new para.\n", encoding="utf-8")
    document, utterances = script_of(source)
    words = system_words(document, utterances)
    assert words.keys == ["the", "ellipsis", "is", "here", "it", "ends", "a", "new", "para"]
    assert words.starts == {0, 4, 6}
    assert words.first_in_block == [True, False, False, False, False, False, True, False, False]


def test_stress_source_joins_a_paragraph_and_drops_the_marks(tmp_path: Path) -> None:
    path = tmp_path / "s.txt"
    path.write_text("# c\nOne.\n~ Two.\n\n\nThree.\n---\nFour.\n", encoding="utf-8")
    assert stress_source(path) == "One. Two.\n\nThree. Four.\n"
