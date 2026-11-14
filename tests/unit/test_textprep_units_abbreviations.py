"""The units and abbreviations steps (#68, D-227 to D-243) and their word lists.

Each rule is pinned on short texts: what is read, and what is left as printed. The English
regression cases (`tests/regression/english.toml`) hold the same rules end to end; the
corpus snapshots show them on the papers.
"""

import os
import random
import time

import pytest
from hypothesis import given
from hypothesis import strategies as st

from sci2audio.core import Block, BlockKind, Document, Edit, EditKind, Span, check_edits
from sci2audio.testing import check_text_step, make_document
from sci2audio.textprep import (
    AbbreviationStep,
    Category,
    Stage,
    StepContext,
    UnitStep,
    run_steps,
    spoken_text,
    wording_for,
)
from sci2audio.textprep.notation import edits_through_unread
from sci2audio.textprep.wordlists import (
    abbreviations,
    parse_abbreviations,
    parse_units,
    units,
)

EN = StepContext("en")
UNITS = UnitStep()
ABBREVIATIONS = AbbreviationStep()


def said(
    step: UnitStep | AbbreviationStep, text: str, kind: BlockKind = BlockKind.PARAGRAPH
) -> str:
    """The block's text as read with only this step's edits."""
    document = make_document([(kind, text)])
    run = run_steps(document, EN, steps=(step,), strict=True)
    return spoken_text(run.script())


# ---- word lists ---------------------------------------------------------------------------


def test_the_english_and_german_lists_load_and_other_languages_have_none() -> None:
    listed = abbreviations("en-GB")
    assert listed is not None
    assert len(listed) > 30
    table = units("en")
    assert table is not None
    assert len(table.units) > 80
    assert table.magnitudes == {"K": "thousand", "k": "thousand", "M": "million",
                                "B": "billion", "bn": "billion"}  # fmt: skip
    assert abbreviations("fr") is None
    assert units("fr") is None
    german = units("de-AT")
    assert german is not None
    assert len(german.units) > 70
    assert german.decimal == ","
    assert german.magnitudes == {}
    assert all(unit.gender in ("m", "f", "n") for unit in german.units)
    assert table.decimal == "."
    assert table.ones == {}
    listed_de = abbreviations("de")
    assert listed_de is not None
    assert len(listed_de) > 60


def test_the_label_words_of_the_notices_read_as_the_abbreviation_list() -> None:
    """#64's notices and this step read every short label word the same way (D-235)."""
    listed = abbreviations("en")
    assert listed is not None
    reads = {form: entry.reads for entry in listed for form in entry.printed}
    for short, full in wording_for("en").label_words.items():
        assert reads[short] == full, short


def test_no_unit_form_is_also_a_magnitude_letter_except_the_spaced_kelvin() -> None:
    table = units("en")
    assert table is not None
    forms = {form for unit in table.units for form in unit.printed}
    assert forms & set(table.magnitudes) == {"K"}  # spaced: kelvin; glued: thousand (D-241)


GOOD_ABBREVIATION = (
    '[[abbreviation]]\nprinted = ["e.g."]\nreads = "for example"\nbefore = "anything"\n'
)


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("[[abbreviation]\n", "abbr.toml: "),
        (GOOD_ABBREVIATION.replace('reads = "for example"\n', ""), "reads must be words"),
        (GOOD_ABBREVIATION + "colour = 1\n", "unknown keys"),
        (GOOD_ABBREVIATION + GOOD_ABBREVIATION, "'e.g.' is listed twice"),
        (GOOD_ABBREVIATION.replace("anything", "always"), "before must be one of"),
        (GOOD_ABBREVIATION.replace('"e.g."', '"eg"'), "ends in a full stop"),
        (GOOD_ABBREVIATION.replace('["e.g."]', "[]"), "printed must be a list"),
        (GOOD_ABBREVIATION + "can_end_sentence = 1\n", "true or false"),
        (GOOD_ABBREVIATION + "exact_case = 1\n", "true or false"),
        (GOOD_ABBREVIATION + 'before_year = ""\n', "before_year must be words"),
        (
            GOOD_ABBREVIATION + "exact_case = true\n" + GOOD_ABBREVIATION + "exact_case = true\n",
            "'e.g.' is listed twice",
        ),
        (
            GOOD_ABBREVIATION + GOOD_ABBREVIATION.replace("e.g.", "E.G.") + "exact_case = true\n",
            "'E.G.' is also listed in any case",
        ),
    ],
)
def test_a_broken_abbreviation_list_names_the_file_and_entry(text: str, message: str) -> None:
    with pytest.raises(ValueError, match=message) as raised:
        parse_abbreviations("abbr.toml", text)
    assert str(raised.value).startswith("abbr.toml")


WORDS = (
    '[words]\nper = "per"\nsquare = "square"\ncubic = "cubic"\nsquared = "squared"\n'
    'cubed = "cubed"\napproximately = "approximately"\nabout = "about"\ntimes = "times"\n'
    'labels = ["figure"]\narticles = ["a"]\n'
)
GOOD_UNIT = '[[unit]]\nprinted = ["m"]\nsingular = "metre"\nplural = "metres"\n'


