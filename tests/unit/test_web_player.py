"""The read-along player's data and routes (#78, OU-02; D-294 to D-303).

Part one builds the page's view from hand-made documents and read-along data; part two
runs a real audio job with the fake voice and real ffmpeg (a few seconds, allowed in the
fast tier) and checks the page, the audiobook file route and the path checks (D-295).
"""

from __future__ import annotations

import dataclasses
import errno
import itertools
import json
import os
import re
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest
from audio_fakes import FakeVoice
from hypothesis import given
from hypothesis import strategies as st
from pdf_maker import Text, make_pdf
from web_helpers import (
    events,
    make_config,
    offline,  # noqa: F401 - fixture
    paper_bytes,
    program,
    upload,
)

from sci2audio.core import Block, BlockKind, Document, Page, Section, Span
from sci2audio.output import ReadAlong
from sci2audio.output.readalong import ChapterTimes, ChunkTimes, to_json
from sci2audio.testing.documents import make_document
from sci2audio.voices import EngineError
from sci2audio.web import create_app, player, tasks
from sci2audio.web.player import (
    AudioRecord,
    PlayerError,
    bare_name,
    build_view,
    joined_hyphens,
    shown,
)

# ---- the view, from hand-made data ------------------------------------------------------


def record(**changes: Any) -> AudioRecord:
    values: dict[str, Any] = {
        "voice": "af_heart",
        "switched_off": frozenset({"footnote-texts"}),
        "duration": 10.0,
        "chunks": 0,
        "m4b": "Book.m4b",
        "mp3s": ("Book - 01 One.mp3",),
        "readalong": "Book.readalong.json",
    }
    values.update(changes)
    return AudioRecord(**values)


def readalong(
    spans: Sequence[tuple[int, int, int]],
    chapters: Sequence[tuple[str, int]] = (("One", 0),),
    chapter_of: Sequence[int] | None = None,
) -> ReadAlong:
    """Chunks one second apart; `chapters` as (title, first chunk)."""
    owners = list(chapter_of) if chapter_of is not None else [0] * len(spans)
    chunks = tuple(
        ChunkTimes(owners[n], float(n), n + 0.5, Span(*span)) for n, span in enumerate(spans)
    )
    times = tuple(
        ChapterTimes(title, f"Book - {n + 1:02d} {title}.mp3", float(first), 99.0, first)
        for n, (title, first) in enumerate(chapters)
    )
    return ReadAlong(24000, float(len(spans)), "Book.m4b", times, chunks)


def on_pages(document: Document, pages: Sequence[int], labels: Sequence[str] = ()) -> Document:
    """The document with block n's lines on page `pages[n]`."""
    lines: dict[int, list[Any]] = {}
    items = {line.id: line for line in document.content.pages[0].lines}
    for number, block in enumerate(document.blocks):
        for part in block.parts:
            lines.setdefault(pages[number], []).append(items[part.item])
    count = max(pages)
    content = dataclasses.replace(
        document.content,
        pages=tuple(Page(n, tuple(lines.get(n, ()))) for n in range(1, count + 1)),
    )
    return dataclasses.replace(document, content=content, page_labels=tuple(labels))


def texts(view: player.PlayerView) -> list[str]:
    out = []
    for chapter in view.chapters:
        blocks = ([chapter.title_block] if chapter.title_block else []) + chapter.blocks
        out += ["".join(p.text for p in b.pieces) or b.notice for b in blocks]
    return out


def test_every_chunk_is_one_element_around_exactly_its_text() -> None:
    document = make_document(
        [("heading", "1 One"), ("paragraph", "First sentence. Second (Smith 2020) one.")]
    )
    data = readalong([(0, 0, 5), (1, 0, 15), (1, 16, 40)])
    view = build_view(document, record(chunks=3), data)
    (chapter,) = view.chapters
    assert chapter.title_block is not None
    assert chapter.title_block.heading == 2
    pieces = chapter.blocks[0].pieces
    assert [(p.text, p.element, p.chunk) for p in pieces] == [
        ("First sentence.", "s1", 1),
        (" ", None, None),
        ("Second (Smith 2020) one.", "s2", 2),
    ]
    assert [c[3] for c in view.chunks] == ["s0", "s1", "s2"]
    assert view.mode == "mp3"
    data = view.data("0123456789abcdef")
    assert data["document"] == "0123456789abcdef"
    assert data["chapters"][0]["file"] == "Book - 01 One.mp3"


