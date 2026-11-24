# ruff: noqa: RUF001
# (minus signs, dashes and the times sign are what these texts are made of)
"""Readings a second run over the first run's script keeps (D-577): an arrow of logic beside
"Nx" (#843), an arrow or a sign where another step reads what stands before it (#924), and
an ISO date after a dash range (#957). Each is pinned on the printed text and on its first
run's script, in English and German."""

import pytest

from sci2audio.core import BlockKind
from sci2audio.testing import make_document
from sci2audio.textprep import StepContext, run_steps, spoken_text


def _both_runs(text: str, language: str) -> tuple[str, str]:
    context = StepContext(language)
    document = make_document([(BlockKind.PARAGRAPH, text)], language)
    first = spoken_text(run_steps(document, context, strict=True).script())
    again = make_document([(BlockKind.PARAGRAPH, first)], language)
    return first, spoken_text(run_steps(again, context, strict=True).script())


@pytest.mark.parametrize(
    ("printed", "language", "said"),
    [
        # #843: an arrow, printed whole, in pieces or in ASCII, is no operator around "Nx"
        ("So 3x=>A.", "en", "So 3 times implies A."),
        ("So 3x ⇒ A.", "en", "So 3 times implies A."),
        ("So 3x =⇒ A.", "en", "So 3 times implies A."),
        ("So 3x <=> A.", "en", "So 3 times if and only if A."),
        ("So A => 3x.", "en", "So A implies 3 times."),
        ("So A ⇐= 3x.", "en", "So A is implied by 3 times."),
        ("Also 3x=>A.", "de", "Also 3 mal daraus folgt A."),
        ("Also 3x ⇒ A.", "de", "Also 3 mal daraus folgt A."),
        ("Also A <=> 3x.", "de", "Also A genau dann, wenn 3 mal."),
        # ... while an "=" that is no arrow keeps "Nx" a variable, as before
        ("So 3x = A and y = 2x + 1.", "en", "So 3x equals A and y equals 2x + 1."),
        ("So 3x>=A.", "en", "So 3x>=A."),
        ("So 3x ==> A.", "en", "So 3x ==> A."),  # no arrow of logic: left as printed
        # ... nor after "<", ">" or "=", where the statistics step reads none either
        ("A ==> 3x and B", "en", "A ==> 3x and B"),
        ("A >=> 3x and B", "en", "A >=> 3x and B"),
        ("A ==> 3x und B", "de", "A ==> 3x und B"),
        ("A >=> 3x und B", "de", "A >=> 3x und B"),
        ("It runs 3x faster and 3 × 4 is 12.", "en", "It runs 3 times faster and 3 times 4 is 12."),
        ("Es läuft 3x schneller.", "de", "Es läuft 3 mal schneller."),
        # #924: an arrow after an abbreviation read with its full stop
        ("Jh.⇒1", "de", "Jahrhundert daraus folgt 1"),
        ("usw. => 1", "de", "und so weiter daraus folgt 1"),
        ("Jh. ⇒ Das gilt.", "de", "Jahrhundert ⇒ Das gilt."),  # named between two words
        # ... also where the abbreviation ends in one letter: it is one prose word
        ("z. B. ⇒ Die Daten", "de", "zum Beispiel ⇒ Die Daten"),
        ("d. h. ⇒ wir messen", "de", "das heißt ⇒ wir messen"),
        ("i. V. m. ⇒ dem Gesetz", "de", "in Verbindung mit ⇒ dem Gesetz"),
        ("z. B. ⇒ 2", "de", "zum Beispiel daraus folgt 2"),
        ("Ende. ⇒ 3 Teilnehmer", "de", "Ende. ⇒ 3 Teilnehmer"),  # no abbreviation: as before
        # ... and a sign after a left arrow in pieces, read as after "←"
        ("←−=1", "de", "← gleich 1"),
        ("←−− < 31", "de", "← kleiner als 31"),
        ("←−<1", "en", "← less than 1"),
        ("Kapitel I", "de", "Kapitel 1"),
        # #957: an ISO date after an en dash, as after an em dash
        ("3–3–1999-02-01", "en", "3 to 3 to 1 February 1999"),
        ("3—3—1999-02-01", "en", "3 to 3 to 1 February 1999"),
        ("3-3-1999-02-01", "en", "3-3-1999-02-01"),
        ("from 2019-03-01–2019-03-05", "en", "from 1 March 2019 to 5 March 2019"),
        ("3–3–1999-02-01", "de", "3 bis 3 bis ersten Februar 19 hundert 99"),
        ("3-3-1999-02-01", "de", "3-3-1999-02-01"),
    ],
)
def test_the_reading_is_the_same_on_both_runs(printed: str, language: str, said: str) -> None:
    assert _both_runs(printed, language) == (said, said)
