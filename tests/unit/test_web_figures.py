"""The figure, table or formula itself in the player (#293, D-771): which blocks show images
and with what alt text, the crop cache in the project data folder, and the route that serves
them under the D-310 checks."""

from __future__ import annotations

import hashlib
import json
import os
import re
import struct
import threading
from contextlib import nullcontext
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from cli_helpers import Cli
from epub_maker import Item, make_epub
from pdf_maker import Rect, Text, make_pdf
from test_web_player import make, server, work_of
from web_helpers import (
    make_config,
    offline,  # noqa: F401 - fixture
    program,
)

from sci2audio.core import Block, BlockKind, Box, Document, Part
from sci2audio.extraction import Region, read_epub, read_pdf
from sci2audio.extraction.cover import png
from sci2audio.layout import build_document
from sci2audio.web import OutsideJob, create_app, figures
from sci2audio.web.figures import (
    CACHE_FOLDER,
    Catalog,
    Figures,
    cache_name,
    images,
    prune,
    read_cached,
    write_cached,
)

pytestmark = [pytest.mark.timeout(120), pytest.mark.usefixtures("offline")]

PNG = png(2, 1, b"\x00\x00\x00\xff\xff\xff", 6)
CHART = Rect(100, 150, 400, 350)
TABLE_RULE = Rect(100, 500, 400, 501)


def figure_pdf(*more: list[Text | Rect]) -> bytes:
    first = [
        Text("Introduction", 72, 80, size=14),
        Text("Things happen and the chart below shows them.", 72, 100, size=11),
        CHART,
        Text("Figure 1: A chart of things.", 100, 370, size=9),
        Text("More text follows the figure here.", 72, 420, size=11),
    ]
    return make_pdf(first, *more)


def figure_epub() -> bytes:
    body = (
        "<h1>One</h1><p>Text before.</p>"
        '<figure><img src="images/fig.png" alt="A chart of things"/>'
        "<figcaption>Figure 1: Things.</figcaption></figure>"
        "<p>Text after.</p><table><tr><td>a</td><td>b</td></tr></table>"
        '<p><img src="images/eq.png" alt=""/></p><p>End.</p>'
    )
    items = [
        Item("f", "images/fig.png", "image/png", content=PNG, in_spine=False),
        Item("e", "images/eq.png", "image/png", content=PNG, in_spine=False),
    ]
    return make_epub(
        body, items=items, metadata="<dc:title>T</dc:title><dc:language>en</dc:language>"
    )


def pdf_document(data: bytes | None = None) -> Document:
    return build_document(read_pdf(data or figure_pdf(), "paper.pdf"))


def kinds(document: Document) -> dict[BlockKind, list[int]]:
    found: dict[BlockKind, list[int]] = {}
    for n, block in enumerate(document.blocks):
        found.setdefault(block.kind, []).append(n)
    return found


# ---- which blocks, which regions, which alt text ---------------------------------------------


def test_a_pdf_figure_is_its_parts_box_with_a_margin_and_its_caption_as_alt() -> None:
    document = pdf_document()
    (figure,) = kinds(document)[BlockKind.FIGURE]
    (shown,) = images(document, figure, "Figure 1 is skipped.")
    assert shown.region == Region(1, Box(96, 146, 404, 354))
    assert shown.alt == "Figure 1: A chart of things."
    assert (shown.width, shown.height) == (round(308 * 4 / 3), round(208 * 4 / 3))
    assert shown.ref == ""


def test_without_a_caption_the_alt_text_is_the_notice() -> None:
    document = pdf_document(make_pdf([Text("Introduction", 72, 80, size=14), CHART]))
    (figure,) = kinds(document)[BlockKind.FIGURE]
    assert [s.alt for s in images(document, figure, "A figure is skipped.")] == [
        "A figure is skipped."
    ]


def test_a_box_is_clipped_to_its_page() -> None:
    document = pdf_document(
        make_pdf([Text("Introduction", 72, 80, size=14), Rect(0, 600, 600, 800)])
    )
    (figure,) = kinds(document)[BlockKind.FIGURE]
    (shown,) = images(document, figure)
    assert shown.region is not None
    assert shown.region.box == Box(0, 596, 600, 800)