def test_an_empty_span_belongs_to_the_sentence_before_it_or_its_block() -> None:
    document = make_document([("paragraph", "Long one. Then"), ("figure", "")])
    data = readalong([(0, 0, 9), (0, 9, 9), (1, 0, 0)])
    view = build_view(
        document, record(chunks=3, switched_off=frozenset({"tables-and-figures"})), data
    )
    assert [c[3] for c in view.chunks] == ["s0", "s0", "b1"]
    figure = view.chapters[0].blocks[1]
    assert figure.element == "b1"
    assert figure.chunk == 2
    assert figure.read


def test_furniture_is_left_out_and_printed_pages_are_marked() -> None:
    document = make_document(
        [
            ("paragraph", "On page one."),
            ("furniture", "39"),
            ("paragraph", "On page two."),
            ("paragraph", "Still page two."),
        ]
    )
    document = on_pages(document, [1, 1, 2, 2], ["38", "39"])
    data = readalong([(0, 0, 12), (2, 0, 12), (3, 0, 15)])
    view = build_view(document, record(chunks=3), data)
    blocks = view.chapters[0].blocks
    assert [b.index for b in blocks] == [0, 2, 3]
    assert [b.page for b in blocks] == ["38", "39", ""]


def test_pages_without_a_printed_label_use_the_page_number() -> None:
    document = on_pages(make_document([("paragraph", "A."), ("paragraph", "B.")]), [1, 2])
    view = build_view(document, record(chunks=2), readalong([(0, 0, 2), (1, 0, 2)]))
    assert [b.page for b in view.chapters[0].blocks] == ["1", "2"]


def test_a_placeholder_shows_the_notice_the_audiobook_reads() -> None:
    blocks = [
        ("paragraph", "See the table."),
        ("table", "a b\n1 2"),
        Block(BlockKind.CAPTION, "Table 2: Results.", describes=1, label="Table 2"),
        Block(BlockKind.FORMULA, "x = y (3)", label="3"),
    ]
    document = make_document(blocks)
    data = readalong([(0, 0, 14), (1, 0, 7), (2, 0, 17), (3, 0, 9)])
    view = build_view(document, record(chunks=4), data)
    table, caption, formula = view.chapters[0].blocks[1:]
    assert table.notice == "Table 2 is skipped."
    assert table.printed == "a b 1 2"
    assert table.element == "b1"
    assert view.chunks[1][3] == "b1"
    assert caption.notice == ""
    assert caption.pieces[0].element == "s2"
    assert formula.notice.startswith("Formula 3")
    # switched off, the formula was read as printed: its text is the sentence
    off = build_view(document, record(chunks=4, switched_off=frozenset({"formulas"})), data)
    formula = off.chapters[0].blocks[3]
    assert formula.notice == ""
    assert formula.pieces[0].text == "x = y (3)"


def test_a_code_block_shows_its_notice_and_its_code_with_its_line_breaks() -> None:
    """#280, D-546: the notice is the sentence; the code is shown open, line breaks kept."""
    code = 'import seaborn as sns\ng = sns.relplot(\ng.savefig("paper_demo.pdf")'
    document = make_document([("paragraph", "Run this:"), ("code", code)])
    data = readalong([(0, 0, 9), (1, 0, len(code))])
    view = build_view(document, record(chunks=2), data)
    block = view.chapters[0].blocks[1]
    assert (block.notice, block.code, block.printed) == ("A code block is skipped.", code, "")
    assert block.element == "b1"
    assert view.chunks[1][3] == "b1"
    off = build_view(document, record(chunks=2, switched_off=frozenset({"code"})), data)
    block = off.chapters[0].blocks[1]
    assert (block.notice, block.code) == ("", "")
    assert block.pieces[0].text == " ".join(code.split("\n"))


def test_chapters_not_in_the_audiobook_are_named() -> None:
    document = make_document(
        [
            ("heading", "Intro"),
            ("paragraph", "Text."),
            ("heading", "References"),
            ("paragraph", "R."),
        ],
        sections=(Section("Intro", 1, 0, 2), Section("References", 1, 2, 4)),
    )
    view = build_view(document, record(chunks=2), readalong([(0, 0, 5), (1, 0, 5)]))
    assert [c.title for c in view.chapters] == ["One"]
    assert view.left_out == ["References"]


