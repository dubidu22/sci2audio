"""Draws sci2audio's app icon (#215) and writes it in the three systems' formats.

    uv run --with pillow python packaging/icons/make_icons.py

The icon is our own drawing, under sci2audio's licence (GPL-3.0-or-later): a page in the
interface's cobalt (#2340A8) with three lines of text turning into sound waves. The PNG,
ICO and ICNS files beside this script are its output and are committed, so a build needs
no drawing library.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).parent
COBALT = (0x23, 0x40, 0xA8, 255)
PAGE = (255, 255, 255, 255)
INK = (0x1A, 0x30, 0x87, 255)
SIZE = 1024


def draw() -> Image.Image:
    image = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    pen = ImageDraw.Draw(image)
    pen.rounded_rectangle((64, 64, SIZE - 64, SIZE - 64), radius=200, fill=COBALT)
    pen.rounded_rectangle((200, 190, 580, 834), radius=40, fill=PAGE)  # the page
    for row, width in enumerate((280, 240, 280, 180)):  # its lines of text
        y = 300 + row * 120
        pen.rounded_rectangle((250, y, 250 + width, y + 36), radius=18, fill=INK)
    for ring in range(3):  # the sound leaving it
        r = 120 + ring * 90
        box = (560 - r, 512 - r, 560 + r, 512 + r)
        pen.arc(box, start=-40, end=40, fill=PAGE, width=44)
    return image


def main() -> None:
    icon = draw()
    icon.resize((512, 512), Image.LANCZOS).save(HERE / "sci2audio.png")
    icon.save(HERE / "sci2audio.ico", sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])
    icon.save(HERE / "sci2audio.icns")


if __name__ == "__main__":
    main()
