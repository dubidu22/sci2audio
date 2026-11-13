"""The text-step interface: categories, declared attributes, the registry order (#63, D-57)."""

import pytest

from sci2audio.core import Document, Edit, ScriptPiece, Span
from sci2audio.textprep import (
    ANY_LANGUAGE,
    BUILT_IN_STEPS,
    PAUSE_MARK,
    TEXT_STEP_API,
    Category,
    Stage,
    StepContext,
    TextStep,
    check_registry,
    spoken_text,
    step_problems,
)


class Step(TextStep):
    """A step that proposes nothing, with whatever attributes a test gives it."""

    def __init__(self, step_id="a-step", stage=Stage.INLINE, **attributes):
        self.id = step_id
        self.stage = stage
        self.languages = attributes.pop("languages", ("en",))
        self.category = attributes.pop("category", Category.CITATIONS)
        for name, value in attributes.items():
            setattr(self, name, value)

    def find(self, document: Document, context: StepContext) -> list[Edit]:
        return []


def test_the_categories_are_the_fixed_list_with_labels_people_know() -> None:
    assert [category.value for category in Category] == [
        "page-furniture",
        "characters",
        "footnotes",
        "citations",
        "links",
        "formulas",
        "tables-and-figures",
        "references",
        "abbreviations",
        "numbers-and-units",
    ]
    labels = [category.label for category in Category]
    assert len(set(labels)) == len(labels)
    assert Category.LINKS.label == "URLs, DOIs and e-mail addresses"
    assert all(label and label[0].isupper() for label in labels)


def test_a_step_with_valid_attributes_has_no_problems() -> None:
    assert step_problems(Step()) == []
    assert Step().api_version == TEXT_STEP_API


@pytest.mark.parametrize(
    ("attributes", "problem"),
    [
        ({"step_id": "Not Kebab"}, "id must be kebab-case"),
        ({"step_id": ""}, "id must be kebab-case"),
        ({"api_version": 0}, "api_version must be 1"),
        ({"category": "citations"}, "category must be a Category"),
        ({"stage": "inline"}, "stage must be a Stage"),
        ({"languages": ()}, "languages must be"),
        ({"languages": ["en"]}, "languages must be"),
        ({"languages": ("en-GB",)}, "languages must be"),
        ({"languages": ("English",)}, "languages must be"),
    ],
)
def test_bad_attributes_are_named(attributes: dict, problem: str) -> None:
    problems = step_problems(Step(**attributes))
    assert len(problems) == 1
    assert problem in problems[0]


@pytest.mark.parametrize(
    ("languages", "language", "handled"),
    [
        (("en",), "en", True),
        (("en",), "en-GB", True),
        (("en",), "EN-us", True),
        (("en",), "de", False),
        (("en", "de"), "de-AT", True),
        ((ANY_LANGUAGE,), "fr", True),
    ],
)
def test_a_step_handles_the_languages_it_declares(
    languages: tuple[str, ...], language: str, handled: bool
) -> None:
    assert Step(languages=languages).handles(language) is handled


def test_a_step_context_needs_a_language() -> None:
    with pytest.raises(ValueError, match="language"):
        StepContext("")


def test_the_built_in_registry_is_valid() -> None:
    check_registry(BUILT_IN_STEPS)
    assert [step.id for step in BUILT_IN_STEPS] == [
        "page-furniture",
        "unicode-clean-up",  # characters and hyphenation run last (D-150)
        "line-end-hyphens",
    ]


def test_block_steps_must_come_before_inline_steps() -> None:
    check_registry([Step("b", Stage.BLOCK), Step("i", Stage.INLINE), Step("j", Stage.INLINE)])
    with pytest.raises(ValueError, match="block step 'b' comes after inline step 'i'"):
        check_registry([Step("i", Stage.INLINE), Step("b", Stage.BLOCK)])


def test_a_step_id_may_be_used_once() -> None:
    with pytest.raises(ValueError, match="'twice' is used twice"):
        check_registry([Step("twice"), Step("twice")])


def test_the_registry_names_every_bad_step() -> None:
    with pytest.raises(ValueError, match=r"api_version must be 1.*languages must be"):
        check_registry([Step("old", api_version=0), Step("none", languages=())])


def test_spoken_text_reads_line_breaks_as_spaces() -> None:
    pieces = (
        ScriptPiece("Exposure to\ntrauma  may", Span(0, 0, 22)),
        ScriptPiece("", Span(0, 22, 22), pause=True),
        ScriptPiece("\tinterfere.\n", Span(0, 22, 34)),
    )
    assert spoken_text(pieces) == "Exposure to trauma may interfere."
    assert (
        spoken_text(pieces, show_pauses=True) == f"Exposure to trauma may {PAUSE_MARK} interfere."
    )
    assert spoken_text(()) == ""