def test_heading_levels_follow_the_sections() -> None:
    document = make_document(
        [("heading", "1 A"), ("heading", "1.1 B"), ("paragraph", "x."), ("heading", "Loose")],
        sections=(Section("1 A", 1, 0, 4, (Section("1.1 B", 2, 1, 4),)),),
    )
    data = readalong([(0, 0, 3), (1, 0, 5), (2, 0, 2), (3, 0, 5)])
    view = build_view(document, record(chunks=4), data)
    chapter = view.chapters[0]
    assert chapter.title_block is not None
    assert chapter.title_block.heading == 2
    assert [b.heading for b in chapter.blocks] == [3, 0, 4]


def test_a_block_with_nothing_read_says_so() -> None:
    document = make_document([("paragraph", "Read."), ("paragraph", "Removed by a step.")])
    view = build_view(document, record(chunks=1), readalong([(0, 0, 5)]))
    removed = view.chapters[0].blocks[1]
    assert not removed.read
    assert removed.pieces[0].text == "Removed by a step."


def test_a_span_outside_its_block_is_refused() -> None:
    document = make_document([("paragraph", "Short.")])
    with pytest.raises(PlayerError) as caught:
        build_view(document, record(chunks=1), readalong([(0, 0, 60)]))
    assert caught.value.key == "listen.mismatch"
    with pytest.raises(PlayerError):
        build_view(document, record(chunks=1), readalong([(4, 0, 1)]))


def test_line_breaks_show_as_spaces_and_hyphenated_words_join() -> None:
    assert shown("exam-\nple and\nmore") == "exam-ple and more"
    assert shown("exam-\nple and\nmore", joined=frozenset({4})) == "example and more"
    assert (
        shown("exam-\nple", 0, 5, frozenset({4})) + shown("exam-\nple", 5, None, {4}) == "example"
    )


def test_a_word_the_hyphen_step_joined_shows_joined_and_a_kept_hyphen_as_printed() -> None:
    """#286: the read-along shows what the line-end-hyphens step decided, as the voice reads
    it ("contributing"), and keeps a hyphen the step kept ("COVID-19"), also when a
    sentence's piece ends between the hyphen and the line break."""
    text = "asking questions, and con-\ntributing code during COVID-\n19."
    document = make_document([("paragraph", text)])
    cut = text.index("-") + 1  # one piece ends right after the joined word's hyphen
    data = readalong([(0, 0, cut), (0, cut, len(text))])
    view = build_view(document, record(chunks=2), data)
    pieces = [p.text for p in view.chapters[0].blocks[0].pieces]
    assert pieces == ["asking questions, and con", "tributing code during COVID-19."]
    assert joined_hyphens(document, frozenset()) == {0: frozenset({text.index("-")})}
    # characters and hyphenation switched off: the voice read it as printed, and so it shows
    off = build_view(document, record(chunks=2, switched_off=frozenset({"characters"})), data)
    assert "".join(p.text for p in off.chapters[0].blocks[0].pieces) == (
        "asking questions, and con-tributing code during COVID-19."
    )


@pytest.mark.parametrize(
    "text",
    [
        "See https://www.data-\nbase.org/x for more.",
        "See www.mypack-\nage.org for more.",
        "Code at github.com/foo/sea-\nborn today.",
    ],
)
def test_a_hyphen_in_a_link_at_a_line_end_shows_as_printed(text: str) -> None:
    """Review M1 of #290: the links step wins over the join, so the voice never joined it
    and the address shows with its printed hyphen."""
    document = make_document([("paragraph", text)])
    view = build_view(document, record(chunks=1), readalong([(0, 0, len(text))]))
    assert view.chapters[0].blocks[0].pieces[0].text == text.replace("-\n", "-")
    assert joined_hyphens(document, frozenset()) == {}


def test_a_join_inside_a_removed_reference_list_is_not_shown_as_joined() -> None:
    """Review M1 of #290: the reference-list step removes the whole block first, so the
    line-end-hyphens join there is set aside and the text shows as printed."""
    document = make_document(
        [("heading", "References"), ("paragraph", "Doe, J. (2020). A con-\ntributing study.")],
        sections=(Section("References", 1, 0, 2),),
    )
    assert joined_hyphens(document, frozenset()) == {}


@st.composite
def blocks_and_spans(draw: st.DrawFn) -> tuple[Document, list[tuple[int, int, int]]]:
    words = st.text(alphabet="ab -.\n", min_size=1, max_size=30).filter(
        lambda t: t.strip() and not t.startswith("\n")
    )
    texts = draw(st.lists(words, min_size=1, max_size=5))
    spans = []
    for number, text in enumerate(texts):
        cuts = sorted(draw(st.sets(st.integers(0, len(text)), max_size=6)))
        for start, end in itertools.pairwise(cuts):
            spans.append((number, start, end))
        if draw(st.booleans()):
            at = draw(st.integers(0, len(text)))
            spans.append((number, at, at))
    spans.sort(key=lambda s: (s[0], s[1], s[2]))
    if not spans:
        spans = [(0, 0, 0)]
    return make_document([("paragraph", t) for t in texts]), spans


