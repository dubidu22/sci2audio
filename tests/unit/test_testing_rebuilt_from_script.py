"""`rebuilt_from_script` (D-577): the second-run document keeps each block's label while the
script still reads the label's words, as the script reads them, also when a step rewrote
them (#324, D-578)."""

from sci2audio.core import Block, BlockKind, ScriptPiece, Span
from sci2audio.testing import make_document, rebuilt_from_script
from sci2audio.textprep import StepContext, run_steps, spoken_text


def _figure_and_caption(caption: str, label: str, language: str = "en"):
    return make_document(
        [
            Block(BlockKind.FIGURE, "0 10 20"),
            Block(BlockKind.CAPTION, caption, describes=0, label=label),
        ],
        language,
    )


def _read(document) -> list[str]:
    script = run_steps(document, StepContext(document.language), strict=True).script()
    return [
        spoken_text([piece for piece in script if piece.span.block == index])
        for index in range(len(document.blocks))
    ]


def test_a_label_a_step_spelled_out_stays_and_names_the_figure_again() -> None:
    document = _figure_and_caption(
        "Abb. 1: Anwendungsfälle und Datenstrukturen.", "Abb. 1", language="de"
    )
    first = run_steps(document, StepContext("de"), strict=True)
    rebuilt = rebuilt_from_script(document, first.script())
    assert rebuilt.blocks[1].text == "Abbildung 1: Anwendungsfälle und Datenstrukturen."
    assert rebuilt.blocks[1].label == "Abbildung 1"
    assert (
        _read(rebuilt)
        == _read(document)
        == [
            "Abbildung 1 wird übersprungen.",
            "Abbildung 1: Anwendungsfälle und Datenstrukturen.",
        ]
    )


def test_a_label_read_as_printed_stays() -> None:
    document = _figure_and_caption("Figure 3. Response over time.", "Figure 3")
    first = run_steps(document, StepContext("en"), strict=True)
    assert rebuilt_from_script(document, first.script()).blocks[1].label == "Figure 3"


def test_a_label_whose_words_were_all_removed_goes() -> None:
    """The script reads only the caption's text after its label: no label is made up."""
    document = _figure_and_caption("Fig. 3. Response over time.", "Fig. 3")
    script = [ScriptPiece("Response over time.", Span(1, 8, 27))]
    assert rebuilt_from_script(document, script).blocks[1].label == ""


def test_a_label_next_to_a_pause_only_goes() -> None:
    document = _figure_and_caption("Fig. 3. Response.", "Fig. 3")
    script = [ScriptPiece("", Span(1, 3, 3), pause=True), ScriptPiece("Response.", Span(1, 8, 17))]
    assert rebuilt_from_script(document, script).blocks[1].label == ""


def test_a_block_the_script_left_out_loses_its_label() -> None:
    document = _figure_and_caption("Fig. 3. Response.", "Fig. 3")
    script = [ScriptPiece("A figure is skipped.", Span(0, 0, 7))]
    rebuilt = rebuilt_from_script(document, script)
    assert (rebuilt.blocks[1].text, rebuilt.blocks[1].label) == ("", "")


def test_a_label_read_inside_a_longer_replacement_stays_only_where_the_new_text_prints_it() -> None:
    """A replacement that runs past the label's edge cannot be mapped: the label stays only
    if the new text still prints it, as before #324."""
    document = _figure_and_caption("Fig. 3. Response over time.", "Fig. 3")
    script = [ScriptPiece("The response over time.", Span(1, 0, 27))]
    assert rebuilt_from_script(document, script).blocks[1].label == ""
    script = [ScriptPiece("Fig. 3: the response over time.", Span(1, 0, 27))]
    assert rebuilt_from_script(document, script).blocks[1].label == "Fig. 3"


def test_a_label_partly_removed_keeps_what_is_read() -> None:
    document = _figure_and_caption("Fig. 3. Response.", "Fig. 3")
    script = [ScriptPiece("Figure", Span(1, 0, 4)), ScriptPiece(". Response.", Span(1, 6, 17))]
    rebuilt = rebuilt_from_script(document, script)
    assert (rebuilt.blocks[1].text, rebuilt.blocks[1].label) == ("Figure. Response.", "Figure")


def test_a_placeholder_label_is_not_mapped_into_its_notice() -> None:
    """A notice replaces a placeholder's whole text: its label stays as printed if the
    notice prints it and is never the notice itself (nightly seed 555 of the runner's
    idempotence property)."""
    document = make_document([Block(BlockKind.FORMULA, "0", label="0")])
    first = run_steps(document, StepContext("en"), strict=True)
    rebuilt = rebuilt_from_script(document, first.script())
    assert (rebuilt.blocks[0].text, rebuilt.blocks[0].label) == ("Formula 0 is skipped.", "0")
    assert _read(rebuilt) == _read(document) == ["Formula 0 is skipped."]
    script = [ScriptPiece("A formula is skipped.", Span(0, 0, 1))]
    assert rebuilt_from_script(document, script).blocks[0].label == ""