@pytest.mark.parametrize(
    ("text", "message"),
    [
        (GOOD_UNIT, "a \\[words\\] table is needed"),
        (WORDS.replace('times = "times"\n', "") + GOOD_UNIT, "times must be words"),
        (WORDS + GOOD_UNIT + GOOD_UNIT, "'m' is listed twice"),
        (WORDS + GOOD_UNIT.replace("plural", "plurals"), "unknown keys"),
        (WORDS + GOOD_UNIT + "length = 2\n", "true or false"),
        (WORDS + '[[magnitude]]\nprinted = ["K"]\nreads = "thousand"\n' * 2, "listed twice"),
        (WORDS + GOOD_UNIT.replace('["m"]', '[" m"]'), "printed must be a list"),
        (WORDS + 'decimal = ";"\n' + GOOD_UNIT, "decimal must be"),
        (WORDS + GOOD_UNIT + 'gender = "x"\n', "gender must be one of"),
        (WORDS + 'dative = ["mit"]\n' + GOOD_UNIT, "need a \\[words.one\\] table"),
        (
            WORDS + "[words.one]\ndative = { m = 'a', f = 'b', n = 'c' }\n" + GOOD_UNIT,
            "the nominative is needed",
        ),
        (
            WORDS + "[words.one]\nnominative = { m = 'a', f = 'b' }\n" + GOOD_UNIT,
            "give exactly the genders",
        ),
        (
            WORDS + "[words.one]\nnominative = { m = 'a', f = 'b', n = 'c' }\n" + GOOD_UNIT,
            "every unit needs a gender",
        ),
        (
            WORDS + "[words.one]\ngenitive = { m = 'a', f = 'b', n = 'c' }\n" + GOOD_UNIT,
            "unknown keys",
        ),
        (WORDS + "one = 3\n" + GOOD_UNIT, "one must be a table"),
    ],
)
def test_a_broken_unit_list_names_the_file_and_entry(text: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        parse_units("units.toml", text)


def test_a_good_unit_list_parses() -> None:
    table = parse_units("units.toml", WORDS + GOOD_UNIT)
    assert table.units[0].plural == "metres"
    assert table.labels == {"figure"}
    assert (table.decimal, table.joined_powers, table.hyphen_singular) == (".", False, True)


def test_articles_may_be_left_out_and_german_keys_parse() -> None:
    words = WORDS.replace('articles = ["a"]\n', "") + (
        'decimal = ","\njoined_powers = true\nhyphen_singular = false\n'
        'dative = ["Mit"]\naccusative = ["für"]\nlabel_joins = ["Bzw."]\n'
        "[words.one]\nnominative = { m = 'ein', f = 'eine', n = 'ein' }\n"
    )
    table = parse_units("units.toml", words + GOOD_UNIT + 'gender = "m"\n')
    assert table.articles == frozenset()
    assert (table.decimal, table.joined_powers, table.hyphen_singular) == (",", True, False)
    assert table.ones == {"nominative": {"m": "ein", "f": "eine", "n": "ein"}}
    assert (table.dative, table.accusative) == ({"mit"}, {"für"})
    assert table.label_joins == ("bzw.",)
    assert table.units[0].gender == "m"


# ---- abbreviations ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # anywhere (D-230)
        ("included, i.e., preschoolers", "included, that is, preschoolers"),
        ("E.g., the first", "For example, the first"),
        ("see i. e. this", "see that is this"),
        ("cf. the second, viz. the large one", "compare the second, namely the large one"),
        (
            "w.r.t. the weights, s.t. it falls; w.l.o.g. n is even",
            "with respect to the weights, such that it falls; without loss of generality n is even",
        ),
        (
            "Approx. half; approx. 30; esp. here; incl. two; avg. score",
            "Approximately half; approximately 30; especially here; including two; average score",
        ),
        ("Prof. Lee spoke", "Professor Lee spoke"),
        # before a number, a label or a word only
        ("built ca. 1900 or ca.1900", "built circa 1900 or circa 1900"),
        ("ca. that time", "ca. that time"),
        ("Nos. 4 and 5", "Numbers 4 and 5"),
        (
            "in Eq. (8), eq.(1), Eq. [3], Eq.[4], Eqs. 2 and 3, Eqn. 4",
            "in Equation (8), equation (1), Equation [3], Equation [4], Equations 2 and 3, "
            "Equation 4",
        ),
        (
            "Fig. 2a, Fig.4, Figs. 3, FIG. 3, fig. 2",
            "Figure 2a, Figure 4, Figures 3, Figure 3, figure 2",
        ),
        (
            "Sec. III, Sect. 2, Secs. 2, App. B, App.B",
            "Section III, Section 2, Sections 2, Appendix B, Appendix B",
        ),
        (
            "Alg. 1, Thm. 2, Def. 3, Prop. 4, Cor. 5, Lem. 6, Ch. 7, Chap. 8",
            "Algorithm 1, Theorem 2, Definition 3, Proposition 4, Corollary 5, Lemma 6, "
            "Chapter 7, Chapter 8",
        ),
        (
            "Tab. 2, Tabs. 3, Ref. 4, Refs. 5, Ex. 6, Exp. 7, Algs. 8",
            "Table 2, Tables 3, Reference 4, References 5, Example 6, Experiment 7, Algorithms 8",
        ),
        ("Suppl. Fig. 3 and Suppl. Material", "Supplementary Figure 3 and Supplementary Material"),
        (
            "the Tab. key, the Sec. The end, Suppl. here",
            "the Tab. key, the Sec. The end, Suppl. here",
        ),
        # left as printed (D-231 to D-233)
        (
            "Dr. Kim et al. compared No. 5 vs. No. 6, etc.",
            "Dr. Kim et al. compared No. 5 vs. No. 6, etc.",
        ),
        ("see p. 8 and pp. 3-5, vol. 2", "see p. 8 and pp. 3-5, vol. 2"),
        # not part of a longer word or dotted chain
        ("Piantadosi, S.T., and I.E. Smith", "Piantadosi, S.T., and I.E. Smith"),
        ("the gifs. and e.g.x and preFig. 2", "the gifs. and e.g.x and preFig. 2"),
    ],
)
def test_abbreviations_read(text: str, expected: str) -> None:
    assert said(ABBREVIATIONS, text) == expected


def test_an_abbreviation_edit_names_the_printed_form_and_its_reading() -> None:
    document = make_document([(BlockKind.PARAGRAPH, "Children, e.g., toddlers (Fig. 1).")])
    edits = ABBREVIATIONS.find(document, EN)
    assert [(e.span, e.kind, e.replacement, e.reason) for e in edits] == [
        (Span(0, 10, 14), EditKind.REPLACE, "for example",
         'abbreviation "e.g." read as "for example"'),
        (Span(0, 26, 30), EditKind.REPLACE, "Figure", 'abbreviation "Fig." read as "Figure"'),
    ]  # fmt: skip
    assert {e.step for e in edits} == {"abbreviations"}


