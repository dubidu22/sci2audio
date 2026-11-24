"""Make the reference drawings letter recognition compares glyphs with (#618, D-789).

    uv run python scripts/letter_shapes.py shapes --cache DIR
    uv run python scripts/letter_shapes.py measure FONT.ttf [FONT.ttf ...]
    uv run --with fonttools==4.55.3 python scripts/letter_shapes.py fixtures --cache DIR

`shapes` writes `src/sci2audio/extraction/data/letter-shapes.json.gz`: for each style of
Tinos, Arimo, Cousine, Caladea (Apache-2.0) and Carlito (OFL-1.1), the metric-compatible
open twins of Times New Roman, Arial, Courier New, Cambria and Calibri, each letter's advance
width and its drawing on the em grid of `sci2audio.extraction.glyphs`, drawn by that same
code. The file holds drawings, not the fonts: no font file ships (D-789).

`measure` prints, for fonts of the same metrics (Times New Roman and the like, on the
machine that runs it; never committed), how far each letter's drawing lies from its twin's
and from the nearest other letter of the same width: the margins the thresholds of
`sci2audio.extraction.letters` are pinned from.

`fixtures` writes the Apache-2.0 subsets of Tinos and Arimo the tests build their PDFs from
(`tests/fixtures/fonts/`), with fontTools, which is not a dependency of sci2audio.

This is the only code that downloads the fonts, and only a person runs it: the three
ChromeOS releases below, each checked against its SHA-256 before it is opened. Nothing in
sci2audio or its tests touches the network.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import struct
import sys
import tarfile
import urllib.request
from pathlib import Path

import numpy as np

from sci2audio.extraction import glyphs

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "src" / "sci2audio" / "extraction" / "data" / "letter-shapes.json.gz"
FIXTURES = ROOT / "tests" / "fixtures" / "fonts"
_MIRROR = "https://commondatastorage.googleapis.com/chromeos-localmirror/distfiles/"
RELEASES = {
    "croscorefonts-1.31.0.tar.bz2": (
        "672c3487883ec1ef83d9254240d4327b014212abc823d06d15816095867315e1"
    ),
    "crosextrafonts-20130214.tar.gz": (
        "c48d1c2fd613c9c06c959c34da7b8388059e2408d2bb19845dc3ed35f76e4d09"
    ),
    "crosextrafonts-carlito-20130920.tar.gz": (
        "4bd12b6cbc321c1cf16da76e2c585c925ce956a08067ae6f6c64eff6ccfdaf5a"
    ),
}
FAMILIES = {  # family: (release, twin of)
    "Tinos": ("croscorefonts-1.31.0", "Times New Roman"),
    "Arimo": ("croscorefonts-1.31.0", "Arial"),
    "Cousine": ("croscorefonts-1.31.0", "Courier New"),
    "Caladea": ("crosextrafonts-20130214", "Cambria"),
    "Carlito": ("crosextrafonts-carlito-20130920", "Calibri"),
}
STYLES = ("Regular", "Bold", "Italic", "BoldItalic")
# The letters drawn: the printable characters of Windows-1252 (what an Office document in
# English or German sets), and the minus sign. No space: a glyph without ink is white space.
_CP1252 = {bytes([c]).decode("cp1252", errors="ignore") for c in range(0x80, 0x100)}
LETTERS = "".join(
    sorted({chr(c) for c in range(0x21, 0x7F)} | (_CP1252 - {"", "\u00a0", "\u00ad"}) | {"\u2212"})
)
# The letters, digits and marks of English and German text the thresholds are measured on.
COMMON = (
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.,;:-()/!?'\"%&"
    "\u00e4\u00f6\u00fc\u00c4\u00d6\u00dc\u00df\u201e\u201c\u201d\u2018\u2019\u2013"
)
# What the test subsets hold: printable ASCII with the space, and German's letters and marks.
FIXTURE_TEXT = "".join(chr(c) for c in range(0x20, 0x7F)) + (
    "\u00e4\u00f6\u00fc\u00c4\u00d6\u00dc\u00df\u201e\u201c\u201a\u2018\u2013\u2014\u2026\u20ac"
)


def fonts(cache: Path) -> dict[str, Path]:
    """Each style's font file ("Tinos Regular": path), from the releases, downloaded into
    `cache` if not there yet and checked against their SHA-256."""
    cache.mkdir(parents=True, exist_ok=True)
    for name, digest in RELEASES.items():
        archive = cache / name
        if not archive.exists():
            print(f"downloading {name}", file=sys.stderr)
            with urllib.request.urlopen(_MIRROR + name) as response:  # noqa: S310 (a fixed https URL)
                archive.write_bytes(response.read())
        if hashlib.sha256(archive.read_bytes()).hexdigest() != digest:
            raise SystemExit(f"{name}: not the pinned release (SHA-256 differs)")
        folder = cache / name.split(".tar")[0]
        if not folder.exists():
            with tarfile.open(archive) as tar:
                tar.extractall(cache, filter="data")
    return {
        f"{family} {style}": cache / release / f"{family}-{style}.ttf"
        for family, (release, _) in FAMILIES.items()
        for style in STYLES
    }


def unicode_map(program: bytes) -> dict[int, int]:
    """The program's cmap (format 4 or 12, Windows Unicode): code point to glyph."""
    (count,) = struct.unpack_from(">H", program, 4)
    tables = {}
    for k in range(count):
        tag, _, offset, _length = struct.unpack_from(">4sIII", program, 12 + 16 * k)
        tables[tag] = offset
    cmap = tables[b"cmap"]
    (subtables,) = struct.unpack_from(">H", program, cmap + 2)
    found: dict[int, int] = {}
    for k in range(subtables):
        platform, encoding, offset = struct.unpack_from(">HHI", program, cmap + 4 + 8 * k)
        if (platform, encoding) not in ((3, 1), (3, 10)):
            continue
        at = cmap + offset
        (form,) = struct.unpack_from(">H", program, at)
        if form == 4:
            (segments,) = struct.unpack_from(">H", program, at + 6)
            segments //= 2
            ends = struct.unpack_from(f">{segments}H", program, at + 14)
            starts = struct.unpack_from(f">{segments}H", program, at + 16 + 2 * segments)
            deltas = struct.unpack_from(f">{segments}h", program, at + 16 + 4 * segments)
            ranges_at = at + 16 + 6 * segments
            ranges = struct.unpack_from(f">{segments}H", program, ranges_at)
            for s in range(segments):
                for code in range(starts[s], ends[s] + 1):
                    if ranges[s] == 0:
                        glyph = (code + deltas[s]) & 0xFFFF
                    else:
                        where = ranges_at + 2 * s + ranges[s] + 2 * (code - starts[s])
                        (glyph,) = struct.unpack_from(">H", program, where)
                        glyph = (glyph + deltas[s]) & 0xFFFF if glyph else 0
                    if glyph:
                        found.setdefault(code, glyph)
        elif form == 12:
            (groups,) = struct.unpack_from(">I", program, at + 12)
            for g in range(groups):
                start, end, glyph = struct.unpack_from(">III", program, at + 16 + 12 * g)
                for code in range(start, end + 1):
                    found.setdefault(code, glyph + code - start)
    return found


