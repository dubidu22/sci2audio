"""Cover images for the audiobook files (#73, OU-01, D-313).

An EPUB gives the cover it declares, if that is a JPEG or PNG of at most 20 MB; a PDF gives
its first page rendered as a PNG, 1400 pixels on the longer side. Anything else gives no
cover and never an error: a missing cover never stops a job.
"""

from __future__ import annotations

import struct
import zlib
from collections.abc import Callable
from pathlib import Path

import pytest
from epub_maker import Book, Item, make_epub, pack, xhtml
from hypothesis import given, settings
from hypothesis import strategies as st
from pdf_maker import Text, make_pdf

from sci2audio.extraction import Cover, extract_epub_cover, extract_pdf_cover
from sci2audio.extraction import cover as cover_module
from sci2audio.extraction import epub as epub_module
from sci2audio.extraction.cover import media_type, pixel_size, png

pytestmark = pytest.mark.timeout(60)

CORPUS = Path(__file__).resolve().parents[1] / "corpus"
BROKEN = Path(__file__).resolve().parents[1] / "fixtures" / "broken"


def jpeg(width: int, height: int, frame: int = 0xC0, before: bytes = b"") -> bytes:
    """The header of a JPEG: start, an APP0 segment, `before`, and a frame header (SOF)
    of type `frame` for 3 components; no image data, which no test here decodes."""
    app0 = b"\xff\xe0" + struct.pack(">H", 16) + b"JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    sof = struct.pack(">BBHBHHB", 0xFF, frame, 17, 8, height, width, 3) + b"\x01\x11\x00" * 3
    return b"\xff\xd8" + app0 + before + sof + b"\xff\xd9"


def png_header(width: int, height: int, depth: int = 8, kind: int = 2) -> bytes:
    """A PNG that is all header: IHDR, an empty IDAT and IEND (no decoder runs on it)."""
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, depth, kind, 0, 0, 0))
        + _chunk(b"IDAT", zlib.compress(b""))
        + _chunk(b"IEND", b"")
    )


def _chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))


JPEG = jpeg(1, 1)
PNG = png(1, 1, b"\x00\x00\x00", 3)
GIF = b"GIF89a" + b"\x00" * 30


def chunks(data: bytes) -> list[tuple[bytes, bytes]]:
    """The chunks of a PNG, each checked against its CRC."""
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    out, at = [], 8
    while at < len(data):
        (size,) = struct.unpack(">I", data[at : at + 4])
        kind, body = data[at + 4 : at + 8], data[at + 8 : at + 8 + size]
        (crc,) = struct.unpack(">I", data[at + 8 + size : at + 12 + size])
        assert crc == zlib.crc32(kind + body) & 0xFFFFFFFF
        out.append((kind, body))
        at += 12 + size
    return out


def test_png_writes_rows_as_given() -> None:
    # two rows of two pixels, with two bytes of padding at the end of each row
    pixels = bytes([255, 0, 0, 0, 255, 0, 9, 9, 0, 0, 255, 255, 255, 255, 9, 9])
    data = png(2, 2, pixels, stride=8)
    found = chunks(data)
    assert [kind for kind, _ in found] == [b"IHDR", b"IDAT", b"IEND"]
    assert struct.unpack(">IIBBBBB", found[0][1]) == (2, 2, 8, 2, 0, 0, 0)
    rows = zlib.decompress(found[1][1])
    assert rows == b"\x00" + pixels[:6] + b"\x00" + pixels[8:14]


@pytest.mark.parametrize(("width", "height", "stride"), [(0, 1, 3), (2, 2, 5), (2, 3, 6)])
def test_png_refuses_pixels_that_do_not_fit(width: int, height: int, stride: int) -> None:
    with pytest.raises(ValueError, match="do not fit"):
        png(width, height, bytes(12), stride)


def test_media_type_comes_from_the_bytes() -> None:
    assert (media_type(JPEG), media_type(PNG), media_type(GIF), media_type(b"")) == (
        "image/jpeg",
        "image/png",
        None,
        None,
    )
    assert media_type(b"\xff\xd8\x00" + JPEG[3:]) is None  # all three signature bytes
    assert media_type(PNG[:7] + b"\x00" + PNG[8:]) is None
    assert Cover(JPEG, "image/jpeg").suffix == ".jpg"
    assert Cover(PNG, "image/png").suffix == ".png"
    with pytest.raises(ValueError, match="JPEG or PNG"):
        Cover(GIF, "image/gif")
    with pytest.raises(ValueError, match="JPEG or PNG"):
        Cover(PNG, "image/jpeg")  # the label must match the bytes


# ---- PDF -----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("paper", "size"),
    [("acl2023-hardt-ellipsis.pdf", (990, 1400)), ("joss2021-waskom-seaborn.pdf", (990, 1400))],
)
def test_a_pdf_cover_is_its_first_page(paper: str, size: tuple[int, int]) -> None:
    cover = extract_pdf_cover(CORPUS / "papers" / paper)
    assert cover is not None
    assert cover.media_type == "image/png"
    header = chunks(cover.data)[0][1]
    assert struct.unpack(">II", header[:8]) == size