@pytest.mark.parametrize(
    ("text", "expected", "end"),
    [
        ("scored 3 and 4, resp. The next", "scored 3 and 4, respectively. The next", 20),
        ("scored 3 and 4, resp.", "scored 3 and 4, respectively.", 20),
        (
            "scored 3 and 4, resp. \u201cThe next",
            "scored 3 and 4, respectively. \u201cThe next",
            20,
        ),
        ("scored 3 and 4, resp. the next", "scored 3 and 4, respectively the next", 21),
        ("as in e.g. BERT", "as in for example BERT", 10),
    ],
)
def test_a_sentence_end_keeps_its_full_stop(text: str, expected: str, end: int) -> None:
    """D-234: only abbreviations that can end a sentence leave their full stop there."""
    assert said(ABBREVIATIONS, text) == expected
    (edit,) = ABBREVIATIONS.find(make_document([(BlockKind.PARAGRAPH, text)]), EN)
    assert edit.span.end == end


def test_the_cutter_still_ends_the_sentence_after_a_kept_full_stop() -> None:
    document = make_document([(BlockKind.PARAGRAPH, "A and B, resp. The next one.")])
    from sci2audio.textprep import cut_utterances

    run = run_steps(document, EN, steps=(ABBREVIATIONS,), strict=True)
    cut = [u.text for u in cut_utterances(document, run.script())]
    assert cut == ["A and B, respectively.", "The next one."]


def test_white_space_inside_and_after_an_abbreviation() -> None:
    assert said(ABBREVIATIONS, "toddlers, e.\u00a0g., in") == "toddlers, for example, in"
    assert said(ABBREVIATIONS, "see Fig.\n2 and i.e.\nthis") == "see Figure 2 and that is this"
    assert said(ABBREVIATIONS, "see Fig.\u00a02") == "see Figure 2"


@pytest.mark.parametrize("kind", [BlockKind.FURNITURE, BlockKind.TABLE, BlockKind.FORMULA,
                                  BlockKind.FIGURE])  # fmt: skip
def test_furniture_and_placeholders_are_left_to_their_own_steps(kind: BlockKind) -> None:
    document = make_document([(kind, "e.g. 5 mg/kg at 37 \u00b0C, Fig. 2")])
    assert ABBREVIATIONS.find(document, EN) == []
    assert UNITS.find(document, EN) == []


@pytest.mark.parametrize("kind", [BlockKind.HEADING, BlockKind.CAPTION, BlockKind.LIST_ITEM,
                                  BlockKind.FOOTNOTE])  # fmt: skip
def test_every_other_kind_is_read(kind: BlockKind) -> None:
    assert said(ABBREVIATIONS, "Proof of Lem. 1", kind) == "Proof of Lemma 1"
    assert said(UNITS, "It took 5 mg", kind) == "It took 5 milligrams"


def test_the_steps_declare_their_categories_and_stage() -> None:
    assert (UNITS.id, UNITS.category, UNITS.stage) == (
        "units", Category.NUMBERS_AND_UNITS, Stage.INLINE)  # fmt: skip
    assert (ABBREVIATIONS.id, ABBREVIATIONS.category, ABBREVIATIONS.stage) == (
        "abbreviations", Category.ABBREVIATIONS, Stage.INLINE)  # fmt: skip
    assert UNITS.languages == ABBREVIATIONS.languages == ("en", "de")
    french = make_document([(BlockKind.PARAGRAPH, "p.ex. 5 mg, e.g.")], language="fr")
    assert run_steps(french, StepContext("fr"), strict=True).outcomes == ()