@given(blocks_and_spans())
def test_nothing_is_lost_or_doubled_and_every_chunk_has_one_element(
    case: tuple[Document, list[tuple[int, int, int]]],
) -> None:
    document, spans = case
    view = build_view(document, record(chunks=len(spans)), readalong(spans))
    shown_blocks = view.chapters[0].blocks
    joined = joined_hyphens(document, frozenset())
    assert ["".join(p.text for p in b.pieces) for b in shown_blocks] == [
        shown(b.text, joined=joined.get(n, frozenset())) for n, b in enumerate(document.blocks)
    ]
    ids = {p.element for b in shown_blocks for p in b.pieces if p.element}
    ids |= {b.element for b in shown_blocks if b.element}
    assert all(chunk[3] in ids for chunk in view.chunks)
    for number, (block, start, end) in enumerate(spans):
        if start < end:
            piece = next(p for b in shown_blocks for p in b.pieces if p.element == f"s{number}")
            text = document.blocks[block].text
            assert piece.text == shown(text, start, end, joined.get(block, frozenset()))


def test_bare_names() -> None:
    for good in ("Book.m4b", "Book - 01 Intro.mp3", "a..b.mp3"):
        assert bare_name(good)
    for bad in ("", ".", "..", "../x.mp3", "a/b.mp3", "a\\b.mp3", "C:x.mp3", "x\x00.mp3", None, 3):
        assert not bare_name(bad)


# ---- the routes, after a real audio job --------------------------------------------------

pytestmark = pytest.mark.usefixtures("offline")


def server(tmp_path: Path, voice: FakeVoice | None = None) -> tuple[Any, Any]:
    voice = voice or FakeVoice()
    config = make_config(tmp_path)
    app = create_app(config, voice=lambda models_dir: voice.source())
    return program(app, config), config


def make(
    client: Any, data: bytes = b"", name: str = "paper.pdf", **settings: Any
) -> dict[str, Any]:
    doc = upload(client, data or paper_bytes(), name)
    body = {"kind": "audio", "document": doc["id"], "settings": settings}
    job = client.post("/api/v1/jobs", json=body).json()
    final = json.loads(events(client, job["id"])[-1][1])
    return {"doc": doc, "job": final}


def player_data(page: str) -> dict[str, Any]:
    found = re.search(
        r'<script id="player-data" type="application/json">(.*?)</script>', page, re.S
    )
    assert found is not None
    return json.loads(found[1])


def work_of(config: Any, document: str) -> Path:
    return config.work_root / document


def test_the_listen_page_after_an_audio_job(tmp_path: Path) -> None:
    client, _config = server(tmp_path)
    made = make(client)
    assert made["job"]["state"] == "done", made["job"]
    doc = made["doc"]["id"]
    page = client.get(f"/documents/{doc}/listen")
    assert page.status_code == 200
    text = page.text
    assert "Listen: paper.pdf" in text
    assert "read by a synthetic voice (Heart)" in text
    assert 'Not in this audiobook: <span lang="en">References</span>' in text
    assert '<script src="/static/player.js" defer></script>' in text
    data = player_data(text)
    assert data["mode"] == "mp3"
    assert [c["title"] for c in data["chapters"]] == ["Introduction", "Methods"]
    for start, end, chapter, element in data["chunks"]:
        assert f'id="{element}"' in text
        assert start <= end
        assert chapter in (0, 1)
    sentence = (
        r'<span class="s" id="s\d+" data-chunk="\d+">Things happen \(Smith, 2020\) and more\.'
    )
    assert re.search(sentence + "</span>", text)
    # the other pages link here
    assert f'href="/documents/{doc}/listen"' in client.get(f"/documents/{doc}").text
    assert f'href="/documents/{doc}/listen"' in client.get("/").text
    assert f'href="/documents/{doc}/listen"' in client.get(f"/jobs/{made['job']['id']}").text


