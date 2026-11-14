"""A book's cover image, for the audiobook files (OU-01, D-313).

Not part of `Content`: images are not exportable as plain data, and only the app reads the
cover, to hand it to output. Each format has its own function (`extract_pdf_cover`,
`extract_epub_cover`); both give None rather than fail, since a missing cover never stops a
job. An EPUB's own cover is used only if its header gives a size within the pixel limits
(`small_enough`, D-579); the PDF cover is rendered here at a fixed size.
"""

from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass

JPEG = "image/jpeg"
PNG = "image/png"
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_JPEG_SIGNATURE = b"\xff\xd8\xff"
# A cover's size, read from its header (#165, D-579): ffmpeg decodes the whole frame in each
# run that opens the image, and a 2 MB PNG of 16,000 x 16,000 pixels costs it 2 GB. Four
# times the largest store size (2,560 x 1,600); 16-bit RGBA at 25 megapixels is 200 MB.
MAX_COVER_PIXELS = 25_000_000
MAX_COVER_SIDE = 10_000
# JPEG frame headers SOF0 to SOF15; C4 (Huffman tables), C8 (reserved) and CC (arithmetic
# coding conditions) share the range but are not frames
_FRAMES = frozenset(range(0xC0, 0xD0)) - {0xC4, 0xC8, 0xCC}


@dataclass(frozen=True)
class Cover:
    """The cover image's bytes and their media type, JPEG or PNG."""

    data: bytes
    media_type: str

    def __post_init__(self) -> None:
        if self.media_type not in (JPEG, PNG) or media_type(self.data) != self.media_type:
            raise ValueError(f"a cover must be a JPEG or PNG image, got {self.media_type!r}")

    @property
    def suffix(self) -> str:
        """The file suffix for the image: ".jpg" or ".png"."""
        return ".jpg" if self.media_type == JPEG else ".png"


def media_type(data: bytes) -> str | None:
    """JPEG or PNG, from the image's first bytes (a file's own label is not trusted)."""
    if data.startswith(_JPEG_SIGNATURE):
        return JPEG
    if data.startswith(_PNG_SIGNATURE):
        return PNG
    return None


def pixel_size(data: bytes) -> tuple[int, int] | None:
    """Width and height in pixels from a PNG's IHDR chunk or a JPEG's frame header; None if
    the header cannot be read (a decoder could not read the image either) or gives no size."""
    if data.startswith(_PNG_SIGNATURE):
        if data[12:16] != b"IHDR" or len(data) < 24:
            return None
        width, height = struct.unpack(">II", data[16:24])
    elif data.startswith(_JPEG_SIGNATURE):
        size = _jpeg_size(data)
        if size is None:
            return None
        width, height = size
    else:
        return None
    return (width, height) if width and height else None


def _jpeg_size(data: bytes) -> tuple[int, int] | None:
    """The size in the first frame header, walking the segments before it; None at the
    first scan or the end of the image, or where a segment does not fit the data."""
    at = 2  # after the start of image
    while at + 2 <= len(data):
        if data[at] != 0xFF:
            return None
        marker = data[at + 1]
        if marker == 0xFF:  # a fill byte before the marker
            at += 1
            continue
        if marker == 0x01 or 0xD0 <= marker <= 0xD8:  # markers without a segment
            at += 2
            continue
        if marker in (0xD9, 0xDA) or at + 4 > len(data):  # end of image, or a scan
            return None
        (length,) = struct.unpack(">H", data[at + 2 : at + 4])
        if length < 2:
            return None
        if marker in _FRAMES:
            if length < 7 or at + 2 + length > len(data):  # the whole header, or none
                return None
            height, width = struct.unpack(">HH", data[at + 5 : at + 9])
            return width, height
        at += 2 + length
    return None


def small_enough(data: bytes) -> bool:
    """The image's header gives a size within `MAX_COVER_SIDE` and `MAX_COVER_PIXELS`."""
    size = pixel_size(data)
    return (
        size is not None and max(size) <= MAX_COVER_SIDE and size[0] * size[1] <= MAX_COVER_PIXELS
    )


def png(width: int, height: int, pixels: bytes, stride: int) -> bytes:
    """An 8-bit RGB PNG of `height` rows of `width` pixels; each row starts `stride` bytes
    after the one before in `pixels`, as a rendered bitmap stores them."""
    row = 3 * width
    if width < 1 or height < 1 or stride < row or len(pixels) < stride * (height - 1) + row:
        raise ValueError(f"pixels do not fit a {width} x {height} image with stride {stride}")
    raw = b"".join(
        b"\x00" + pixels[y * stride : y * stride + row]  # filter type 0: the row as it is
        for y in range(height)
    )
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)  # 8 bit, RGB
    return (
        _PNG_SIGNATURE
        + _chunk(b"IHDR", header)
        + _chunk(b"IDAT", zlib.compress(raw, 9))
        + (_chunk(b"IEND", b""))
    )


def _chunk(kind: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(kind + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", crc)