# ---- units --------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # TP-10's examples
        (
            "Doses of 3.5 mg/kg at 37 \u00b0C",
            "Doses of 3.5 milligrams per kilogram at 37 degrees Celsius",
        ),
        ("1 m and 5 km/h", "1 metre and 5 kilometres per hour"),
        # plural agreement (D-237)
        (
            "1 m, 1.0 m, 0.5 m, 2 m, 1,000 m",
            "1 metre, 1.0 metres, 0.5 metres, 2 metres, 1,000 metres",
        ),
        (
            "1\u20132 h, 0\u20131 h, 5-10 mg, \u22121 \u00b0C",
            "1\u20132 hours, 0\u20131 hours, 5-10 milligrams, \u22121 degree Celsius",
        ),
        (
            "a 5-km race, a 10-mg dose, a 1 m pole, an 8 h day",
            "a 5-kilometre race, a 10-milligram dose, a 1 metre pole, an 8 hour day",
        ),
        # per, negative exponents and powers (D-239)
        (
            "2 m s\u207b\u00b9, 3 m s^-1, 4 m s-1, 5 km h\u207b\u00b9",
            "2 metres per second, 3 metres per second, 4 metres per second, 5 kilometres per hour",
        ),
        (
            "2 mg kg\u207b\u00b9 day\u207b\u00b9 and 5 mg/kg/day",
            "2 milligrams per kilogram per day and 5 milligrams per kilogram per day",
        ),
        (
            "3 J/(kg\u00b7K) and 2 W/(m\u00b2\u00b7K)",
            "3 joules per kilogram per kelvin and 2 watts per square metre per kelvin",
        ),
        (
            "5 m\u00b2, 3 m^2, 4 cm\u00b3, 5 m2, 3 W m\u207b\u00b2, 6 kg/m\u00b3",
            "5 square metres, 3 square metres, 4 cubic centimetres, 5 square metres, "
            "3 watts per square metre, 6 kilograms per cubic metre",
        ),
        (
            "9.8 m/s\u00b2, 9.8 m/s2, 2 s\u00b2",
            "9.8 metres per second squared, 9.8 metres per second squared, 2 seconds squared",
        ),
        ("5 s\u207b\u00b9", "5 per second"),
        (
            "5 N m, 2 kW h, 3 kW\u00b7h, 4 N\u22c5m",
            "5 newton metres, 2 kilowatt hours, 3 kilowatt hours, 4 newton metres",
        ),
        # degrees and kelvin (D-240)
        (
            "37\u00b0C, 37 \u02daC, 37 \u2103, 37 \u00baC, 98 \u00b0F, 98 \u2109",
            "37 degrees Celsius, 37 degrees Celsius, 37 degrees Celsius, 37 degrees Celsius, "
            "98 degrees Fahrenheit, 98 degrees Fahrenheit",
        ),
        (
            "45\u00b0, 45 \u00b0, 1\u00b0, 300 K, 1 K",
            "45 degrees, 45 degrees, 1 degree, 300 kelvin, 1 kelvin",
        ),
        # glued and spaced (D-236)
        (
            "9kg, 0.1ps, 25meV, 12 GB, 5\u00a0mg, 5\u2009mg, 5\u202fmg, 5\nmg",
            "9 kilograms, 0.1 picoseconds, 25 millielectronvolts, 12 gigabytes, 5 milligrams, "
            "5 milligrams, 5 milligrams, 5 milligrams",
        ),
        (
            "1.42\u02daA, 5 \u00c5, 5 \u212b, 3.6eV\u02daA",
            "1.42 angstroms, 5 angstroms, 5 angstroms, 3.6 electronvolt angstroms",
        ),
        (
            "5 \u00b5m, 2 \u03bcm, 3 \u00b5L, 4 \u03a9, 5 k\u2126",
            "5 micrometres, 2 micrometres, 3 microlitres, 4 ohms, 5 kilohms",
        ),
        ("10\u2078 m/s and 3 \u00d7 10^8 m", "10\u2078 metres per second and 3 times 10^8 metres"),
        # magnitudes (D-241)
        (
            "441K apps, 332M words, 100k steps, 175B tokens, 2bn people, 1.5k items",
            "441 thousand apps, 332 million words, 100 thousand steps, 175 billion tokens, "
            "2 billion people, 1.5 thousand items",
        ),
        ("trained on 15M", "trained on 15 million"),  # at the end of the block (review)
        ("441K", "441 thousand"),
        ("300K.", "300 thousand."),
        # left as printed
        (
            "the 1990s, 2D maps, 5G, 5m, 5s, 2a, 3 in, at 5 pm, 12%, 12 %",
            "the 1990s, 2D maps, 5G, 5m, 5s, 2a, 3 in, at 5 pm, 12%, 12 %",
        ),
        (
            "Figure 2 A, Table 3 C, Fig. 2 h, step 4 s, group 5 m",
            "Figure 2 A, Table 3 C, Fig. 2 h, step 4 s, group 5 m",
        ),
        (
            "COVID-19 m, GPT-3 h, x2 m, B12 g, 10:30 h, 1/2 h, 0,5 mg",
            "COVID-19 m, GPT-3 h, x2 m, B12 g, 10:30 h, 1/2 h, 0,5 mg",
        ),
        ("1 A note, 5 A current, 5 A.", "1 A note, 5 A current, 5 amperes."),
        # a number inside a power is no number of its own
        ("5\u00b0^-1B, 5 s^{-1}B, 5 s^{2}K", "5\u00b0^-1B, 5 s^{-1}B, 5 s^{2}K"),
        ("5 m A and 10 V A", "5 metres A and 10 volts A"),
        ("5 day course and 2 weeks", "5 day course and 2 weeks"),
        ("5 mgs and 5 mg2 and 5 m3x", "5 mgs and 5 mg2 and 5 m3x"),
        ("5 K/s glued 5K/s", "5 kelvin per second glued 5K/s"),
        # a label word carries over a list of labels; a plural label word is a label word too
        (
            "Figures 2B and 3B, Figs. 2A and 3B, panels 2A and 4B, Tables 1A, 1B, and 2C",
            "Figures 2B and 3B, Figs. 2A and 3B, panels 2A and 4B, Tables 1A, 1B, and 2C",
        ),
        (
            "Types 1A or 2B, Figure 1, panels A and 3B, Fig. 3B\u2013D and 4B, Figures 2 and 3 A",
            "Types 1A or 2B, Figure 1, panels A and 3B, Fig. 3B\u2013D and 4B, Figures 2 and 3 A",
        ),
        (
            "Our 7B model, the 175B model, trained 7B and 13B models, between 2 and 3 B",
            "Our 7 billion model, the 175 billion model, trained 7 billion and 13 billion models, "
            "between 2 and 3 B",
        ),
    ],
)
def test_units_read(text: str, expected: str) -> None:
    assert said(UNITS, text) == expected


def test_a_unit_edit_names_the_printed_unit_and_its_reading() -> None:
    document = make_document([(BlockKind.PARAGRAPH, "Doses of 3.5 mg/kg and 9kg.")])
    edits = UNITS.find(document, EN)
    assert [(e.span, e.kind, e.replacement, e.reason) for e in edits] == [
        (Span(0, 13, 18), EditKind.REPLACE, "milligrams per kilogram",
         '"mg/kg" read as "milligrams per kilogram"'),
        (Span(0, 24, 26), EditKind.REPLACE, " kilograms", '"kg" read as "kilograms"'),
    ]  # fmt: skip


