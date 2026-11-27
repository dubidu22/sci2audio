# Unreadable PDF text: fonts with no Unicode source (#442)

Some PDFs hold no letters at all, only glyph numbers. A PDF organiser or Acrobat Distiller
can drop a TrueType font's ToUnicode map, and when the embedded font program has no `cmap`
and no `post` table either, nothing in the file says which letter a glyph is. PDFium (and
every other reader) then gives the glyph number as the character: "Das Buch" reads as
`'DV %XFK` (Times New Roman's usual glyph order is the code point minus 29), and Calibri's
glyph numbers read as `'ĞŵĞŝŶǁĞƐĞŶ` ("Gemeinwesen"). Voicing that is 13 minutes of
nonsense on a three-page excerpt.

Extraction records and measures this; it decides nothing (D-63). The app decides what to
do with a document (#442 part B, policy below).

## What extraction records: `Page.unmapped`

`core.Page` has the field `unmapped: int = 0`: how many characters of the page's lines come
from a font with no Unicode source. A character counts when both hold:

1. PDFium found no Unicode for its code (`FPDFText_HasUnicodeMapError`): the font has no
   ToUnicode map, and no encoding or glyph name PDFium knows gives one;
2. its font's embedded program is TrueType or OpenType without a `cmap` and without a `post`
   table.

The share of the page is `unmapped / Page.characters` (`characters` counts the characters of
the page's lines, white space not counted). The field is additive with an empty default:
exports and golden files leave it out at 0, so files made before it read the same, and every
corpus page has 0.

The count belongs to the page as extracted: on every page extraction makes, `unmapped` is at
most `characters` (extraction's tests check it). `core.Page` itself refuses only a negative
count, because a page a later stage builds from some of the lines may keep the count of the
whole page: the notice steps read a caption's label in a small document of the lines it
uses, and on a page with glyph-number text those lines hold fewer characters (#574). Measure
the share on the pages extraction returns, as `legibility` does.

**Narrowed on purpose (D-762).** The issue's criterion AC-442.1 also named "a simple font
with unknown glyph names". Those are not counted: TeX's math fonts (MSAM10, CMEX) and
matplotlib's Type 3 fonts are exactly such fonts, and in the corpus they set symbols and
correct text (4 of 8 papers, 22 to 96 characters each). Garbled text from them, or from any
other font, is what the text check finds.

A font whose program has a `cmap` or `post` table but no ToUnicode map also reads as glyph
numbers in PDFium; it is not counted either, and the text check finds it. Such a program
names its glyphs, so its text could be recovered from those names; that is not done (#618
leaves it to an issue of its own).

**White space and control codes (#618, AC-442.7).** In the usual TrueType glyph order the
digits and `,` `.` `-` `/` `:` `(` `)`, `ü` and `ß` have glyph numbers that PDFium gives as
white space or control codes, and extraction used to drop them (4.9 % of the characters of
the #442 file). A character of a font with no Unicode source whose glyph has ink is now kept:
read as its recognised letter (below), or as U+FFFD and counted in `unmapped`. A glyph
without ink (the space) stays white space, and so does one the font's program does not let
extraction read.

## Letters recognised from glyph shapes: `Page.recovered` (#618, D-789)

For the usual Office fonts, open fonts with the same advance widths exist, and the glyphs
of the embedded program are still in the file, so the letters can be recognised from their
shapes, without OCR. After the last page is read, extraction does this per font, for the
fonts with no Unicode source (`extraction.letters`):

1. **The font program is read** by `extraction.glyphs`, a TrueType reader of our own that
   reads only what drawing needs (`head`, `maxp`, `hhea`, `hmtx`, `loca`, `glyf`; simple and
   composite glyphs) and bounds every count and offset, since the program comes from the
   user's file: at most 16 MB a program, 512 contours, 8,192 points and 64 components a
   glyph, composites 4 deep, every offset inside its table. A glyph past a limit is not
   drawn; a program it cannot read keeps today's text. A damaged program never fails the
   file (fuzz tests in `tests/unit/test_extraction_glyphs.py` and `test_extraction_letters.py`).
   CFF and Type 3 fonts, `/CIDToGIDMap` streams and CJK fonts are not read.
   Those limits bound one glyph; one read of a PDF also has one budget for all its fonts
   (`glyphs.Budget`): 400,000 points parsed and 2,000,000 steps of close calls (below).
   While pages are read, no outline is parsed at all (whether a glyph has ink is read from
   its header), and the checks that cost nothing (steps 3 and 4) come before any glyph is
   drawn. A font the budget runs out on keeps today's text.
2. **Each used glyph is drawn** on a fixed grid over the em (24 × 30 cells from -0.05 to
   1.05 em across and from 1.05 em above to 0.3 em below the baseline), so a drawing keeps
   where it stands: a comma low, an apostrophe high.
3. **The codes must be glyph numbers.** The widths the PDF gives each glyph (PDFium's loose
   box) must agree with the program's own advances of the glyphs with those numbers: at
   least 95 % of at least 8 glyphs (or of all the font uses), and the agreeing glyphs must
   have at least 3 different widths. Otherwise a `/CIDToGIDMap` stream or another encoding
   may stand between code and glyph, and the font is refused. In a monospaced font every
   width is the same, so a shuffled `/CIDToGIDMap` agrees just as well: nothing shows the
   codes are glyph numbers, and a monospaced font (Courier New, a Cousine subset) is
   always refused.
4. **The family and style** is the reference style in which most glyphs find a letter of
   their width, at least 90 % of them; among the styles close to it by that count, the one
   whose letters lie nearest the 64 most used glyphs. The reference drawings are those of
   Tinos, Arimo, Cousine, Caladea and Carlito, the metric-compatible open twins of Times
   New Roman, Arial, Courier New, Cambria and Calibri, in regular, bold, italic and bold
   italic (`extraction/data/letter-shapes.json.gz`, 216 letters each: the printable
   characters of Windows-1252 and the minus sign).
5. **Each glyph gets the nearest letter of its width** (within 1/1000 em; where the ink
   reaches past the advance, the PDF shows only how wide the glyph is at most, and letters
   no wider are candidates), one letter per glyph, nearest pairs first. Two drawings are
   compared after a blur of one cell, each scaled to the same ink: the distance is the share
   of ink that lies elsewhere (0 the same drawing, 1 nothing in common), at most
   `GLYPH_DISTANCE` = 0.35.
6. **Close calls.** Where another letter, or the swap of two glyphs' letters, lies within
   half the best distance of it (`CLOSE_SHARE`, at least `CLOSE_FLOOR` = 0.01), the readings
   that use only the letters English and German use are kept; if more than one is left, the
   one that makes at least 2 more common English and German words, or numbers, among the
   font's words wins (a closed list of 272 words in `extraction.letters`). A close
   call left unsettled leaves its glyphs unrecognised. A test proves the word step on a
   font that draws "e" exactly as "c": with the step patched out, the font is refused.
7. **The font is accepted** only when at least 95 % of its inked glyphs' occurrences are
   recognised (`FONT_SHARE`) at a mean distance of at most 0.2 (`FONT_DISTANCE`).
8. **The pages are read again** with the letters. A font any of whose pages is still
   unreadable by `legibility` is refused, and its pages keep the first read. Refusing a
   font can make another page fail; after two reads again in which a page failed, every
   font left is refused, so a page is read at most three times (`LETTER_ROUNDS`).

A font is also refused when some of its characters are not glyph numbers PDFium failed to
map: PDFium maps some codes itself (glyph numbers in the Arabic, Hebrew or Tamil ranges,
combining marks), with no map error, so they are not counted in `unmapped`. Recognising the
rest would leave a page part recovered letters, part characters nothing counts, which
`legibility` may pass; refused, the page reads and is judged as before. An Office subset's
glyph numbers lie under 258, so its characters are all counted.

A refused font keeps today's text, and part B stops or warns as before (AC-442.6).
Recognition costs nothing for a file without fonts with no Unicode source: no drawing is
loaded and no page read twice (AC-442.10). On a MacBook Pro M4 recognising 2,000 glyphs of
an Office font takes 0.5 s; the worst a hostile program can make of it, glyphs that each
hold one 8,191-point glyph, spends the whole point budget in about 1 s, and a page of 20,000
of them reads in 1.0 s (main: 0.96 s): a few seconds of the 60 s a step of the reader may
take, also on slower machines (`docs/baseline.md`).

`core.Page` has the field `recovered: int = 0`: how many of the page's `unmapped`
characters were read as recognised letters (`0 <= recovered <= unmapped`). Additive with an
empty default like `unmapped`: exports and golden files leave it out at 0.

The recognised text may hold mistakes, so the pages with any recognised letter are named
(`app.readability.recovered_pages`, PDFs only; #618, AC-442.9, #1086), always in the same
warning, `app.readability.recovered_warning`: "The text of page 2 was recognised from the
shapes of its letters: the PDF's fonts give glyph numbers there instead of letters. The
recognised text may hold mistakes." The report lists it after the picture-page warning and
before the rest, and its JSON gets `"recovered_pages": {"pages": [2], "ranges": "2"}` at the
end, only when a page was recognised. `sci2audio script` and `sci2audio convert` print the
same warning on stderr (`sci2audio: warning: …`), after the picture-page one; a document
without such pages prints nothing new. The document page shows it in English or German
in step 1, after the picture-page notice (`document.recovered_pages`).

**How the limits were set.** `scripts/letter_shapes.py measure` draws the 89 letters, digits
and marks of English and German text of fonts on the machine that runs it and compares them
with their twins' (24 Nov 2026, Times New Roman, Arial and Courier New of macOS, every style;
these fonts are only measured, never committed):

| font | twin's letter, mean distance | at most | another letter nearer | within 0.05 |
|---|---|---|---|---|
| Times New Roman | 0.084 | 0.254 | 1 (8 and ß) | 7 |
| Times New Roman Bold | 0.086 | 0.200 | 0 | 9 |
| Times New Roman Italic | 0.168 | 0.416 | 6 (quotes, comma) | 30 |
| Arial | 0.078 | 0.296 | 3 (Q and O, quotes) | 5 |
| Arial Bold | 0.073 | 0.250 | 2 (Q and O, I and l) | 9 |
| Arial Italic | 0.142 | 0.341 | 2 | 16 |
| Courier New | 0.263 | 0.740 | 31 | 64 |

Courier New's drawings differ too much from Cousine's (mean above `FONT_DISTANCE`), and as
a monospaced font it is refused by step 3 in any case. The close-call margin was then set on whole texts: three texts
written for the tests (two German, one English, 270 to 900 characters) set in each of these
seven fonts as a PDF with no Unicode source holds them. With `CLOSE_SHARE` = 0.5 no letter
came out wrong; 12 of the 21 were recognised, with 70 of their 6,100 characters (1.1 %) left
as U+FFFD, mostly digits (no word tells 3 from 5); Times New Roman Italic, Arial Italic on
the German texts, Courier New and the shortest, digit-heavy German text in Times New Roman
were refused. A smaller share (0.35) let Arial Bold read "l" as "I" (their drawings differ by
a few cells), a larger one (0.6, 0.75, 1.0) refused more and got nothing more right. Calibri and
Cambria were not at hand to measure; Carlito, Calibri's twin, is drawn after Lato, so a
Calibri font may be refused where Times New Roman is read. The reference drawings are made by
`scripts/letter_shapes.py shapes` from the pinned ChromeOS releases (SHA-256 in the script;
licences in `THIRD_PARTY_LICENSES.md`), downloading only when a person runs it; the file it
writes is committed, and no font file ships with sci2audio.

## What extraction measures: `extraction.legibility`

`legibility(content)` gives one `PageLegibility` per page, for any `Content` (PDF, EPUB,
Markdown, text). A page is `unreadable` when any of these holds:

| measure | limit | corpus (most) | glyph numbers (least) |
|---|---|---|---|
| characters from fonts with no Unicode source, less those `recovered` | more than `UNMAPPED_SHARE` = 50 % | 0 % | 100 % |
| rare letter pairs, with at least `MIN_PAIRS` = 100 pairs | `RARE_SHARE` = 5 % | 0.93 % | 12.7 % |
| foreign letters, with at least `MIN_LETTERS` = 50 letters | `FOREIGN_SHARE` = 20 % | 1.5 % | |

- **Rare letter pairs:** letter pairs inside words (case-folded, a to z) that English and
  German words hardly ever hold ("savvy" and "XXL" do; the 5 % limit leaves room for them):
  `RARE_PAIRS`, 72 pairs whose first letter is j, q, v, w or x or whose second letter is q
  or x, so no German compound forms them where its words meet. The
  usual TrueType glyph order turns "n" into "q", so text read through it is full of them,
  while it stays plain ASCII that no script check sees. The corpus margins come from a
  leave-one-out count over the corpus (8 papers, the EPUB, the Markdown and text samples)
  and one German paper used only to measure; Colin's #442 file reads 22 to 24 %.
- **Foreign letters:** letters outside Basic Latin, Latin-1, Latin Extended-A and Greek
  (formulas use Greek), with U+FFFD and private-use characters: glyph numbers far from
  Unicode, as Calibri's are, land there (#187's measure).

## What the app does with it (#442 part B, #187; D-762, D-772)

`app.readability.unreadable(content)` turns the measures into the app's verdict, for PDFs only
(D-772: a page is a printed page only there; EPUB, Markdown and text give their own letters):

- **Stop.** When the unreadable pages hold more than half of the document's characters
  (`characters` summed over the unreadable pages, times 2, more than the sum over all pages),
  the audio job stops right after reading, before the voice is checked or made, with
  `UnreadableTextError` (a kind of `UnreadableFileError`: exit code 5 on the command line,
  error kind `unreadable-text` in the interface). Nothing is spoken and no file is written.
- **Warning.** A document with at least one unreadable page below that share is voiced; the
  report warns about it, naming the pages.

The analysis (script job) always runs: it speaks nothing, and its report is where the person
learns why. The report's warning comes first among its warnings, and its JSON gets
`"unreadable": {"pages": [1, 2, 3], "ranges": "1–3", "stops": true}` at the end, only when a
page is unreadable, so the reports of readable documents are as before. The document page
shows the notice in English or German in step 1 (`document.unreadable_stop` or
`document.unreadable_pages`) and, for a stop, blocks "Make the audiobook" with
`make.needs_text`. Pages are named by their number from 1, as a PDF viewer counts,
with runs of three or more as ranges ("1–3, 7").
