"""Cover images for the audiobook files (#73, OU-01, D-313).

An EPUB gives the cover it declares, if that is a JPEG or PNG of at most 20 MB; a PDF gives
its first page rendered as a PNG, 1400 pixels on the longer side. Anything else gives no
cover and never an error: a missing cover never stops a job.
"""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

import pytest
from epub_maker import Item, make_epub
from pdf_maker import Text, make_pdf

from sci2audio.extraction import Cover, extract_epub_cover, extract_pdf_cover
from sci2audio.extraction import epub as epub_module
from sci2audio.extraction.cover import media_type, png

pytestmark = pytest.mark.timeout(60)

CORPUS = Path(__file__).resolve().parents[1] / "corpus"
BROKEN = Path(__file__).resolve().parents[1] / "fixtures" / "broken"
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 60
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