# ---- symbols ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "\u2248 95% and x \u2248 3 and x\u22483",
            "approximately 95% and x approximately 3 and x approximately 3",
        ),
        (
            "~5 runs, ~ 10, (~5), \u223c 0.1, ~-3, ~.5",
            "about 5 runs, about 10, (about 5), about 0.1, about -3, about .5",
        ),
        ("X ~ N(0, 1), 5~10, 5 ~ 10, ~/data", "X ~ N(0, 1), 5~10, 5 ~ 10, ~/data"),
        # after a unit and its power, "~" is "about"
        ("5 \u00c5\u00b3~5, 5 \u00c53~5", "5 cubic angstroms about 5, 5 cubic angstroms about 5"),
        (
            "3 \u00d7 4, d \u00d7 d, 2\u00d7 faster, \u00d710, a\u00d7b",
            "3 times 4, d times d, 2 times faster, times 10, a times b",
        ),
        ("\u00d7\u00d7 and \u2248\u2248", "\u00d7\u00d7 and \u2248\u2248"),
        (
            "3 x 4, 3x4, 1920x1080, 10x speedup, 3.5x., 2x3x4",
            "3 times 4, 3 times 4, 1920 times 1080, 10 times speedup, 3.5 times., "
            "2 times 3 times 4",
        ),
        (
            "0x1F, x86, 2 x n, 2xl, 0003-066X, 10.1/2x3",
            "0x1F, x86, 2 x n, 2xl, 0003-066X, 10.1/2x3",
        ),
        # in a formula the x is the variable: an operator before the number or after the x
        (
            "y = 2x + 1, the term 3x^2, f(x) = 4x., 2x(1+y), 5x/2, 1 - 3x, x<2x",
            "y = 2x + 1, the term 3x^2, f(x) = 4x., 2x(1+y), 5x/2, 1 - 3x, x<2x",
        ),
        (
            "a speedup (10x), 10x, and 4x faster",
            "a speedup (10 times), 10 times, and 4 times faster",
        ),
        ("\u00d75x and times 5x", "times 5x and times 5x"),  # "\u00d7" and its reading: operators
        ("35 \u2030 and 35\u2030", "35 per mille and 35 per mille"),
        (
            "\u00b5 = 3, \u00b5B, 5 \u00b5m, \u03bc = 2",
            "\u03bc = 3, \u03bcB, 5 micrometres, \u03bc = 2",
        ),
    ],
)
def test_symbols_read(text: str, expected: str) -> None:
    assert said(UNITS, text) == expected


def test_a_symbol_edit_names_the_symbol() -> None:
    document = make_document([(BlockKind.PARAGRAPH, "x \u2248 3, ~5, \u00b5B")])
    reasons = [e.reason for e in UNITS.find(document, EN)]
    assert reasons == [
        '"\u2248" read as "approximately"',
        '"~" read as "about"',
        'micro sign "\u00b5" read as the Greek letter "\u03bc"',
    ]


# ---- properties ---------------------------------------------------------------------------

_TOKENS = [
    "5", "1", "1.0", "0.5", "1,000", "10\u2078", "3", "-", "\u2212", "\u2013", " ", " ", " ",
    "\u00a0", "\n", "m", "mg", "kg", "km", "h", "s", "K", "A", "M", "k", "B", "\u00b0", "\u00b0C",
    "\u02daA", "\u00c5", "eV", "\u00b5m", "\u00b5", "\u03bc", "/", "/(", ")", "\u00b7", "\u00b2",
    "\u00b3", "\u207b\u00b9", "^2", "^-1", "2", "x", "X", "\u00d7", "\u2248", "~", "\u223c",
    "\u2030", "%", "e.g.", "i.e.", "E.g.", "i. e.", "Fig.", "fig.", "FIG.", "Eq.", "eq.", "(",
    "(1)", "App.", "B", "III", "resp.", "approx.", "ca.", "Suppl.", "The", "the", "a", "Figure",
    "note", ".", ",", "S.T.", "x86", "0x1F", "day", "Prof.",
]  # fmt: skip
_TEXTS = st.lists(st.sampled_from(_TOKENS), min_size=1, max_size=30).map("".join)


@st.composite
def unit_documents(draw: st.DrawFn) -> Document:
    """Paragraphs that always hold a unit and an abbreviation the steps read, plus random
    tokens around them, so every example exercises both steps (#83 density lesson)."""
    blocks = []
    for _ in range(draw(st.integers(1, 3))):
        text = draw(_TEXTS) + " 5 mg/kg, e.g. " + draw(_TEXTS)
        kind = draw(st.sampled_from([BlockKind.PARAGRAPH, BlockKind.FOOTNOTE, BlockKind.TABLE]))
        blocks.append(Block(kind, text))
    return make_document(blocks)


@given(unit_documents())
def test_both_steps_keep_the_contract_on_any_document(document: Document) -> None:
    """Spans valid, no overlap, the same edits each time, idempotent, no ask (conformance)."""
    for step in (UNITS, ABBREVIATIONS):
        check_text_step(step, [document], allow_ask=False)


def _digits(text: str) -> str:
    return "".join(char for char in text if char in "0123456789")


@given(unit_documents())
def test_no_step_adds_or_moves_a_digit(document: Document) -> None:
    """Replacements hold no digit; `units` removes only the digits of a unit's power, and
    `abbreviations` never touches one."""
    for edit in ABBREVIATIONS.find(document, EN) + UNITS.find(document, EN):
        assert not _digits(edit.replacement), edit
        removed = document.blocks[edit.span.block].text[edit.span.start : edit.span.end]
        if edit.step == "abbreviations":
            assert not _digits(removed), edit
        else:
            assert removed[:1] not in "0123456789", edit  # never the number itself


def test_random_token_soup_never_gives_overlapping_or_bad_edits() -> None:
    """A fixed-seed fuzz through `core.check_edits` (the check that found #103's overlaps);
    30,000 texts in the nightly run."""
    rng = random.Random(68)  # noqa: S311 (a fixed seed for a repeatable fuzz, not secrecy)
    count = 30_000 if os.environ.get("HYPOTHESIS_PROFILE") == "nightly" else 2_000
    for _ in range(count):
        text = "".join(rng.choice(_TOKENS) for _ in range(rng.randint(1, 25)))
        document = make_document([(BlockKind.PARAGRAPH, text)])
        for step in (UNITS, ABBREVIATIONS):
            check_edits(document, step.find(document, EN))


