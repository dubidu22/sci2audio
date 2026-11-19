"""A PDF page's regions and an EPUB's pictures, for the player (#293, D-771): rendered in the
PDF reader's child process, read from the zip under the cover's checks."""

from __future__ import annotations

import struct
import zipfile
import zlib
from pathlib import Path

import pytest
from epub_maker import Item, make_epub, pack
from pdf_maker import Rect, Text, cropped, make_pdf, turned

from sci2audio.core import Box
from sci2audio.extraction import (
    Cover,
    Region,
    extract_epub_picture,
    extract_pdf_regions,
    isolate,
    read_pdf,
)
from sci2audio.extraction import epub as epub_module
from sci2audio.extraction import pdf as pdf_module
from sci2audio.extraction.cover import png
from sci2audio.extraction.pdf import region_scale

pytestmark = pytest.mark.timeout(120)

BROKEN = Path(__file__).resolve().parents[1] / "fixtures" / "broken"
RECT = Rect(100, 200, 300, 260)  # filled black, 200 x 60 points
PAGE = [Text("A figure below.", 100, 600), RECT]


def pixels(image: bytes) -> tuple[int, int, list[bytes]]:
    """Width, height and RGB rows of a PNG that `png` wrote (8-bit RGB, filter 0)."""
    assert image[:8] == b"\x89PNG\r\n\x1a\n"
    width, height = struct.unpack(">II", image[16:24])
    data, at = b"", 8
    while at < len(image):
        (size,) = struct.unpack(">I", image[at : at + 4])
        if image[at + 4 : at + 8] == b"IDAT":
            data += image[at + 8 : at + 8 + size]
        at += 12 + size
    raw = zlib.decompress(data)
    row = 3 * width + 1
    return width, height, [raw[y * row + 1 : (y + 1) * row] for y in range(height)]


def dark_box(image: bytes) -> tuple[int, int, int, int]:
    """The pixel box (x0, y0, x1, y1, exclusive end) of the image's dark pixels."""
    width, _, rows = pixels(image)
    xs, ys = [], []
    for y, row in enumerate(rows):
        for x in range(width):
            if sum(row[3 * x : 3 * x + 3]) < 3 * 64:
                xs.append(x)
                ys.append(y)
    assert xs, "no dark pixel"
    return min(xs), min(ys), max(xs) + 1, max(ys) + 1


def write(tmp_path: Path, data: bytes, name: str = "paper.pdf") -> Path:
    path = tmp_path / name
    path.write_bytes(data)
    return path


def drawing_box(data: bytes) -> Box:
    """Where extraction places the page's one drawing (the rectangle)."""
    (drawing,) = read_pdf(data, "paper.pdf").pages[0].drawings
    return drawing.box


# ---- PDF regions ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "shape",
    [
        pytest.param(lambda d: d, id="upright"),
        pytest.param(lambda d: turned(d, 90), id="turned-90"),
        pytest.param(lambda d: turned(d, 180), id="turned-180"),
        pytest.param(lambda d: turned(d, 270), id="turned-270"),
        pytest.param(lambda d: cropped(d, (50, 50, 550, 750)), id="crop-box-off-origin"),
        pytest.param(
            lambda d: cropped(d, (50, 50, 550, 750), (-100, -100, 700, 900)),
            id="crop-and-media-box-off-origin",
        ),
    ],
)
def test_a_region_is_what_extraction_places_there(tmp_path: Path, shape: object) -> None:
    """The region is cut from the page as shown, in the points `Content` uses: the box
    extraction gives the rectangle, widened by 10 points, holds it 10 points from each
    edge, on every page frame extraction knows (#458, #537, #543)."""
    data = shape(make_pdf(PAGE))  # type: ignore[operator]
    box = drawing_box(data)
    wide = Box(box.x0 - 10, box.y0 - 10, box.x1 + 10, box.y1 + 10)
    (image,) = extract_pdf_regions(write(tmp_path, data), [Region(1, wide, 2.0)])
    assert image is not None
    width, height, _ = pixels(image)
    assert (width, height) == (440, 160)
    x0, y0, x1, y1 = dark_box(image)
    assert [x0, y0, x1, y1] == pytest.approx([20, 20, 420, 140], abs=1)


def test_the_part_off_the_page_is_left_out(tmp_path: Path) -> None:
    data = make_pdf([Text("x", 10, 10), Rect(0, 0, 50, 40)])
    (image,) = extract_pdf_regions(write(tmp_path, data), [Region(1, Box(-30, -30, 60, 50), 1.0)])
    assert image is not None
    assert pixels(image)[:2] == (60, 50)
    assert dark_box(image) == (0, 0, 50, 40)


