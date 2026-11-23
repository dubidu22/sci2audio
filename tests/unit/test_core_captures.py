# ruff: noqa: RUF001  (the sentences are as papers print them)
"""The capture model of the study layer (#396, ADR-008 2.1): the data objects, their JSON
form with its format checks, and a golden file of that form.

When the JSON form changes on purpose, accept the new golden file with
`uv run pytest --snapshot-update` and explain the diff in the PR (D-60). A change to it is
a change of the `captures.json` format: it needs a new version and a reader for the old.
"""

from __future__ import annotations

import copy
import json
from dataclasses import replace
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st
from syrupy.assertion import SnapshotAssertion

from sci2audio.core import (
    Anchor,
    Capture,
    CaptureFile,
    CaptureFormatError,
    CaptureType,
    captures_from_data,
    captures_to_data,
)
from sci2audio.core.captures import MAX_CAPTURES, TEXT_LIMIT

DOC = "0123456789abcdef"
SENTENCE = "Sleep loss lowered recall by 12 % (p < .01) in the α-group."
ANCHOR = Anchor(3, 10, 10 + len(SENTENCE), SENTENCE)
TIME = "2026-11-20T19:04:00Z"
MARK = Capture("00000000000000a1", CaptureType.MARK, TIME, TIME, ANCHOR)
NOTE = Capture(
    "00000000000000b2",
    CaptureType.NOTE,
    TIME,
    "2026-11-21T08:30:12Z",
    Anchor(4, 0, 22, "Naps were not counted."),
    "Check the appendix: were naps\nreally left out?",
)
QUOTE = Capture("00000000000000c3", CaptureType.QUOTE, TIME, TIME, ANCHOR)
FILE = CaptureFile(DOC, (MARK, NOTE, QUOTE))


def test_the_three_types_are_mark_note_and_quote() -> None:
    assert [t.value for t in CaptureType] == ["mark", "note", "quote"]


def test_the_json_form_golden_file(snapshot: SnapshotAssertion) -> None:
    """The form `captures.json` is written in, for a file of each type and a carried-over
    one; it reads back to the same objects."""
    carried = CaptureFile(DOC, (MARK, NOTE), migrated_from="markers.json")
    forms = {
        "three types": captures_to_data(FILE),
        "carried over from markers.json": captures_to_data(carried),
        "no capture": captures_to_data(CaptureFile(DOC)),
    }
    assert forms == snapshot
    assert captures_from_data(forms["three types"]) == FILE
    assert captures_from_data(forms["carried over from markers.json"]) == carried
    assert captures_from_data(forms["no capture"]) == CaptureFile(DOC)


def test_the_json_form_keeps_a_fixed_key_order_and_no_time_of_the_audiobook() -> None:
    data = captures_to_data(FILE)
    assert list(data) == ["format", "version", "document", "captures"]
    assert data["format"] == "sci2audio-captures"
    assert data["version"] == 1
    assert list(data["captures"][0]) == ["id", "type", "created", "changed", "anchor", "text"]
    assert list(data["captures"][0]["anchor"]) == ["block", "start", "end", "text"]


def test_the_anchor_keeps_the_printed_sentence_verbatim() -> None:
    """D-57: the sentence as printed, symbols and all, survives the round trip through JSON."""
    text = json.dumps(captures_to_data(FILE), ensure_ascii=False)
    assert captures_from_data(json.loads(text)).captures[0].anchor.text == SENTENCE


def test_a_carried_over_file_reads_like_any_version_1_file() -> None:
    """ADR-008 review note: `migrated_from: markers.json` is allowed at file level."""
    data = captures_to_data(FILE)
    data["migrated_from"] = "markers.json"
    read = captures_from_data(data)
    assert read.captures == FILE.captures
    assert read.document == DOC
    assert read.migrated_from == "markers.json"
    assert captures_to_data(read)["migrated_from"] == "markers.json"


def test_counts_by_type_name_every_type() -> None:
    assert CaptureFile(DOC).count() == {
        CaptureType.MARK: 0,
        CaptureType.NOTE: 0,
        CaptureType.QUOTE: 0,
    }
    assert CaptureFile(DOC, (MARK, NOTE, replace(QUOTE, id="00000000000000d4"))).count() == {
        CaptureType.MARK: 1,
        CaptureType.NOTE: 1,
        CaptureType.QUOTE: 1,
    }


# ---- what is refused -------------------------------------------------------------------------