@pytest.mark.timeout(60)
def test_a_very_long_block_takes_no_more_than_linear_time() -> None:
    """100,000 characters of units and abbreviations: no per-match look-back (#103 lesson)."""
    text = ("It took 5 mg/kg, e.g. at 37 \u00b0C, ~5 runs, 3 x 4 grids and Fig. 2; " * 1600)[
        :100_000
    ]
    document = make_document([(BlockKind.PARAGRAPH, text)])
    started = time.perf_counter()
    edits = UNITS.find(document, EN) + ABBREVIATIONS.find(document, EN)
    assert time.perf_counter() - started < 3
    assert len(edits) > 9_000


# ---- second runs (#159, #160) -------------------------------------------------------------


def _both_runs(text: str) -> tuple[str, str]:
    document = make_document([(BlockKind.PARAGRAPH, text)])
    first = spoken_text(run_steps(document, EN, strict=True).script())
    again = make_document([(BlockKind.PARAGRAPH, first)])
    return first, spoken_text(run_steps(again, EN, strict=True).script())


@pytest.mark.parametrize(
    ("printed", "spoken"),
    [  # #159: a soft hyphen or zero-width space does not hide a unit or an abbreviation
        ("0\u00adK", "0 thousand"),
        ("5\u00adkg", "5 kilograms"),
        ("5 \u200bmg", "5 milligrams"),
        ("e.\u00adg. this", "for example this"),
        ("Fig\u200b. 3 shows", "Figure 3 shows"),
        # #160: once "x" reads "times", the number after it is found on the first run too
        ("5 5 mg/kg, e.g. 5 x86K", "5 5 milligrams per kilogram, for example 5 times 86 thousand"),
        ("5 x86K", "5 times 86 thousand"),
        # #253: a power before the x, which the numbers step reads in the same run
        ("10⁶ x1", "10 to the power of 6 times 1"),
        ("a 10⁶ x 3 grid", "a 10 to the power of 6 times 3 grid"),
        ("10⁸ x86K", "10 to the power of 8 times 86 thousand"),  # nightly seed 8006
        # ... and "<" before a CI read glued, as the statistics step leaves it
        ("<CI=", "<confidence interval ="),
        # ... and an x before the times sign, which reads "times" after it as before it
        ("5x\u00d7 3", "5x times 3"),
        ("a 5x times", "a 5x times"),
        # ... and an abbreviation before a link the links step removes
        ("See Fig. https://x.org/a 3.", "See Figure 3."),
        # ... and a label after a symbol and a full stop (nightly seed 6007)
        ("\u00d7.Figure 5 mg/kg", "times.Figure 5 mg/kg"),
    ],
)
def test_units_and_abbreviations_read_the_same_on_the_first_and_second_run(
    printed: str, spoken: str
) -> None:
    assert _both_runs(printed) == (spoken, spoken)


def test_an_edit_behind_an_unread_character_is_mapped_onto_the_printed_text() -> None:
    """#159: the edit's span is mapped back onto the printed text: the unit itself, after
    the soft hyphen, which the Unicode step leaves out."""
    document = make_document([(BlockKind.PARAGRAPH, "5\u00adkg and 5k\u200bg")])
    edits = UNITS.find(document, EN)
    assert [(e.span.start, e.span.end, e.replacement) for e in edits] == [
        (2, 4, " kilograms"),
        (10, 13, " kilograms"),  # an unread character inside the unit is taken in
    ]
    assert all("\u00ad" not in e.reason and "\u200b" not in e.reason for e in edits)


@pytest.mark.parametrize(
    "edit",
    [
        Edit(Span(0, 0, 1), EditKind.REMOVE, "gone", "fake"),
        Edit(Span(0, 1, 1), EditKind.PAUSE, "a breath", "fake"),
    ],
)
def test_only_replace_edits_are_mapped_back_through_unread_characters(edit: Edit) -> None:
    """Review F3 of PR #208: a remove or pause edit would come back as a remove of another
    span, so the adapter refuses it instead (#159)."""
    with pytest.raises(ValueError, match="only replace edits"):
        edits_through_unread(0, "5\u00adkg", lambda read: [edit], "fake")


# ---- German (#113, D-476, D-480) -----------------------------------------------------------

DE = StepContext("de")


def said_de(step: UnitStep | AbbreviationStep, text: str) -> str:
    document = make_document([(BlockKind.PARAGRAPH, text)], "de")
    return spoken_text(run_steps(document, DE, steps=(step,), strict=True).script())