def test_the_audiobook_route_serves_only_its_own_files(tmp_path: Path) -> None:
    client, config = server(tmp_path)
    made = make(client)
    doc = made["doc"]["id"]
    base = f"/api/v1/documents/{doc}/audiobook"
    names = [f["name"] for f in made["job"]["files"]]
    for name in names:
        answer = client.get(f"{base}/{name}")
        assert answer.status_code == 200, name
        assert answer.content == (config.output_folder / name).read_bytes()
    mp3 = next(n for n in names if n.endswith(".mp3"))
    assert client.get(f"{base}/{mp3}").headers["content-type"] == "audio/mpeg"
    part = client.get(f"{base}/{mp3}", headers={"Range": "bytes=0-9"})
    assert part.status_code == 206
    assert len(part.content) == 10
    saved = client.get(f"{base}/{mp3}?download=true")
    assert saved.headers["content-disposition"].startswith("attachment")
    (config.output_folder / "other.mp3").write_bytes(b"x")
    for wrong in ("other.mp3", "..%2Fsettings.json", "%2E%2E", "audio.json", "document.json"):
        assert client.get(f"{base}/{wrong}").status_code == 404, wrong
    assert client.get(f"/api/v1/documents/0123456789abcdef/audiobook/{mp3}").status_code == 404
    other = make(client, make_pdf([Text("Another one.", 72, 100)]), "other.pdf")
    assert client.get(f"/api/v1/documents/{other['doc']['id']}/audiobook/{mp3}").status_code == 404
    (config.output_folder / mp3).unlink()
    assert client.get(f"{base}/{mp3}").status_code == 404


def test_the_record_finds_a_folder_the_saved_settings_dont_name(tmp_path: Path) -> None:
    client, config = server(tmp_path)
    elsewhere = tmp_path / "elsewhere"
    made = make(client, output_folder=str(elsewhere))
    doc = made["doc"]["id"]
    record_file = work_of(config, doc) / player.RECORD
    stored = json.loads(record_file.read_text(encoding="utf-8"))
    assert stored == {
        "format": "sci2audio-web-audiobook",
        "version": 1,
        "document": doc,
        "folder": str(elsewhere.absolute()),
    }
    assert client.get(f"/documents/{doc}/listen").text.count('class="s"') > 0
    record_file.unlink()  # without it, the saved and the default folder hold nothing
    page = client.get(f"/documents/{doc}/listen").text
    assert "The audiobook files are no longer in" in page
    assert "player-data" not in page


@pytest.mark.parametrize(
    "change",
    [
        {"folder": "relative/folder"},
        {"document": "0123456789abcdef"},
        {"format": "something-else"},
        {"version": 2},
        {"folder": 42},
    ],
)
def test_a_record_that_is_not_ours_is_ignored(tmp_path: Path, change: dict[str, Any]) -> None:
    client, config = server(tmp_path)
    elsewhere = tmp_path / "elsewhere"
    made = make(client, output_folder=str(elsewhere))
    doc = made["doc"]["id"]
    record_file = work_of(config, doc) / player.RECORD
    stored = json.loads(record_file.read_text(encoding="utf-8"))
    record_file.write_text(json.dumps({**stored, **change}), encoding="utf-8")
    assert "The audiobook files are no longer in" in client.get(f"/documents/{doc}/listen").text


def test_files_of_another_audiobook_under_the_same_names_are_refused(tmp_path: Path) -> None:
    client, config = server(tmp_path)
    made = make(client)
    doc = made["doc"]["id"]
    names = {f["name"] for f in made["job"]["files"]}
    readalong_name = next(n for n in names if n.endswith(".readalong.json"))
    path = config.output_folder / readalong_name
    data = json.loads(path.read_text(encoding="utf-8"))
    data["duration"] += 5
    path.write_text(json.dumps(data), encoding="utf-8")
    page = client.get(f"/documents/{doc}/listen").text
    assert "now belong to another audiobook" in page
    mp3 = next(n for n in names if n.endswith(".mp3"))
    assert client.get(f"/api/v1/documents/{doc}/audiobook/{mp3}").status_code == 404


def test_a_read_along_that_does_not_fit_the_document_is_refused(tmp_path: Path) -> None:
    client, config = server(tmp_path)
    made = make(client)
    doc = made["doc"]["id"]
    name = next(f["name"] for f in made["job"]["files"] if f["name"].endswith(".readalong.json"))
    path = config.output_folder / name
    data = json.loads(path.read_text(encoding="utf-8"))
    data["chunks"][0]["end_char"] = 10_000
    path.write_text(json.dumps(data), encoding="utf-8")
    assert "does not fit this document" in client.get(f"/documents/{doc}/listen").text