def test_a_page_of_another_size_is_1400_pixels_on_its_longer_side(tmp_path: Path) -> None:
    path = tmp_path / "small.pdf"
    path.write_bytes(make_pdf([Text("Small", 50, 60)]))  # 600 x 800 points
    cover = extract_pdf_cover(path)
    assert cover is not None
    assert struct.unpack(">II", chunks(cover.data)[0][1][:8]) == (1050, 1400)


@pytest.mark.parametrize(
    "data",
    [
        pytest.param(None, id="missing"),
        pytest.param(b"", id="empty"),
        pytest.param(b"not a pdf", id="not-a-pdf"),
        pytest.param((BROKEN / "password-protected.pdf").read_bytes(), id="password"),
    ],
)
def test_an_unreadable_pdf_gives_no_cover(tmp_path: Path, data: bytes | None) -> None:
    path = tmp_path / "broken.pdf"
    if data is not None:
        path.write_bytes(data)
    assert extract_pdf_cover(path) is None


# ---- EPUB ----------------------------------------------------------------------------------


def epub_with(
    tmp_path: Path,
    image: bytes,
    *,
    properties: str = "cover-image",
    metadata: str = "",
    media: str = "image/jpeg",
) -> Path:
    items = [Item("cover", "images/cover.img", media, properties, content=image, in_spine=False)]
    path = tmp_path / "book.epub"
    path.write_bytes(
        make_epub(
            "<p>x</p>",
            items=items,
            metadata="<dc:title>T</dc:title>" + metadata,
        )
    )
    return path


def test_an_epub_3_cover_image() -> None:
    cover = extract_epub_cover(CORPUS / "epub" / "wells-the-time-machine.epub")
    assert cover is not None
    assert cover.media_type == "image/jpeg"


def test_an_epub_2_cover_meta(tmp_path: Path) -> None:
    path = epub_with(tmp_path, PNG, properties="", metadata='<meta name="cover" content="cover"/>')
    assert extract_epub_cover(path) == Cover(PNG, "image/png")


def test_the_bytes_decide_not_the_manifest(tmp_path: Path) -> None:
    path = epub_with(tmp_path, PNG, media="image/jpeg")
    assert extract_epub_cover(path) == Cover(PNG, "image/png")


@pytest.mark.parametrize(
    ("image", "properties", "metadata"),
    [
        pytest.param(GIF, "cover-image", "", id="gif"),
        pytest.param(JPEG, "", "", id="not-declared"),
        pytest.param(JPEG, "", '<meta name="cover" content="nope"/>', id="meta-names-nothing"),
    ],
)
def test_no_usable_declared_cover_gives_none(
    tmp_path: Path, image: bytes, properties: str, metadata: str
) -> None:
    path = epub_with(tmp_path, image, properties=properties, metadata=metadata)
    assert extract_epub_cover(path) is None


def test_a_cover_over_the_limit_gives_none(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(epub_module, "MAX_COVER", 10)
    assert extract_epub_cover(epub_with(tmp_path, JPEG)) is None


# ---- pixel size (#165, D-579) ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("data", "size"),
    [
        pytest.param(png_header(2560, 1600), (2560, 1600), id="png"),
        pytest.param(png_header(16_000, 16_000, 16, 6), (16_000, 16_000), id="png-16-bit-rgba"),
        pytest.param(PNG, (1, 1), id="png-made-by-png"),
        pytest.param(jpeg(2560, 1600), (2560, 1600), id="jpeg-baseline"),
        pytest.param(jpeg(640, 480, 0xC2), (640, 480), id="jpeg-progressive"),
        pytest.param(jpeg(7, 9, 0xCF), (7, 9), id="jpeg-lossless-arithmetic"),
        pytest.param(
            jpeg(30, 20, before=b"\xff\xc4" + struct.pack(">H", 5) + b"abc"),
            (30, 20),
            id="jpeg-huffman-table-is-not-a-frame",
        ),
        pytest.param(
            jpeg(30, 20, before=b"\xff\xcc" + struct.pack(">H", 6) + b"abcd"),
            (30, 20),
            id="jpeg-arithmetic-table-is-not-a-frame",
        ),
        pytest.param(jpeg(30, 20, before=b"\xff\xff\xff"), (30, 20), id="jpeg-fill-bytes"),
        pytest.param(jpeg(30, 20)[:-8], None, id="jpeg-frame-header-cut-off"),
        pytest.param(jpeg(30, 0), None, id="jpeg-height-defined-later"),
        pytest.param(b"\xff\xd8\xff\xda\x00\x02\xff\xd9", None, id="jpeg-scan-before-a-frame"),
        pytest.param(b"\xff\xd8\xff\xe0\x00\x00" + b"\x00" * 60, None, id="jpeg-bad-length"),
        pytest.param(png_header(0, 5), None, id="png-zero-width"),
        pytest.param(png_header(5, 5)[:20], None, id="png-truncated"),
        pytest.param(GIF, None, id="gif"),
    ],
)
def test_the_pixel_size_comes_from_the_header(data: bytes, size: tuple[int, int] | None) -> None:
    assert pixel_size(data) == size


