# ruff: noqa: RUF001
# (minus signs, dashes and the times sign are what these texts are made of)
"""Readings a second run over the first run's script keeps (D-577): an arrow of logic beside
"Nx" (#843, #984), an arrow or a sign where another step reads what stands before it (#924,
#972), an ISO date after a dash range (#957), a part's Roman numeral before a full stop
(#976) and a list of them (#996), and "<", ">" or a minus sign before "Nx" (#988, #997) and
after it (#1010). Each is pinned on the printed text and on its first run's script, in English
and German."""

import pytest

from sci2audio.core import BlockKind
from sci2audio.testing import make_document
from sci2audio.textprep import StepContext, run_steps, spoken_text
from sci2audio.textprep.notation import in_ascii_run


def _both_runs(text: str, language: str, kind: BlockKind = BlockKind.PARAGRAPH) -> tuple[str, str]:
    context = StepContext(language)
    document = make_document([(kind, text)], language)
    first = spoken_text(run_steps(document, context, strict=True).script())
    again = make_document([(kind, first)], language)
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
        # #972: a sign or an arrow after an English abbreviation read with its full stop
        ("e.g.=1", "en", "for example equals 1"),
        ("approx.⇒1", "en", "approximately implies 1"),
        ("i.e.=2", "en", "that is equals 2"),
        ("cf.⇒A", "en", "compare implies A"),
        (
            "See e.g. = 1 and i.e. ⇒ 2 here.",
            "en",
            "See for example equals 1 and that is implies 2 here.",
        ),
        ("e.g. ⇒ the data", "en", "for example ⇒ the data"),  # named between two words
        ("End. = 1", "en", "End. = 1"),  # no abbreviation: as before
        # #984: the "=" after "⇐" or "⇐=" is a piece of that arrow, so "=>" there is no arrow
        # and ">" is a sign to both steps; before "<" it ends the pieced arrow ("⇐=<=>")
        ("A ⇐==> 3x", "de", "A folgt aus größer als 3x"),
        ("A ⇐=> 3x", "de", "A folgt aus größer als 3x"),
        ("A ⇐= > 3x", "de", "A folgt aus größer als 3x"),
        ("A ⇐=<=> 3x", "de", "A folgt aus genau dann, wenn 3 mal"),
        ("A ⇐==> 3x und B", "de", "A folgt aus größer als 3x und B"),
        # ... in English a bare "greater than" after the arrow's words is prose (D-605)
        ("A ⇐==> 3x", "en", "A is implied by greater than 3 times"),
        ("A ⇐= > 3x", "en", "A is implied by greater than 3 times"),
        ("A ⇒ > 3x", "en", "A implies greater than 3 times"),
        ("A ⇐=<=> 3x", "en", "A is implied by if and only if 3 times"),
        ("y > 3x", "en", "y greater than 3x"),  # no arrow before the sign: as before
        # #976: a part's Roman numeral before a full stop, in a paragraph
        ("Siehe Kapitel I.", "de", "Siehe Kapitel 1."),
        ("Kapitel I. Einleitung", "de", "Kapitel 1. Einleitung"),
        ("Kapitel IV.", "de", "Kapitel 4."),
        ("Das zeigt Teil II.", "de", "Das zeigt Teil 2."),
        ("Kap. I. Einleitung", "de", "Kapitel 1. Einleitung"),
        ("Teil II und III. Dann", "de", "Teil II und III. Dann"),  # a run: left whole
        # ... but not after another keyword or word, nor where "1." is an ordinal next time
        ("Ludwig XIV.", "de", "Ludwig XIV."),
        ("Typ I.", "de", "Typ I."),
        ("Phase II. Dann", "de", "Phase II. Dann"),
        ("Kapitel I. Teil", "de", "Kapitel I. Teil"),
        ("Kapitel I. Mai", "de", "Kapitel I. Mai"),
        ("Kapitel I.2", "de", "Kapitel I.2"),
        # #996: a list of such numerals, a full stop after each, is left whole too
        ("Kapitel I. und II.", "de", "Kapitel I. und II."),
        ("Teile I. und II. folgen.", "de", "Teile I. und II. folgen."),
        ("Kapitel I. bis III.", "de", "Kapitel I. bis III."),
        ("Kapitel I. oder II.", "de", "Kapitel I. oder II."),
        ("Kapitel I. & II.", "de", "Kapitel I. & II."),
        ("Kapitel I./II.", "de", "Kapitel I./II."),
        ("Kapitel I., II. und III.", "de", "Kapitel I., II. und III."),
        ("Kap. I. und II.", "de", "Kapitel I. und II."),
        # ... but not one numeral before a word or another part keyword
        ("Kapitel IV. Dann folgt mehr.", "de", "Kapitel 4. Dann folgt mehr."),
        ("Kapitel I. Im Text", "de", "Kapitel 1. Im Text"),
        ("Kapitel I. und Teil II.", "de", "Kapitel 1. und Teil 2."),
        # #988: a bare "<" or ">" before "Nx" is the sign only where its words are on a second
        # run, after a one-letter variable or a closing bracket (D-646); prose elsewhere
        ("A > 3x", "en", "A greater than 3 times"),
        ("A < 3x", "en", "A less than 3 times"),
        ("e.g. < 3x", "en", "for example less than 3 times"),
        ("e.g. > 3x", "en", "for example greater than 3 times"),
        ("A>3x", "en", "A greater than 3 times"),
        ("> 3x", "en", "greater than 3 times"),
        ("I < 3x", "en", "I less than 3 times"),
        ("2 s > 3x", "en", "2 seconds greater than 3 times"),
        ("x < 3x", "en", "x less than 3x"),
        ("(a) < 3x", "en", "(a) less than 3x"),
        ("f(x) > 3x", "en", "f(x) greater than 3x"),
        ("A > 3x + 1", "en", "A greater than 3x + 1"),  # an operator after it still counts
        ("A << 3x", "en", "A << 3x"),  # left as printed: a sign on both runs
        ("A -> 3x", "en", "A -> 3x"),
        ("A > 3x", "de", "A größer als 3x"),
        ("z. B. < 3x", "de", "zum Beispiel kleiner als 3x"),
        # #997: "minus", the reading of a minus sign, is that sign before "Nx"
        ("A − 3x", "en", "A minus 3x"),
        ("A = − 3x", "en", "A equals minus 3x"),
        ("A ⇒ − 3x", "en", "A implies minus 3x"),
        ("− 3x", "en", "minus 3x"),
        ("A = −3x", "en", "A equals minus 3x"),
        ("A ± 3x", "en", "A plus or minus 3 times"),  # "±" is no operator: as before
        ("A plus or minus 3x", "en", "A plus or minus 3 times"),
        ("It was minus 3x here.", "en", "It was minus 3x here."),  # printed: as its sign
        ("It was minus\n3x here.", "en", "It was minus 3x here."),
        # ... but "plus or minus" ("±") in any case and with any white space is no sign
        ("A plus or  minus 3x", "en", "A plus or minus 3 times"),
        ("A plus or\nminus 3x", "en", "A plus or minus 3 times"),
        ("A plus or minus 3x", "en", "A plus or minus 3 times"),
        ("A plus\tor minus 3x", "en", "A plus or minus 3 times"),
        ("Plus or minus 3x.", "en", "Plus or minus 3 times."),
        ("A PLUS OR minus 3x", "en", "A PLUS OR minus 3 times"),
        ("A plus/minus 3x", "en", "A plus/minus 3 times"),
        ("A plus / minus 3x", "en", "A plus / minus 3 times"),
        ("A plus-minus 3x", "en", "A plus-minus 3 times"),
        ("Minus 3x is the spread.", "en", "Minus 3 times is the spread."),  # no sign's reading
        ("A − 3x", "de", "A − 3x"),
        ("A = − 3x", "de", "A gleich − 3x"),
        ("A ⇒ − 3x", "de", "A daraus folgt − 3x"),
        ("− 3x", "de", "− 3x"),
        # #1021: "plus" joined to "minus" by a dash or a Unicode hyphen is "±", as with "-"
        ("A plus–minus 3x", "en", "A plus–minus 3 times"),
        ("A plus—minus 3x", "en", "A plus—minus 3 times"),
        ("A plus‐minus 3x", "en", "A plus‐minus 3 times"),
        ("A plus‑minus 3x", "en", "A plus‑minus 3 times"),
        ("PLUS–minus 3x", "en", "PLUS–minus 3 times"),
        ("A plus – minus 3x", "en", "A plus – minus 3x"),  # spaced: as "plus - minus", as before
        # #1010: a sign after "Nx", as one before it (#988, #997)
        ("So 3x > 2.", "en", "So 3 times greater than 2."),
        ("So 3x < 2.", "en", "So 3 times less than 2."),
        ("So 3x>2.", "en", "So 3 times greater than 2."),
        ("So 3x > A.", "en", "So 3 times greater than A."),
        ("So 3x > a b.", "en", "So 3 times greater than a b."),
        ("So 3x > e.g. 2.", "en", "So 3 times greater than for example 2."),
        ("So 3x > y.", "en", "So 3x greater than y."),
        ("So 3x >\ny.", "en", "So 3x greater than y."),
        ("So 3x < (a).", "en", "So 3x less than (a)."),
        ("So 3x >> 2 and 3x >= 2.", "en", "So 3x >> 2 and 3x >= 2."),
        ("So 3x >y.", "en", "So 3x >y."),
        ("So 3x − 2.", "en", "So 3x minus 2."),
        ("So 3x −2.", "en", "So 3x minus 2."),
        ("So 3x − .5.", "en", "So 3x minus .5."),
        ("So 3x − 2y.", "en", "So 3x minus 2y."),
        ("So 3x minus 2.", "en", "So 3x minus 2."),  # printed: as its sign
        ("So 3x minus\n2.", "en", "So 3x minus 2."),
        ("So 3x minus the rest.", "en", "So 3 times minus the rest."),
        ("So 3x Minus 2.", "en", "So 3 times Minus 2."),
        ("So 3x ± 2.", "en", "So 3 times plus or minus 2."),
        ("So 3x > 2.", "de", "So 3x größer als 2."),
        ("So 3x − 2.", "de", "So 3x − 2."),
        # #1010: "=" glued before a spaced minus sign the numbers step reads
        ("So A=− 3.", "en", "So A equals minus 3."),
        ("So A =− 3.", "en", "So A equals minus 3."),
        ("So A=−\n3.", "en", "So A equals minus 3."),
        ("So A=‒ 3.", "en", "So A equals minus 3."),
        ("So A=− .5.", "en", "So A equals minus .5."),
        ("So A=- 3.", "en", "So A=- 3."),
        ("So A <− 3.", "en", "So A <minus 3."),
        ("So A=− 3.", "de", "So A=− 3."),
        # #1010: a sign after a citation that starts the block and is removed
        ("[1] < 3x", "en", "less than 3 times"),
        ("[1] > 3", "en", "greater than 3"),
        ("[1, 2] ≤ 3x", "en", "less than or equal to 3x"),
        ("[1, 2] < 3x", "en", "less than 3 times"),
        ("It holds. [1] < 3x.", "en", "It holds. less than 3 times."),
        ("[1] = 3", "en", "= 3"),  # "=" needs a word before it: as before
        ("So [1] < 3x.", "en", "So less than 3 times."),
        ("[1] < 3x", "de", "kleiner als 3x"),
        # #1010: a part's numeral before a full stop and a sign the statistics step reads
        ("Kapitel IV.=1", "de", "Kapitel 4. gleich 1"),
        ("Kapitel IV.<1", "de", "Kapitel 4. kleiner als 1"),
        ("Kapitel IV.≤1", "de", "Kapitel 4. kleiner oder gleich 1"),
        ("Kapitel IV.=x", "de", "Kapitel 4. gleich x"),
        ("Kap. IV.=1", "de", "Kapitel 4. gleich 1"),
        ("Kapitel IV.==1", "de", "Kapitel IV.==1"),
        ("Kapitel IV.⇒1", "de", "Kapitel IV.⇒1"),
        ("Typ II.=1", "de", "Typ II. gleich 1"),
        # #1010: a range joined by "bis" is read none, as with full stops (#996)
        ("Kapitel I bis III", "de", "Kapitel I bis III"),
        ("Kapitel II bis IV folgen.", "de", "Kapitel II bis IV folgen."),
        ("Teil I bis II", "de", "Teil I bis II"),
        ("Kapitel I und II", "de", "Kapitel 1 und 2"),
        ("Kapitel I bis 3", "de", "Kapitel 1 bis 3"),
        # #870, #871: a four-digit number before an "x" read as "times"
        ("It grew 1234 x 5.", "en", "It grew 1,234 times 5."),
        ("It grew 1234x5.", "en", "It grew 1,234 times 5."),
        ("It grew 1234 X 5.", "en", "It grew 1,234 times 5."),
        ("It is 1234X larger.", "en", "It is 1,234 times larger."),
        ("It is 1234X.", "en", "It is 1,234 times."),
        ("It is 1920x1080.", "en", "It is 1920 times 1080."),
        ("It is 1234x, then.", "en", "It is 1,234 times, then."),
        ("It is 1234xy.", "en", "It is 1234xy."),
        ("It is 1234 xy.", "en", "It is 1234 xy."),
        ("It grew 2019× more.", "en", "It grew 2,019 times more."),
        ("It grew 2019x larger.", "en", "It grew 2,019 times larger."),
        ("It grew 2019 times.", "en", "It grew 2,019 times."),
        ("It grew 2019X.", "en", "It grew 2,019 times."),
        ("It is 2019 × 3.", "en", "It is 2019 times 3."),
        ("It is 2019 x 3.", "en", "It is 2019 times 3."),
        ("It is 2019 times 3.", "en", "It is 2019 times 3."),
        ("It is 2019 = 3.", "en", "It is 2019 equals 3."),
        ("In 2019 times were hard.", "en", "In 2019 times were hard."),
        ("Since 2019× more.", "en", "Since 2019 times more."),
        ("It grew 2000×.", "en", "It grew 2000 times."),
        # #816: the number of "to the power of" is no unit's number
        ("So A⁻¹ K.", "en", "So A to the power of minus 1 K."),
        ("So A⁻² kg.", "en", "So A to the power of minus 2 kg."),
        ("So (A)⁻¹ m.", "en", "So (A) to the power of minus 1 m."),
        ("So A² K.", "en", "So A squared K."),
        ("So 10⁻¹ K.", "en", "So 10 to the power of minus 1 kelvin."),
        ("So 2⁻¹x.", "en", "So 2 to the power of minus 1 times."),
        ("So 2⁻¹x faster.", "en", "So 2 to the power of minus 1 times faster."),
        ("Also A⁻¹ K.", "de", "Also A⁻¹ K."),
        ("Also 2⁻¹x.", "de", "Also 2 hoch minus 1 mal."),
    ],
)
def test_the_reading_is_the_same_on_both_runs(printed: str, language: str, said: str) -> None:
    assert _both_runs(printed, language) == (said, said)