def test_a_record_of_another_file_is_refused(tmp_path: Path) -> None:
    client, config = server(tmp_path)
    doc = make(client)["doc"]["id"]
    audio = work_of(config, doc) / "audio.json"
    data = json.loads(audio.read_text(encoding="utf-8"))
    data["source"]["sha256"] = "f" * 64
    audio.write_text(json.dumps(data), encoding="utf-8")
    assert (
        "The record of this audiobook can&#39;t be read"
        in client.get(f"/documents/{doc}/listen").text
    )


@pytest.mark.parametrize("name", ["../escape.mp3", "sub/x.mp3", "C:x.mp3"])
def test_file_names_with_a_folder_part_are_refused(tmp_path: Path, name: str) -> None:
    client, config = server(tmp_path)
    doc = make(client)["doc"]["id"]
    audio = work_of(config, doc) / "audio.json"
    data = json.loads(audio.read_text(encoding="utf-8"))
    data["files"]["mp3"][0] = name
    audio.write_text(json.dumps(data), encoding="utf-8")
    assert (
        "The record of this audiobook can&#39;t be read"
        in client.get(f"/documents/{doc}/listen").text
    )


@pytest.mark.skipif(sys.platform == "win32", reason="symbolic links need extra rights")
def test_a_link_out_of_the_folder_is_not_followed(tmp_path: Path) -> None:
    client, config = server(tmp_path)
    made = make(client)
    doc = made["doc"]["id"]
    mp3 = next(f["name"] for f in made["job"]["files"] if f["name"].endswith(".mp3"))
    secret = tmp_path / "secret.mp3"
    secret.write_bytes(b"not yours")
    (config.output_folder / mp3).unlink()
    os.symlink(secret, config.output_folder / mp3)
    assert client.get(f"/api/v1/documents/{doc}/audiobook/{mp3}").status_code == 404
    assert "no longer in" in client.get(f"/documents/{doc}/listen").text


def test_no_audiobook_yet(tmp_path: Path) -> None:
    client, _ = server(tmp_path)
    doc = upload(client, paper_bytes(), "paper.pdf")
    page = client.get(f"/documents/{doc['id']}/listen")
    assert page.status_code == 200
    assert "There is no audiobook of this document yet." in page.text
    assert "player.js" not in page.text
    assert client.get("/documents/0123456789abcdef/listen").status_code == 404


def test_a_failed_job_writes_no_record(tmp_path: Path) -> None:
    voice = FakeVoice()
    voice.fail_to_make = EngineError("broken")
    client, config = server(tmp_path, voice)
    made = make(client)
    assert made["job"]["state"] == "failed"
    assert not (work_of(config, made["doc"]["id"]) / player.RECORD).exists()


def test_a_full_disk_while_noting_the_folder_leaves_the_job_done(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def full(*args: object) -> None:
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(tasks, "write_record", full)
    client, config = server(tmp_path)
    made = make(client)
    assert made["job"]["state"] == "done"
    doc = made["doc"]["id"]
    assert not (work_of(config, doc) / player.RECORD).exists()
    # the default output folder is the fallback (D-295)
    assert "player-data" in client.get(f"/documents/{doc}/listen").text


def test_text_from_the_file_is_escaped(tmp_path: Path) -> None:
    client, _ = server(tmp_path)
    made = make(
        client, make_pdf([Text("Bold <script>alert(1)</script> claims.", 72, 100)]), "x.pdf"
    )
    page = client.get(f"/documents/{made['doc']['id']}/listen").text
    assert "<script>alert(1)" not in page
    assert "&lt;script&gt;alert(1)" in page


def test_the_readalong_file_is_read_once_per_version(tmp_path: Path) -> None:
    path = tmp_path / "Book.readalong.json"
    path.write_text(to_json(readalong([(0, 0, 1)])), encoding="utf-8")
    first = player.load_readalong(path)
    assert player.load_readalong(path) is first
    path.write_text(to_json(readalong([(0, 0, 1), (0, 1, 2)])), encoding="utf-8")
    os.utime(path, ns=(1, 1))
    assert len(player.load_readalong(path).chunks) == 2


def test_a_broken_document_record_is_named(tmp_path: Path) -> None:
    client, config = server(tmp_path)
    doc = make(client)["doc"]["id"]
    (work_of(config, doc) / "document.json").write_text("{", encoding="utf-8")
    assert (
        "The record of this audiobook can&#39;t be read"
        in client.get(f"/documents/{doc}/listen").text
    )