@given(st.binary(max_size=200))
def test_any_bytes_give_a_size_or_none(data: bytes) -> None:
    for start in (b"", b"\xff\xd8", b"\x89PNG\r\n\x1a\n\x00\x00\x00\x0dIHDR"):
        size = pixel_size(start + data)
        assert size is None or (size[0] > 0 and size[1] > 0)


@pytest.mark.parametrize("make", [png_header, jpeg, lambda w, h: jpeg(w, h, 0xC2)])
@pytest.mark.parametrize(
    ("width", "height", "kept"),
    [
        (2560, 1600, True),  # the largest store size
        (10_000, 2_500, True),  # at both limits
        (10_001, 100, False),  # a side over 10,000
        (100, 10_001, False),
        (6_000, 5_000, False),  # 30 megapixels
        (5_001, 5_000, False),  # just over 25 megapixels
    ],
)
def test_a_cover_of_too_many_pixels_is_no_cover(
    tmp_path: Path, make: Callable[[int, int], bytes], width: int, height: int, kept: bool
) -> None:
    """A 2 MB PNG can ask ffmpeg for 2 GB per run that opens it (#165)."""
    image = make(width, height)
    assert (extract_epub_cover(epub_with(tmp_path, image)) is not None) is kept


def test_a_cover_whose_size_cannot_be_read_is_no_cover(tmp_path: Path) -> None:
    assert extract_epub_cover(epub_with(tmp_path, jpeg(30, 20)[:-8])) is None
    assert extract_epub_cover(epub_with(tmp_path, b"\xff\xd8\xff\xe0" + b"\x00" * 60)) is None


def test_the_pixel_limits_are_the_decided_ones() -> None:
    assert (cover_module.MAX_COVER_PIXELS, cover_module.MAX_COVER_SIDE) == (25_000_000, 10_000)


def test_a_declared_cover_missing_from_the_zip_gives_none(tmp_path: Path) -> None:
    items = [Item("c", "cover.jpg", "image/jpeg", "cover-image", content=None, in_spine=False)]
    path = tmp_path / "book.epub"
    path.write_bytes(make_epub("<p>x</p>", items=items))
    assert extract_epub_cover(path) is None


@pytest.mark.parametrize(
    "data",
    [
        pytest.param(None, id="missing"),
        pytest.param(b"", id="empty"),
        pytest.param(b"not a zip", id="not-a-zip"),
        pytest.param(
            make_epub("<p>x</p>", extra_files={"META-INF/rights.xml": "<rights/>"}), id="drm"
        ),
    ],
)
def test_an_unreadable_epub_gives_no_cover(tmp_path: Path, data: bytes | None) -> None:
    path = tmp_path / "broken.epub"
    if data is not None:
        path.write_bytes(data)
    assert extract_epub_cover(path) is None


def test_a_cover_whose_address_cannot_be_parsed_gives_none(tmp_path: Path) -> None:
    items = [Item("c", "http://[x", "image/jpeg", "cover-image", content=None, in_spine=False)]
    path = tmp_path / "book.epub"
    path.write_bytes(make_epub("<p>x</p>", items=items))
    assert extract_epub_cover(path) is None


def cover_outcome(folder: Path, data: bytes) -> Cover | None:
    """`extract_epub_cover` on `data`; any exception fails the test (D-313: never raises)."""
    path = folder / "book.epub"
    path.write_bytes(data)
    return extract_epub_cover(path)


@settings(deadline=None)
@given(st.binary(max_size=2000))
def test_any_bytes_give_a_cover_or_none(
    tmp_path_factory: pytest.TempPathFactory, data: bytes
) -> None:
    cover_outcome(tmp_path_factory.mktemp("any"), data)


COVERED = Book(
    items=[
        Item("c1", "c1.xhtml", content=xhtml("<p>x</p>")),
        Item("cover", "cover.jpg", "image/jpeg", "cover-image", content=JPEG, in_spine=False),
    ]
)
PACKAGES = st.sampled_from(
    [
        COVERED.package(),
        COVERED.package().replace('href="cover.jpg"', 'href="http://[x"'),
        COVERED.package().replace('properties="cover-image"', ""),
    ]
)


@settings(deadline=None)
@given(
    PACKAGES,
    st.lists(
        st.tuples(st.integers(0, 2000), st.text(alphabet="<>&;/=\"' ab#:[\x00", max_size=6)),
        max_size=8,
    ),
)
def test_a_damaged_package_gives_a_cover_or_none(
    tmp_path_factory: pytest.TempPathFactory, package: str, inserts: list[tuple[int, str]]
) -> None:
    for position, piece in sorted(inserts, reverse=True):
        at = min(position, len(package))
        package = package[:at] + piece + package[at:]
    files = dict(COVERED.files(), **{"OEBPS/content.opf": package})
    cover = cover_outcome(tmp_path_factory.mktemp("damaged"), pack(files))
    assert cover is None or cover == Cover(JPEG, "image/jpeg")
