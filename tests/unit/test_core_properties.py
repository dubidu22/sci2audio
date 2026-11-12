"""Property-based tests (Hypothesis) for the core objects (issue #17).

Rules that must hold for any document and any edits: spans stay inside their block,
overlapping edits are refused with a clear error, and applying valid edits never raises.
"""

import dataclasses
import json

import pytest
from core_strategies import (
    chunks_in,
    documents,
    edits_on,
    overlapping_spans,
    overlaps,
    spans_in,
)
from hypothesis import assume, given
from hypothesis import strategies as st

from sci2audio.core import (
    AudioChunk,
    Document,
    Edit,
    EditKind,
    OverlappingEditsError,
    Span,
    SpanError,
    apply_edits,
    from_data,
    to_data,
)

non_empty_documents = documents().filter(lambda d: d.blocks)


@st.composite
def document_with_edits(draw: st.DrawFn) -> tuple[Document, list[Edit]]:
    """A document and edits on it that do not overlap (kept greedily, in drawn order)."""
    document = draw(non_empty_documents)
    kept: list[Edit] = []
    for _ in range(draw(st.integers(0, 8))):
        edit = draw(edits_on(draw(spans_in(document))))
        if not any(overlaps(edit.span, other.span) for other in kept):
            kept.append(edit)
    return document, kept


@given(document=non_empty_documents, data=st.data())
def test_span_check_matches_block_length(document: Document, data: st.DataObject) -> None:
    index = data.draw(st.integers(0, len(document.blocks) + 1))
    start = data.draw(st.integers(0, 50))
    span = Span(index, start, start + data.draw(st.integers(0, 50)))
    inside = index < len(document.blocks) and span.end <= len(document.blocks[index].text)
    if inside:
        document.check_span(span)
    else:
        with pytest.raises(SpanError):
            document.check_span(span)


@given(case=document_with_edits())
def test_applying_valid_edits_never_raises(case: tuple[Document, list[Edit]]) -> None:
    document, edits = case
    pieces = apply_edits(document, edits)
    for piece in pieces:
        document.check_span(piece.span)  # every piece points inside its block
    assert apply_edits(document, list(reversed(edits))) == pieces  # order of edits is irrelevant


@given(case=document_with_edits())
def test_kept_text_is_the_original(case: tuple[Document, list[Edit]]) -> None:
    document, edits = case
    edited = {edit.span for edit in edits}
    for piece in apply_edits(document, edits):
        if piece.span not in edited:
            assert piece.text == document.text_of(piece.span)


@given(document=documents())
def test_no_edits_reads_every_block_unchanged(document: Document) -> None:
    pieces = apply_edits(document, [])
    for index, block in enumerate(document.blocks):
        assert "".join(p.text for p in pieces if p.span.block == index) == block.text


@given(document=non_empty_documents, data=st.data())
def test_overlapping_edits_are_refused(document: Document, data: st.DataObject) -> None:
    first = data.draw(edits_on(data.draw(spans_in(document))))
    second = data.draw(edits_on(data.draw(overlapping_spans(document, first.span))))
    assert overlaps(first.span, second.span)  # checks the strategy against the rule
    pair = data.draw(st.permutations([first, second]))
    with pytest.raises(OverlappingEditsError, match="overlaps") as error:
        apply_edits(document, pair)
    assert {error.value.first, error.value.second} == {first, second}


@given(document=non_empty_documents, data=st.data())
def test_ask_edits_keep_the_original(document: Document, data: st.DataObject) -> None:
    span = data.draw(spans_in(document))
    ask = Edit(span, EditKind.ASK, reason="unsure", step="s1", replacement="maybe")
    assert "".join(p.text for p in apply_edits(document, [ask])) == "".join(
        block.text for block in document.blocks
    )


@given(document=documents())
def test_document_round_trips_through_export(document: Document) -> None:
    data = to_data(document)
    assert from_data(Document, data) == document
    assert from_data(Document, json.loads(json.dumps(data))) == document


@given(document=documents())
def test_export_is_sorted_and_repeatable(document: Document) -> None:
    text = json.dumps(to_data(document))
    assert text == json.dumps(to_data(document), sort_keys=True)
    assert text == json.dumps(to_data(from_data(Document, json.loads(text))))


@given(case=document_with_edits(), data=st.data())
def test_edits_and_chunks_round_trip(
    case: tuple[Document, list[Edit]], data: st.DataObject
) -> None:
    document, edits = case
    chunk = data.draw(chunks_in(document))
    assert from_data(AudioChunk, to_data(chunk)) == chunk
    for edit in edits:
        assert from_data(Edit, json.loads(json.dumps(to_data(edit)))) == edit


@given(document=documents(), data=st.data())
def test_a_document_that_loses_an_item_is_refused(document: Document, data: st.DataObject) -> None:
    with_parts = [i for i, block in enumerate(document.blocks) if block.parts]
    assume(with_parts)
    index = data.draw(st.sampled_from(with_parts))
    blocks = document.blocks[:index] + document.blocks[index + 1 :]
    with pytest.raises(ValueError, match="nothing may be lost"):
        dataclasses.replace(document, blocks=blocks, sections=())