def style_data(path: Path) -> dict[str, object]:
    """One style's letters, advances (font units) and drawings (one hex digit a cell)."""
    program = path.read_bytes()
    font = glyphs.read_font(program)
    if font is None:
        raise SystemExit(f"{path.name}: not readable by sci2audio.extraction.glyphs")
    codes = unicode_map(program)
    letters, advances, shapes = "", [], []
    for letter in LETTERS:
        glyph = codes.get(ord(letter))
        outline = font.outline(glyph) if glyph else None
        if not outline:  # missing from this font, or no ink
            continue
        letters += letter
        advances.append(font.advance(glyph, shared=True))
        shapes.append("".join(f"{v:x}" for v in glyphs.draw(outline, font.units)))
    return {
        "units": font.units,
        "letters": letters,
        "advances": advances,
        "shapes": "".join(shapes),
    }


def shapes(cache: Path) -> None:
    styles = []
    for name, path in fonts(cache).items():
        data = style_data(path)
        styles.append({"name": name, **data})
        print(f"{name}: {len(data['letters'])} letters", file=sys.stderr)
    document = {
        "about": (
            "Drawings of letters for sci2audio's letter recognition (#618), made by"
            " scripts/letter_shapes.py from Tinos, Arimo, Cousine (croscorefonts 1.31.0,"
            " Apache-2.0), Caladea (crosextrafonts 20130214, Apache-2.0) and Carlito"
            " (crosextrafonts-carlito 20130920, OFL-1.1); see THIRD_PARTY_LICENSES.md."
        ),
        "grid": [glyphs.COLUMNS, glyphs.ROWS, glyphs.LEFT, glyphs.RIGHT, glyphs.TOP, glyphs.BOTTOM],
        "styles": styles,
    }
    text = json.dumps(document, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    DATA.parent.mkdir(exist_ok=True)
    with DATA.open("wb") as out, gzip.GzipFile(fileobj=out, mode="wb", mtime=0, filename="") as z:
        z.write(text.encode("utf-8"))
    print(f"wrote {DATA.relative_to(ROOT)} ({DATA.stat().st_size:,} bytes)", file=sys.stderr)


def measure(paths: list[Path]) -> None:
    """For each font: the reference style recognition would choose for it, and for each of
    its letters (of `COMMON`) the distance to the same letter's drawing there and to the
    nearest other letter of the same width, with the summary the thresholds are set from."""
    from collections import Counter

    from sci2audio.extraction import letters as recognition

    for path in paths:
        program = path.read_bytes()
        font = glyphs.read_font(program)
        if font is None:
            print(f"{path.name}: not readable", file=sys.stderr)
            continue
        codes = unicode_map(program)
        pictures, widths = {}, {}
        for letter in COMMON:
            glyph = codes.get(ord(letter))
            outline = font.outline(glyph) if glyph else None
            advance = font.advance(glyph, shared=True) if glyph else None
            if outline and advance is not None:
                pictures[letter] = glyphs.draw(outline, font.units)
                widths[letter] = 1000 * advance / font.units
        prepared = recognition.prepare(np.stack(list(pictures.values())))
        drawn = dict(zip(pictures, prepared, strict=True))
        keys = {letter: k for k, letter in enumerate(drawn)}
        style = recognition._style(
            {keys[c]: v for c, v in drawn.items()},
            {keys[c]: w for c, w in widths.items()},
            Counter(keys.values()),
        )
        if style is None:
            print(f"{path.name}: no reference style fits")
            continue
        rows = []
        for letter, picture in drawn.items():
            if letter not in style.letters:
                continue
            k = style.letters.index(letter)
            fits = np.abs(style.widths - widths[letter]) <= recognition.WIDTH_TOLERANCE
            fits &= np.array([c in COMMON for c in style.letters])
            found = np.full(len(style.letters), np.inf)
            found[fits] = recognition.distances(picture, style.shapes[fits])
            own = found[k]
            found[k] = np.inf
            other = int(found.argmin())
            rows.append((float(found[other] - own), float(own), letter, style.letters[other]))
        rows.sort()
        owns = np.array([own for _, own, _, _ in rows])
        margins = np.array([margin for margin, _, _, _ in rows])
        print(f"== {path.name}: {style.name}, {len(rows)} letters")
        print(f"   own distance: mean {owns.mean():.3f}, max {owns.max():.3f}")
        print(
            f"   nearer other letter: {(margins < 0).sum()}, within 0.05:"
            f" {(margins < 0.05).sum()}, within 0.1: {(margins < 0.1).sum()}"
        )
        print("   closest:", [(round(m, 3), c, o) for m, _, c, o in rows[:10]])


def fixtures(cache: Path) -> None:
    from fontTools import subset  # only here: not a dependency of sci2audio

    found = fonts(cache)
    FIXTURES.mkdir(parents=True, exist_ok=True)
    for family in ("Tinos", "Arimo", "Cousine"):
        options = subset.Options()
        options.hinting = False
        options.layout_features = []
        options.drop_tables += ["GSUB", "GPOS", "GDEF", "kern", "hdmx", "LTSH", "VDMX", "gasp"]
        options.name_IDs = [0, 1, 2, 3, 4, 5, 6, 13, 14]  # keeps the copyright and licence
        options.notdef_outline = True
        options.glyph_names = False
        font = subset.load_font(str(found[f"{family} Regular"]), options)
        subsetter = subset.Subsetter(options)
        subsetter.populate(text=FIXTURE_TEXT)
        subsetter.subset(font)
        out = FIXTURES / f"{family.lower()}-regular-subset.ttf"
        font.flavor = None
        font.save(str(out))
        print(f"wrote {out.relative_to(ROOT)} ({out.stat().st_size:,} bytes)", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("command", choices=("shapes", "measure", "fixtures"))
    parser.add_argument("fonts", nargs="*", type=Path)
    parser.add_argument("--cache", type=Path, help="where the releases go (shapes, fixtures)")
    args = parser.parse_args()
    if args.command != "measure" and args.cache is None:
        parser.error("--cache is needed to make shapes or fixtures")
    if args.command == "shapes":
        shapes(args.cache)
    elif args.command == "measure":
        measure(args.fonts)
    else:
        fixtures(args.cache)


if __name__ == "__main__":
    main()