@pytest.mark.parametrize(
    "region",
    [
        pytest.param(Region(1, Box(700, 100, 800, 200)), id="right-of-the-page"),
        pytest.param(Region(1, Box(100, 900, 200, 1000)), id="below-the-page"),
        pytest.param(Region(1, Box(100, 100, 100.5, 200)), id="under-a-point-wide"),
        pytest.param(Region(2, Box(100, 100, 200, 200)), id="no-such-page"),
        pytest.param(Region(0, Box(100, 100, 200, 200)), id="page-0"),
        pytest.param(Region(1, Box(100, 100, 200, 200), 0.0), id="scale-0"),
        pytest.param(Region(1, Box(100, 100, 200, 200), float("nan")), id="scale-nan"),
    ],
)
def test_a_region_not_on_its_page_gives_none(tmp_path: Path, region: Region) -> None:
    good = Region(1, Box(90, 190, 310, 270), 1.0)
    found = extract_pdf_regions(write(tmp_path, make_pdf(PAGE)), [region, good])
    assert found[0] is None
    assert found[1] is not None  # one bad region does not cost the others


def test_the_scale_is_lowered_to_the_side_and_pixel_limits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    whole = Box(0, 0, 600, 800)
    assert region_scale(whole, 3.0) == pytest.approx(2.5)  # 2,000 px on the longer side
    assert region_scale(Box(0, 0, 1000, 1000), 3.0) == pytest.approx(2.0)  # 4 MP
    assert region_scale(Box(0, 0, 100, 50), 3.0) == 3.0
    assert region_scale(Box(5, 5, 5, 50), 3.0) == 0.0
    # the limits in force here hold in the child too
    monkeypatch.setattr(pdf_module, "REGION_SIDE", 400)
    (image,) = extract_pdf_regions(write(tmp_path, make_pdf(PAGE)), [Region(1, whole, 3.0)])
    assert image is not None
    assert pixels(image)[:2] == (300, 400)
    monkeypatch.setattr(pdf_module, "REGION_SIDE", 2_000)
    monkeypatch.setattr(pdf_module, "REGION_PIXELS", 30_000)
    (image,) = extract_pdf_regions(write(tmp_path, make_pdf(PAGE)), [Region(1, whole, 3.0)])
    assert image is not None
    width, height, _ = pixels(image)
    assert width * height <= 30_000 + width + height  # rounding up on each side


