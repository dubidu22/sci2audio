"""A book's cover image, for the audiobook files (OU-01, D-313).

Not part of `Content`: images are not exportable as plain data, and only the app reads the
cover, to hand it to output. Each format has its own function (`extract_pdf_cover`,
`extract_epub_cover`); both give None rather than fail, since a missing cover never stops a
job.
"""

from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass

JPEG = "image/jpeg"
PNG = "image/png"
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_JPEG_SIGNATURE = b"\xff\xd8\xff"


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