def test_both_steps_handle_german() -> None:
    assert UNITS.handles("de")
    assert ABBREVIATIONS.handles("de-CH")
    assert not UNITS.handles("fr")


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("z. B. hier", "zum Beispiel hier"),
        ("z.B. hier", "zum Beispiel hier"),
        ("Z. B. hier", "Zum Beispiel hier"),
        ("z.\u202fB. hier", "zum Beispiel hier"),  # a narrow no-break space, as typeset
        ("d. h. so", "das heißt so"),
        ("u. a. in Berlin", "unter anderem in Berlin"),
        ("Müller u. a. (2019)", "Müller und andere (2019)"),
        ("Müller u. a., 2019", "Müller und andere, 2019"),
        ("Müller u.a. 2019", "Müller und andere 2019"),
        ("bzw. so", "beziehungsweise so"),
        # review of PR #228: capitals with umlauts, "u. a." only after a name, "ff.", "o. ä."
        ("Dr. Özdemir", "Doktor Özdemir"),
        ("Hunde usw. Ältere Studien", "Hunde und so weiter. Ältere Studien"),
        ("Das gilt u. a. 2019", "Das gilt unter anderem 2019"),
        ("S. 12 ff.", "Seite 12 folgende."),
        ("S. 12 ff. und mehr", "Seite 12 folgende und mehr"),
        ("Hunde o. ä. sind", "Hunde oder Ähnliches sind"),
        ("Hunde u.ä. sind", "Hunde und Ähnliches sind"),
        ("max. 5, min. 3", "maximal 5, minimal 3"),
        ("Kinder u. Jugend", "Kinder und Jugend"),
        ("U. Müller", "U. Müller"),  # an initial: "u." is found only in lower case
        ("Ein- o. Ausgang", "Ein- o. Ausgang"),  # "oder", "oben" or "ohne": left as printed
        ("Haupt- resp. Nebeneffekte", "Haupt- respektive Nebeneffekte"),
        ("Lehr- vs. Lernzeit", "Lehr- versus Lernzeit"),
        ("ca. 5", "zirka 5"),
        ("vgl. Kap. 3", "vergleiche Kapitel 3"),
        ("Vgl. Abb. 2a", "Vergleiche Abbildung 2a"),
        ("auf S. 12", "auf Seite 12"),
        ("S. Müller", "S. Müller"),  # an initial, not a page
        ("s. Abb. 3", "siehe Abbildung 3"),
        ("s. o.", "siehe oben."),
        ("Tab. (2)", "Tabelle (2)"),
        ("Gl. 4", "Gleichung 4"),
        ("Nr. 7", "Nummer 7"),
        ("Nr. sieben", "Nr. sieben"),  # not before a label
        ("Dr. Schmidt", "Doktor Schmidt"),
        ("Prof. Dr. Schmidt", "Professor Doktor Schmidt"),
        ("max. 5 Tage", "maximal 5 Tage"),
        ("12 min. lang", "12 min. lang"),  # the unit's, not "minimal"
        ("im 19. Jh.", "im 19. Jahrhundert."),
        ("50 v. Chr. entstand", "50 vor Christus entstand"),
        ("Hunde usw. Dann", "Hunde und so weiter. Dann"),
        ("Hunde etc.", "Hunde et zetera."),
        ("abb. 3", "abb. 3"),  # a noun abbreviation keeps its case: found only as printed
        ("et al. 2019", "et al. 2019"),
        ("e.g. here", "e.g. here"),  # the English list is not used for German
    ],
)
def test_german_abbreviations_read(text: str, expected: str) -> None:
    assert said_de(ABBREVIATIONS, text) == expected


def test_english_text_does_not_take_the_german_list() -> None:
    assert said(ABBREVIATIONS, "z. B. and d. h.") == "z. B. and d. h."


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("5 kg", "5 Kilogramm"),
        ("2,5 km", "2,5 Kilometer"),
        ("1.500 m", "1.500 Meter"),
        ("12.345,6 m", "12.345,6 Meter"),
        (",5 l", ",5 Liter"),
        ("2.5 s", "2.5 Sekunden"),  # a decimal point, as statistics print it
        ("3 h", "3 Stunden"),
        ("2 Std.", "2 Stunden."),  # the full stop at the end of the block stays
        ("2 Std. Pause", "2 Stunden Pause"),
        ("20 min", "20 Minuten"),
        ("5 Mio. Euro", "5 Millionen Euro"),
        ("37 °C", "37 Grad Celsius"),
        ("90°", "90 Grad"),
        ("300 K", "300 Kelvin"),
        ("40 m²", "40 Quadratmeter"),
        ("3 cm³", "3 Kubikzentimeter"),
        ("2 km2", "2 Quadratkilometer"),
        ("9,8 m/s²", "9,8 Meter pro Sekunde hoch 2"),
        ("50 km/h", "50 Kilometer pro Stunde"),
        ("5 mg/kg/Tag", "5 Milligramm pro Kilogramm pro Tag"),
        ("5 mg kg⁻¹", "5 Milligramm pro Kilogramm"),
        ("5 Tag", "5 Tag"),  # a word read as a unit only after "pro"
        ("10 kWh", "10 Kilowattstunden"),
        ("1 kWh", "eine Kilowattstunde"),
        ("1 kg", "ein Kilogramm"),
        ("1 s", "eine Sekunde"),
        ("1 m", "ein Meter"),
        ("1 Mio. Euro", "eine Million Euro"),
        ("nach 1 h", "nach einer Stunde"),
        ("mit 1 kg", "mit einem Kilogramm"),
        ("Mit 1 l", "Mit einem Liter"),
        ("für 1 m", "für einen Meter"),
        ("für 1 s", "für eine Sekunde"),
        ("um 1 °C", "um einen Grad Celsius"),
        ("\u22121 °C", "\u22121 Grad Celsius"),
        ("-1 °C", "-1 Grad Celsius"),
        ("±1 m", "±1 Meter"),
        ("1,0 s", "1,0 Sekunden"),
        ("0,1 s", "0,1 Sekunden"),
        ("21 s", "21 Sekunden"),
        ("2\u20131 s", "2\u20131 Sekunden"),  # the end of a range
        ("1-s-Takt", "Ein-Sekunde-Takt"),  # a compound: the uninflected "Ein"
        ("10-s-Takt", "10-Sekunden-Takt"),
        ("ein 5 m langer Stab", "ein 5 Meter langer Stab"),
        ("eine 2 s lange Pause", "eine 2 Sekunden lange Pause"),
        ("Abbildung 2 A", "Abbildung 2 A"),
        ("Gruppe 3 C", "Gruppe 3 C"),
        ("5 m Abstand", "5 Meter Abstand"),
        ("1 A Strom", "ein Ampere Strom"),
        # review of PR #228: case after "über", "auf", "ab"; German label joins; "min."
        ("über 1 kg", "über ein Kilogramm"),
        ("auf 1 m", "auf einen Meter"),
        ("ab 1 kg", "ab einem Kilogramm"),
        ("Bedingungen 1 bzw. 2 V", "Bedingungen 1 bzw. 2 V"),
        ("Gruppen 1 sowie 2 K", "Gruppen 1 sowie 2 K"),
        ("Gruppen 1 und 2 K", "Gruppen 1 und 2 K"),
        ("nach 12 min. Pause", "nach 12 Minuten Pause"),
        ("ein 1,5-l-Behälter", "ein 1,5-Liter-Behälter"),
        ("eine 1-kg-Packung", "eine Ein-Kilogramm-Packung"),
        ("z. B. 1-m", "z. B. ein-Meter"),  # no compound after it (nightly seed 7008)
        ("10 %", "10 Prozent"),
        ("10%", "10%"),  # glued: the voice reads it right
        ("um 1 %", "um ein Prozent"),
        ("5 ‰", "5 Promille"),
        ("5 €", "5 Euro"),
        ("für 1 €", "für einen Euro"),
        ("5 GB", "5 GB"),
        ("COVID-19 m", "COVID-19 m"),
    ],
)
def test_german_units_read(text: str, expected: str) -> None:
    assert said_de(UNITS, text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("3x so schnell", "3 mal so schnell"),
        ("2 \u00d7 3", "2 mal 3"),
        ("≈ 5", "ungefähr 5"),
        ("~10 Proben", "etwa 10 Proben"),
        ("y = 2x + 1", "y = 2x + 1"),
    ],
)
def test_german_symbols_read(text: str, expected: str) -> None:
    assert said_de(UNITS, text) == expected