def test_all_regions_come_from_one_child(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    started: list[str] = []
    real = isolate.run

    def counted(*args: object, **kwargs: object) -> object:
        started.append("child")
        return real(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(isolate, "run", counted)
    regions = [Region(1, Box(90, 190, 310, 270), 1.0)] * 5
    found = extract_pdf_regions(write(tmp_path, make_pdf(PAGE)), regions)
    assert started == ["child"]
    assert len(found) == 5
    assert all(found)
    assert extract_pdf_regions(write(tmp_path, make_pdf(PAGE)), []) == []
    assert started == ["child"]  # nothing asked, no child


@pytest.mark.parametrize(
    "data",
    [
        pytest.param(None, id="missing"),
        pytest.param(b"", id="empty"),
        pytest.param(b"not a pdf", id="not-a-pdf"),
        pytest.param((BROKEN / "password-protected.pdf").read_bytes(), id="password"),
    ],
)
def test_an_unreadable_pdf_gives_no_regions(tmp_path: Path, data: bytes | None) -> None:
    path = tmp_path / "broken.pdf"
    if data is not None:
        path.write_bytes(data)
    assert extract_pdf_regions(path, [Region(1, Box(0, 0, 10, 10))] * 2) == [None, None]


@pytest.mark.parametrize(
    "outcome",
    [
        pytest.param(isolate.Stopped("memory", "region 1 of 2"), id="stopped"),
        pytest.param(isolate.NotStarted("no child"), id="not-started"),
        pytest.param(["one"], id="wrong-length"),
    ],
)
def test_a_stopped_child_gives_no_regions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, outcome: object
) -> None:
    def run(*_: object, **__: object) -> object:
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(isolate, "run", run)
    regions = [Region(1, Box(0, 0, 10, 10))] * 2
    assert extract_pdf_regions(write(tmp_path, make_pdf(PAGE)), regions) == [None, None]


def test_the_child_has_the_readers_limits(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The same child as `extract_pdf`: its memory and step limits and its reader slots."""
    seen: dict[str, object] = {}

    def run(target: object, args: tuple[object, ...], **kwargs: object) -> object:
        seen.update(kwargs, target=target, limits=args[1])
        return [None]

    monkeypatch.setattr(isolate, "run", run)
    extract_pdf_regions(write(tmp_path, make_pdf(PAGE)), [Region(1, Box(0, 0, 10, 10))])
    assert seen["memory"] == pdf_module.MAX_MEMORY
    assert seen["step_seconds"] == pdf_module.STEP_SECONDS
    assert seen["readers"] is pdf_module._READERS
    assert set(seen["limits"]) >= {"MAX_PAGES", "REGION_SIDE", "REGION_PIXELS"}  # type: ignore[arg-type]


# ---- EPUB pictures (D-310) ----------------------------------------------------------------------

PNG = png(2, 1, b"\x00\x00\x00\xff\xff\xff", 6)
JPEG = b"\xff\xd8\xff\xe0" + struct.pack(">H", 16) + b"JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
JPEG += struct.pack(">BBHBHHB", 0xFF, 0xC0, 17, 8, 3, 4, 3) + b"\x01\x11\x00" * 3 + b"\xff\xd9"


def book(tmp_path: Path, files: dict[str, bytes]) -> Path:
    items = [
        Item(f"i{n}", name, "image/png", content=data, in_spine=False)
        for n, (name, data) in enumerate(files.items())
    ]
    path = tmp_path / "book.epub"
    path.write_bytes(make_epub("<p>x</p>", items=items, metadata="<dc:title>T</dc:title>"))
    return path


def member(path: Path, name: str) -> str:
    """The zip path of the manifest item `name` (epub_maker puts items under the package
    folder)."""
    with zipfile.ZipFile(path) as archive:
        (found,) = [n for n in archive.namelist() if n.endswith(name)]
    return found


def test_a_picture_is_read_by_its_ref(tmp_path: Path) -> None:
    path = book(tmp_path, {"images/fig1.png": PNG, "images/fig2.jpg": JPEG})
    assert extract_epub_picture(path, member(path, "fig1.png")) == Cover(PNG, "image/png")
    assert extract_epub_picture(path, member(path, "fig2.jpg")) == Cover(JPEG, "image/jpeg")


@pytest.mark.parametrize(
    "ref",
    [
        pytest.param("", id="empty"),
        pytest.param("../images/fig1.png", id="parent"),
        pytest.param("/images/fig1.png", id="absolute"),
        pytest.param("OEBPS/../OEBPS/images/fig1.png", id="not-normalised"),
        pytest.param("https://example.org/fig1.png", id="address"),
        pytest.param("OEBPS/images/nope.png", id="not-a-member"),
        pytest.param("mimetype", id="not-an-image"),
    ],
)
def test_a_ref_that_is_not_a_clean_member_gives_none(tmp_path: Path, ref: str) -> None:
    path = book(tmp_path, {"images/fig1.png": PNG})
    assert member(path, "fig1.png") == "OEBPS/images/fig1.png"
    assert extract_epub_picture(path, ref) is None


@pytest.mark.parametrize(
    "data",
    [
        pytest.param(b"GIF89a" + b"\x00" * 30, id="gif"),
        pytest.param(b'<svg xmlns="http://www.w3.org/2000/svg"><script>x</script></svg>', id="svg"),
        pytest.param(
            b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\x0dIHDR" + struct.pack(">II", 20_000, 20_000),
            id="png-too-many-pixels",
        ),
    ],
)
def test_only_small_jpeg_and_png_pictures_are_given(tmp_path: Path, data: bytes) -> None:
    path = book(tmp_path, {"images/fig": data})
    assert extract_epub_picture(path, member(path, "images/fig")) is None


def test_a_picture_over_the_limit_gives_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Counted as it is unpacked, so a small deflate bomb stops at the limit too."""
    bomb = PNG + b"\x00" * 5_000_000
    path = tmp_path / "bomb.epub"
    path.write_bytes(pack({"OEBPS/images/fig.png": bomb}))
    assert path.stat().st_size < 50_000
    monkeypatch.setattr(epub_module, "MAX_COVER", 1_000_000)
    assert extract_epub_picture(path, "OEBPS/images/fig.png") is None
    monkeypatch.setattr(epub_module, "MAX_COVER", 6_000_000)
    found = extract_epub_picture(path, "OEBPS/images/fig.png")
    assert found is not None
    assert found.data == bomb


@pytest.mark.parametrize(
    "data",
    [
        pytest.param(None, id="missing"),
        pytest.param(b"", id="empty"),
        pytest.param(b"x", id="junk"),
    ],
)
def test_an_unreadable_epub_gives_no_picture(tmp_path: Path, data: bytes | None) -> None:
    path = tmp_path / "book.epub"
    if data is not None:
        path.write_bytes(data)
    assert extract_epub_picture(path, "OEBPS/images/fig.png") is None