def _placeholder(document: Document, kind: BlockKind, items: list[str]) -> Document:
    """`document` with the blocks that hold `items` left out (it has no captions) and one
    block of `kind` made of `items` at its end."""
    blocks = [b for b in document.blocks if not {p.item for p in b.parts} & set(items)]
    assert all(b.describes is None for b in blocks)
    block = Block(kind, "", tuple(Part(item) for item in items))
    return Document(document.content, document.language, (*blocks, block))


def _as(document: Document, index: int, kind: BlockKind) -> Document:
    """`document` with block `index` of another kind."""
    blocks = list(document.blocks)
    blocks[index] = replace(blocks[index], kind=kind)
    return replace(document, blocks=tuple(blocks))


def test_one_image_a_page_at_most_four_in_the_order_the_parts_reach_them() -> None:
    pages = [
        [Text(f"Page {n} says something else.", 72, 80), Rect(100 + 20 * n, 100 + 30 * n, 300, 400)]
        for n in range(6)
    ]
    content = read_pdf(make_pdf(*pages), "paper.pdf")
    base = build_document(content)
    drawings = [page.drawings[0].id for page in content.pages]
    order = [drawings[3], drawings[0], drawings[5], drawings[1], drawings[2], drawings[4]]
    document = _placeholder(base, BlockKind.TABLE, order)
    shown = images(document, len(document.blocks) - 1)
    assert [s.region.page for s in shown if s.region] == [4, 1, 6, 2]
    assert [s.n for s in shown] == [0, 1, 2, 3]


@pytest.mark.parametrize("kind", [BlockKind.FIGURE, BlockKind.TABLE, BlockKind.FORMULA])
def test_every_placeholder_kind_of_a_pdf_shows_its_crop(kind: BlockKind) -> None:
    base = pdf_document()
    (figure,) = kinds(base)[BlockKind.FIGURE]
    (shown,) = images(_as(base, figure, kind), figure)
    assert shown.region == Region(1, Box(96, 146, 404, 354))


def test_code_text_and_out_of_range_blocks_show_nothing() -> None:
    base = pdf_document()
    (figure,) = kinds(base)[BlockKind.FIGURE]
    assert images(_as(base, figure, BlockKind.CODE), figure) == []
    for paragraph in kinds(base)[BlockKind.PARAGRAPH]:
        assert images(base, paragraph) == []
    for index in (-1, len(base.blocks)):
        assert images(base, index) == []


def test_an_epub_figure_shows_its_pictures_and_a_table_keeps_its_text_view() -> None:
    document = build_document(read_epub(figure_epub(), "book.epub"))
    found = kinds(document)
    first, second = found[BlockKind.FIGURE]
    (shown,) = images(document, first, "Figure 1 is skipped.")
    assert (shown.ref, shown.alt, shown.region, shown.width) == (
        "OEBPS/images/fig.png",
        "A chart of things",  # the picture's own alt text first
        None,
        0,
    )
    (plain,) = images(document, second, "A figure is skipped.")
    assert plain.alt == "A figure is skipped."  # no alt, no caption: the notice
    (table,) = found[BlockKind.TABLE]
    assert images(document, table) == []


def test_markdown_and_text_show_nothing() -> None:
    """D-771 Q1: sci2audio keeps the text file only, not the pictures beside it."""
    from sci2audio.extraction import read_markdown

    content = read_markdown(b"# One\n\n![A chart](fig.png)\n\nText.\n", "notes.md")
    document = build_document(content)
    figure = [n for n, b in enumerate(document.blocks) if b.is_placeholder]
    assert figure
    assert all(images(document, n, "x") == [] for n in figure)


def test_a_catalog_answers_for_every_block_from_one_pass() -> None:
    document = pdf_document()
    catalog = Catalog(document)
    assert [catalog.images(n) for n in range(len(document.blocks))] == [
        images(document, n) for n in range(len(document.blocks))
    ]


# ---- the cache -------------------------------------------------------------------------------