def test_a_one_edit_covers_the_number_and_names_it() -> None:
    document = make_document([(BlockKind.PARAGRAPH, "nach 1 h")], "de")
    edits = UNITS.find(document, DE)
    assert [(e.span.start, e.span.end, e.replacement, e.reason) for e in edits] == [
        (5, 6, "einer", '"1" read as "einer"'),
        (7, 8, "Stunde", '"h" read as "Stunde"'),
    ]


def test_english_numbers_keep_their_own_pattern() -> None:
    assert said(UNITS, "1,500 m and 2,5 km") == "1,500 metres and 2,5 km"
    assert said(UNITS, "1 kg") == "1 kilogram"


_GERMAN_TOKENS = [
    "5", "1", "1,0", "0,5", "1.500", "2.5", ",5", "3", "-", "\u2212", "\u2013", " ", " ", " ",
    "\u00a0", "\n", "m", "mg", "kg", "km", "h", "s", "Std.", "Mio.", "K", "A", "\u00b0",
    "\u00b0C", "/", "/(", ")", "\u00b7", "\u00b2", "\u00b3", "\u207b\u00b9", "x", "\u00d7",
    "\u2248", "~", "%", "z. B.", "Z.B.", "u. a.", "(2019)", "S.", "s.", "s. o.", "Abb.", "abb.",
    "Nr.", "usw.", "Dr.", "max.", "min", "min.", "nach", "mit", "für", "Abbildung", "Tag",
    "Strom", "ein", ".", ",", "ä", "ß", "Über",
]  # fmt: skip
_GERMAN_TEXTS = st.lists(st.sampled_from(_GERMAN_TOKENS), min_size=1, max_size=30).map("".join)


@st.composite
def german_unit_documents(draw: st.DrawFn) -> Document:
    """German paragraphs that always hold a unit after "1" and an abbreviation, plus random
    tokens, so every example exercises both German paths."""
    blocks = []
    for _ in range(draw(st.integers(1, 3))):
        text = draw(_GERMAN_TEXTS) + " nach 1 h, 2,5 mg/kg, z. B. " + draw(_GERMAN_TEXTS)
        kind = draw(st.sampled_from([BlockKind.PARAGRAPH, BlockKind.FOOTNOTE, BlockKind.TABLE]))
        blocks.append(Block(kind, text))
    return make_document(blocks, "de")


@given(german_unit_documents())
def test_both_steps_keep_the_contract_on_any_german_document(document: Document) -> None:
    for step in (UNITS, ABBREVIATIONS):
        check_text_step(step, [document], allow_ask=False)


@given(german_unit_documents())
def test_german_edits_add_no_digit_and_take_a_number_only_for_one(document: Document) -> None:
    """Replacements hold no digit except a unit's "hoch 2"; the only number a unit edit
    takes is a bare "1", read "ein", "eine", "einem", "einer" or "einen"."""
    for edit in ABBREVIATIONS.find(document, DE) + UNITS.find(document, DE):
        assert not _digits(edit.replacement.replace("hoch 2", "").replace("hoch 3", "")), edit
        removed = document.blocks[edit.span.block].text[edit.span.start : edit.span.end]
        if edit.step == "abbreviations":
            assert not _digits(removed), edit
        elif removed[:1] in "0123456789":
            assert removed == "1", edit
            assert edit.replacement in ("ein", "eine", "einem", "einer", "einen"), edit


def test_random_german_token_soup_never_gives_overlapping_or_bad_edits() -> None:
    rng = random.Random(113)  # noqa: S311 (a fixed seed for a repeatable fuzz, not secrecy)
    count = 30_000 if os.environ.get("HYPOTHESIS_PROFILE") == "nightly" else 2_000
    for _ in range(count):
        text = "".join(rng.choice(_GERMAN_TOKENS) for _ in range(rng.randint(1, 25)))
        document = make_document([(BlockKind.PARAGRAPH, text)], "de")
        for step in (UNITS, ABBREVIATIONS):
            check_edits(document, step.find(document, DE))


def _both_runs_de(text: str) -> tuple[str, str]:
    document = make_document([(BlockKind.PARAGRAPH, text)], "de")
    first = spoken_text(run_steps(document, DE, strict=True).script())
    again = make_document([(BlockKind.PARAGRAPH, first)], "de")
    return first, spoken_text(run_steps(again, DE, strict=True).script())


@pytest.mark.parametrize(
    "printed",
    ["nach 1 h mit 1 kg", "40 m² und 9,8 m/s²", "z. B. S. 12, s. o.", "5 Mio. Euro",
     "Müller u. a. (2019)", "1 Mio.", "3x so schnell"],
)  # fmt: skip
def test_german_units_and_abbreviations_read_the_same_on_a_second_run(printed: str) -> None:
    first, again = _both_runs_de(printed)
    assert first == again