@pytest.mark.parametrize(
    ("printed", "said"),
    [
        ("Kapitel I. Einleitung", "Kapitel 1. Einleitung"),
        ("Teil II.", "Teil 2."),
        ("Typ I.", "Typ I."),
        ("Kapitel I. und II.", "Kapitel I. und II."),  # #996
        ("Kapitel IV.=1", "Kapitel 4. gleich 1"),  # #1010
        ("Kapitel I bis III", "Kapitel I bis III"),  # #1010
    ],
)
def test_a_heading_reads_a_part_number_as_a_paragraph_does(printed: str, said: str) -> None:
    # #976
    assert _both_runs(printed, "de", BlockKind.HEADING) == (said, said)


@pytest.mark.parametrize(
    ("text", "arrow", "in_run"),
    [
        ("A ==> B", "=>", True),
        ("A >=> B", "=>", True),
        ("A ⇐==> B", "=>", True),  # the "=" after "⇐=" is that arrow's (#984)
        ("A ⇐=> B", "=>", True),
        ("A ⇐=<=> B", "<=>", False),  # "⇐=" ends before "<": two arrows
        ("A <<=> B", "<=>", True),
        ("A => B", "=>", False),
        ("A ⇒=> B", "=>", False),
    ],
)
def test_an_ascii_arrow_after_a_pieced_left_arrow(text: str, arrow: str, in_run: bool) -> None:
    start = text.rindex(arrow)
    assert in_ascii_run(text, start, arrow) is in_run