def _changed(path: tuple[Any, ...], value: object) -> dict[str, Any]:
    """The golden data with the value at `path` replaced, or removed for `...`."""
    data = copy.deepcopy(captures_to_data(FILE))
    *outer, last = path
    target: Any = data
    for key in outer:
        target = target[key]
    if value is ...:
        del target[last]
    else:
        target[last] = value
    return data


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("format",), "sci2audio-web-markers"),
        (("version",), 2),
        (("version",), True),
        (("version",), "1"),
        (("document",), 7),
        (("document",), ""),
        (("document",), ...),
        (("captures",), {}),
        (("captures",), ...),
        (("migrated_from",), "notes.txt"),
        (("migrated_from",), 1),
        (("migrated_from",), None),
        (("removed",), []),
        (("captures", 0), "a capture"),
        (("captures", 0, "id"), "00000000000000A1"),
        (("captures", 0, "id"), "a1"),
        (("captures", 0, "id"), 161),
        (("captures", 0, "type"), "card"),
        (("captures", 0, "type"), "Mark"),
        (("captures", 0, "created"), None),
        (("captures", 0, "changed"), "x" * 41),
        (("captures", 0, "text"), "a mark holds no text"),
        (("captures", 2, "text"), "nor does a quote"),
        (("captures", 1, "text"), "x" * (TEXT_LIMIT + 1)),
        (("captures", 1, "text"), "a NUL\x00"),
        (("captures", 1, "text"), ...),
        (("captures", 0, "time"), 12.5),
        (("captures", 0, "removed"), True),
        (("captures", 0, "anchor"), [3, 10, 70, SENTENCE]),
        (("captures", 0, "anchor", "block"), -1),
        (("captures", 0, "anchor", "block"), True),
        (("captures", 0, "anchor", "block"), 3.0),
        (("captures", 0, "anchor", "start"), "10"),
        (("captures", 0, "anchor", "end"), 9),
        (("captures", 0, "anchor", "text"), ""),
        (("captures", 0, "anchor", "text"), None),
        (("captures", 0, "anchor", "spoken"), "twelve percent"),
        (("captures", 2, "id"), "00000000000000a1"),
    ],
)
def test_data_this_version_cannot_read_is_refused_with_a_reason(
    path: tuple[Any, ...], value: object
) -> None:
    with pytest.raises(CaptureFormatError, match=r"\w"):
        captures_from_data(_changed(path, value))


@pytest.mark.parametrize("data", [None, [], "captures", 1, {"format": "sci2audio-captures"}])
def test_what_is_not_a_captures_file_is_refused(data: object) -> None:
    with pytest.raises(CaptureFormatError):
        captures_from_data(data)


def test_a_file_holds_at_most_the_limit() -> None:
    many = [
        captures_to_data(CaptureFile(DOC, (replace(MARK, id=f"{n:016x}"),)))["captures"][0]
        for n in range(MAX_CAPTURES + 1)
    ]
    data = {**captures_to_data(FILE), "captures": many}
    with pytest.raises(CaptureFormatError, match="at most"):
        captures_from_data(data)
    data["captures"] = many[:MAX_CAPTURES]
    assert len(captures_from_data(data).captures) == MAX_CAPTURES


def test_the_objects_refuse_what_the_file_would_refuse() -> None:
    with pytest.raises(CaptureFormatError):
        replace(MARK, text="a mark holds no text")
    with pytest.raises(CaptureFormatError):
        Anchor(0, 5, 4, "x")
    with pytest.raises(CaptureFormatError):
        CaptureFile(DOC, (MARK, MARK))
    with pytest.raises(CaptureFormatError):
        CaptureFile(DOC, migrated_from="other.json")
    assert replace(NOTE, text="").text == ""  # a note may be empty while it is being written


def test_the_error_is_a_value_error() -> None:
    assert issubclass(CaptureFormatError, ValueError)


# ---- any capture file survives the round trip ------------------------------------------------

_texts = st.text(st.characters(exclude_characters="\x00"), max_size=60)
_anchors = st.builds(
    lambda block, start, length, text: Anchor(block, start, start + length, text),
    st.integers(0, 10_000),
    st.integers(0, 10_000),
    st.integers(0, 500),
    _texts.filter(bool),
)


@st.composite
def _captures(draw: st.DrawFn) -> Capture:
    kind = draw(st.sampled_from(CaptureType))
    text = draw(_texts) if kind is CaptureType.NOTE else ""
    return Capture(
        draw(st.text("0123456789abcdef", min_size=16, max_size=16)),
        kind,
        draw(st.text(max_size=40)),
        draw(st.text(max_size=40)),
        draw(_anchors),
        text,
    )


_files = st.builds(
    CaptureFile,
    st.text(min_size=1, max_size=20),
    st.lists(_captures(), max_size=8, unique_by=lambda c: c.id).map(tuple),
    st.sampled_from([None, "markers.json"]),
)


@given(_files)
def test_any_captures_file_reads_back_the_same_through_json(captures: CaptureFile) -> None:
    data = captures_to_data(captures)
    assert captures_from_data(data) == captures
    text = json.dumps(data, ensure_ascii=False, indent=1)
    assert captures_from_data(json.loads(text)) == captures
    assert captures_to_data(captures_from_data(json.loads(text))) == data