def test_a_kept_crop_is_read_back(tmp_path: Path) -> None:
    assert write_cached(tmp_path, "a.png", PNG)
    assert read_cached(tmp_path, "a.png") == PNG
    assert not list((tmp_path / CACHE_FOLDER).glob("*.part"))


def test_the_name_changes_with_what_the_crop_shows() -> None:
    region = Region(1, Box(0, 0, 10, 10))
    names = {
        cache_name("a" * 16, region),
        cache_name("b" * 16, region),
        cache_name("a" * 16, Region(2, Box(0, 0, 10, 10))),
        cache_name("a" * 16, Region(1, Box(0, 0, 10, 11))),
        cache_name("a" * 16, Region(1, Box(0, 0, 10, 10), 2.0)),
    }
    assert len(names) == 5
    assert all(re.fullmatch(r"[0-9a-f]{32}\.png", name) for name in names)


def test_a_project_folder_that_is_gone_is_never_made_again(tmp_path: Path) -> None:
    gone = tmp_path / "project"
    assert not write_cached(gone, "a.png", PNG)
    assert not gone.exists()


@pytest.mark.parametrize("what", ["not-png", "too-large", "folder", "link"])
def test_what_is_not_a_kept_crop_is_not_read(
    tmp_path: Path, what: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    figures_folder = tmp_path / CACHE_FOLDER
    figures_folder.mkdir()
    path = figures_folder / "a.png"
    if what == "not-png":
        path.write_bytes(b"GIF89a")
    elif what == "too-large":
        monkeypatch.setattr(figures, "FILE_LIMIT", 10)
        path.write_bytes(PNG)
    elif what == "folder":
        path.mkdir()
    else:
        outside = tmp_path / "outside.png"
        outside.write_bytes(PNG)
        path.symlink_to(outside)
    assert read_cached(tmp_path, "a.png") is None


def test_a_linked_figures_folder_is_neither_read_nor_written(tmp_path: Path) -> None:
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "a.png").write_bytes(PNG)
    project = tmp_path / "project"
    project.mkdir()
    (project / CACHE_FOLDER).symlink_to(elsewhere, target_is_directory=True)
    assert read_cached(project, "a.png") is None
    assert not write_cached(project, "b.png", PNG)
    assert not (elsewhere / "b.png").exists()


def test_a_failed_write_keeps_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def full(*_: Any) -> None:
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(figures.os, "replace", full)
    assert not write_cached(tmp_path, "a.png", PNG)
    assert list((tmp_path / CACHE_FOLDER).iterdir()) == []


def test_the_oldest_crops_go_first_above_the_cap(tmp_path: Path) -> None:
    folder = tmp_path / CACHE_FOLDER
    folder.mkdir()
    for n in range(5):
        path = folder / f"{n}.png"
        path.write_bytes(b"x" * 100)
        os.utime(path, (1000 + n, 1000 + n))
    (folder / "other.txt").write_bytes(b"y" * 1000)  # not a crop: never counted or removed
    prune(folder, 250)
    assert sorted(p.name for p in folder.iterdir()) == ["3.png", "4.png", "other.txt"]
    prune(folder, 250)
    assert sorted(p.name for p in folder.iterdir()) == ["3.png", "4.png", "other.txt"]


def test_a_write_keeps_the_folder_under_the_cap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(figures, "CACHE_LIMIT", len(PNG) * 2)
    for n in range(4):
        assert write_cached(tmp_path, f"{n}.png", PNG)
        os.utime(tmp_path / CACHE_FOLDER / f"{n}.png", (1000 + n, 1000 + n))
    assert sorted(p.name for p in (tmp_path / CACHE_FOLDER).iterdir()) == ["2.png", "3.png"]


# ---- serving through the route -----------------------------------------------------------------


def _made(
    tmp_path: Path, data: bytes, name: str = "paper.pdf", **settings: Any
) -> tuple[Any, Any, str]:
    client, config = server(tmp_path)
    made = make(client, data, name, **settings)
    assert made["job"]["state"] == "done", made["job"]
    return client, config, made["doc"]["id"]


def _figure_of(config: Any, doc: str, kind: BlockKind = BlockKind.FIGURE) -> int:
    data = json.loads((work_of(config, doc) / "document.json").read_text(encoding="utf-8"))
    return next(n for n, block in enumerate(data["blocks"]) if block["kind"] == str(kind))


def test_a_pdf_figure_is_served_and_kept(tmp_path: Path) -> None:
    client, config, doc = _made(tmp_path, figure_pdf())
    block = _figure_of(config, doc)
    answer = client.get(f"/api/v1/documents/{doc}/figures/{block}/0")
    assert answer.status_code == 200, answer.text
    assert answer.headers["content-type"] == "image/png"
    assert answer.headers["x-content-type-options"] == "nosniff"
    assert answer.headers["cache-control"] == "no-store"  # as every answer (security.py)
    width, height = struct.unpack(">II", answer.content[16:24])
    assert (width, height) == (924, 624)  # 308 x 208 points at 3 pixels a point
    kept = list((work_of(config, doc) / CACHE_FOLDER).glob("*.png"))
    assert [p.read_bytes() for p in kept] == [answer.content]
    assert client.get(f"/api/v1/documents/{doc}/figures/{block}/0").content == answer.content


def test_a_kept_crop_is_served_without_a_child(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, config, doc = _made(tmp_path, figure_pdf())
    block = _figure_of(config, doc)
    first = client.get(f"/api/v1/documents/{doc}/figures/{block}/0").content

    def no_child(*_: Any, **__: Any) -> Any:
        raise AssertionError("rendered again")

    monkeypatch.setattr(figures, "extract_pdf_regions", no_child)
    assert client.get(f"/api/v1/documents/{doc}/figures/{block}/0").content == first


def test_one_child_renders_the_next_figures_too(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pages = [
        [Text(f"Page {n} holds another chart.", 72, 80, size=11), Rect(100, 100 + 40 * n, 400, 350)]
        for n in range(1, 4)
    ]
    client, config, doc = _made(tmp_path, figure_pdf(*pages))
    asked: list[int] = []
    real = figures.extract_pdf_regions

    def counted(path: Path, regions: list[Region]) -> list[bytes | None]:
        asked.append(len(regions))
        return real(path, regions)

    monkeypatch.setattr(figures, "extract_pdf_regions", counted)
    data = json.loads((work_of(config, doc) / "document.json").read_text(encoding="utf-8"))
    blocks = [n for n, b in enumerate(data["blocks"]) if b["kind"] == "figure"]
    assert len(blocks) == 4
    for block in blocks:
        assert client.get(f"/api/v1/documents/{doc}/figures/{block}/0").status_code == 200
    assert asked == [4]


def test_an_epub_picture_is_served_from_the_book(tmp_path: Path) -> None:
    client, config, doc = _made(tmp_path, figure_epub(), "book.epub")
    block = _figure_of(config, doc)
    answer = client.get(f"/api/v1/documents/{doc}/figures/{block}/0")
    assert answer.status_code == 200, answer.text
    assert (answer.headers["content-type"], answer.content) == ("image/png", PNG)
    assert not (work_of(config, doc) / CACHE_FOLDER).exists()  # read from the book each time


def _not_found(client: Any, address: str) -> None:
    answer = client.get(address)
    assert answer.status_code in (404, 422), (address, answer.status_code)


def test_only_a_placeholders_own_images_are_served(tmp_path: Path) -> None:
    client, config, doc = _made(tmp_path, figure_pdf())
    block = _figure_of(config, doc)
    base = f"/api/v1/documents/{doc}/figures"
    for address in (
        f"{base}/{block}/1",  # one image only
        f"{base}/{block}/-1",
        f"{base}/0/0",  # a heading
        f"{base}/{block + 1}/0",  # its caption
        f"{base}/100000/0",
        f"{base}/{block}/x",
        f"{base}/..%2f..%2fsource/0",
        f"/api/v1/documents/0000000000000000/figures/{block}/0",
        f"/api/v1/documents/cli-{doc}/figures/{block}/0",
    ):
        _not_found(client, address)


def test_a_record_naming_another_document_is_not_used(tmp_path: Path) -> None:
    client, config, doc = _made(tmp_path, figure_pdf())
    block = _figure_of(config, doc)
    record = work_of(config, doc) / "document.json"
    data = json.loads(record.read_text(encoding="utf-8"))
    data["content"]["source"]["sha256"] = "f" * 64
    record.write_text(json.dumps(data), encoding="utf-8")
    _not_found(client, f"/api/v1/documents/{doc}/figures/{block}/0")
    record.write_text("[" * 20_000, encoding="utf-8")  # RecursionError, not a 500
    _not_found(client, f"/api/v1/documents/{doc}/figures/{block}/0")


def test_a_markdown_picture_is_not_served(tmp_path: Path) -> None:
    client, config, doc = _made(tmp_path, b"# One\n\n![A chart](fig.png)\n\nText here.\n", "a.md")
    data = json.loads((work_of(config, doc) / "document.json").read_text(encoding="utf-8"))
    placeholders = [n for n, b in enumerate(data["blocks"]) if b["kind"] == "figure"]
    assert placeholders
    for block in placeholders:
        _not_found(client, f"/api/v1/documents/{doc}/figures/{block}/0")


def test_removing_the_project_removes_its_crops(tmp_path: Path) -> None:
    client, config, doc = _made(tmp_path, figure_pdf())
    block = _figure_of(config, doc)
    assert client.get(f"/api/v1/documents/{doc}/figures/{block}/0").status_code == 200
    assert (work_of(config, doc) / CACHE_FOLDER).is_dir()
    answer = client.delete(f"/api/v1/documents/{doc}", params={"keep_audiobook": "true"})
    assert answer.status_code == 200, answer.text
    assert not work_of(config, doc).exists()
    _not_found(client, f"/api/v1/documents/{doc}/figures/{block}/0")
    assert not work_of(config, doc).exists()


def test_a_removal_during_the_render_is_not_undone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The crop is written only while the project is still there (D-356): a project removed
    while its figures were rendered stays removed, with no folder made again."""
    client, config, doc = _made(tmp_path, figure_pdf())
    block = _figure_of(config, doc)
    real = figures.extract_pdf_regions

    def removed_meanwhile(path: Path, regions: list[Region]) -> list[bytes | None]:
        found = real(path, regions)
        answer = client.delete(f"/api/v1/documents/{doc}", params={"keep_audiobook": "true"})
        assert answer.status_code == 200, answer.text
        return found

    monkeypatch.setattr(figures, "extract_pdf_regions", removed_meanwhile)
    client.get(f"/api/v1/documents/{doc}/figures/{block}/0")
    assert not work_of(config, doc).exists()


def test_a_render_that_fails_answers_404_and_keeps_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, config, doc = _made(tmp_path, figure_pdf())
    block = _figure_of(config, doc)
    monkeypatch.setattr(figures, "extract_pdf_regions", lambda path, regions: [None] * len(regions))
    _not_found(client, f"/api/v1/documents/{doc}/figures/{block}/0")
    assert not list((work_of(config, doc)).glob(f"{CACHE_FOLDER}/*.png"))


def test_requests_for_one_document_wait_for_one_render(tmp_path: Path) -> None:
    """Two requests at once: the second waits for the first's child, then reads the crop."""
    document = pdf_document()
    (block,) = kinds(document)[BlockKind.FIGURE]
    source = tmp_path / "source.pdf"
    source.write_bytes(figure_pdf())
    folder = tmp_path / "project"
    folder.mkdir()
    doc = document.content.source.sha256[:16]
    calls: list[int] = []
    gate = threading.Event()
    real = figures.extract_pdf_regions

    def slow(path: Path, regions: list[Region]) -> list[bytes | None]:
        calls.append(len(regions))
        gate.wait(10)
        return real(path, regions)

    class Still:
        def __init__(self) -> None:
            self.folder = folder

        def __enter__(self) -> Still:
            return self

        def __exit__(self, *_: object) -> None:
            return None

    shown = Figures()
    results: list[Any] = []
    original = figures.extract_pdf_regions
    figures.extract_pdf_regions = slow  # type: ignore[assignment]
    try:
        threads = [
            threading.Thread(
                target=lambda: results.append(
                    shown.image(doc, document, block, 0, source, folder, Still)  # type: ignore[arg-type]
                )
            )
            for _ in range(2)
        ]
        for thread in threads:
            thread.start()
        gate.set()
        for thread in threads:
            thread.join(30)
    finally:
        figures.extract_pdf_regions = original  # type: ignore[assignment]
    assert calls == [1]
    assert len(results) == 2
    assert results[0] is not None
    assert results[0] == results[1]


def test_nothing_is_kept_while_a_removal_runs_or_for_another_folder(tmp_path: Path) -> None:
    """The write waits for `unchanged`: while a removal runs it gives None, and a project
    found in another folder (the old root, D-748) is not this one: nothing is kept, even
    though this folder is still there."""
    document = pdf_document()
    (block,) = kinds(document)[BlockKind.FIGURE]
    source = tmp_path / "source.pdf"
    source.write_bytes(figure_pdf())
    folder = tmp_path / "project"
    folder.mkdir()
    doc = document.content.source.sha256[:16]

    class Elsewhere:
        folder = tmp_path / "other"

    for given in (None, Elsewhere()):
        found = Figures().image(
            doc, document, block, 0, source, folder, lambda given=given: nullcontext(given)
        )
        assert found is not None  # still served
        assert not (folder / CACHE_FOLDER).exists()


# ---- the page --------------------------------------------------------------------------------


def test_the_listen_page_shows_the_figure_in_its_notice_box(tmp_path: Path) -> None:
    client, config, doc = _made(tmp_path, figure_pdf())
    block = _figure_of(config, doc)
    page = client.get(f"/documents/{doc}/listen").text
    box = re.search(rf'<div class="block notice s" id="b{block}".*?</div>', page, re.S)
    assert box is not None
    assert (
        f'<img class="figure" src="/api/v1/documents/{doc}/figures/{block}/0"'
        ' alt="Figure 1: A chart of things." width="411" height="277"'
        ' loading="lazy" decoding="async">'
    ) in box[0]
    assert page.count('<img class="figure"') == 1


def test_an_epub_picture_has_no_size_on_the_page(tmp_path: Path) -> None:
    client, config, doc = _made(tmp_path, figure_epub(), "book.epub")
    block = _figure_of(config, doc)
    page = client.get(f"/documents/{doc}/listen").text
    assert (
        f'<img class="figure" src="/api/v1/documents/{doc}/figures/{block}/0"'
        ' alt="A chart of things" loading="lazy" decoding="async">'
    ) in page


def test_a_switched_off_category_shows_no_figure(tmp_path: Path) -> None:
    """A figure read as printed text (its category off) has no notice box, so no image."""
    client, _config, doc = _made(tmp_path, figure_pdf())
    assert '<img class="figure"' in client.get(f"/documents/{doc}/listen").text
    client2, _config2, doc2 = _made(
        tmp_path / "off", figure_pdf(), switched_off=["tables-and-figures"]
    )
    assert '<img class="figure"' not in client2.get(f"/documents/{doc2}/listen").text


def test_a_command_line_job_shows_no_figure(tmp_path: Path) -> None:
    """D-771 Q2: its folders are read-only to the server, so nothing could be kept."""
    cli = Cli(tmp_path / "cli")
    source = tmp_path / "in" / "paper.pdf"
    source.parent.mkdir()
    source.write_bytes(figure_pdf())
    out = tmp_path / "book"
    assert cli("convert", source, "-o", out, "-q").code == 0
    job = OutsideJob(
        document=hashlib.sha256(source.read_bytes()).hexdigest()[:16],
        name=source.name,
        work=cli.work(source).absolute(),
        folder=out.absolute(),
    )
    config = make_config(tmp_path / "server", outside=(job,))
    client = program(create_app(config), config)
    page = client.get(f"/documents/{job.id}/listen")
    assert page.status_code == 200
    assert 'class="block notice s"' in page.text
    assert '<img class="figure"' not in page.text
