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

**Narrowed on purpose (D-762).** The issue's criterion AC-442.1 also named "a simple font
with unknown glyph names". Those are not counted: TeX's math fonts (MSAM10, CMEX) and
matplotlib's Type 3 fonts are exactly such fonts, and in the corpus they set symbols and
correct text (4 of 8 papers, 22 to 96 characters each). Garbled text from them, or from any
other font, is what the text check finds.

A font whose program has a `cmap` or `post` table but no ToUnicode map also reads as glyph
numbers in PDFium; it is not counted either, and the text check finds it. Such a program
names its glyphs, so its text could be recovered; recovering glyph numbers (#442 part 3) is
a roadmap decision and not done.

## What extraction measures: `extraction.legibility`

`legibility(content)` gives one `PageLegibility` per page, for any `Content` (PDF, EPUB,
Markdown, text). A page is `unreadable` when any of these holds:

| measure | limit | corpus (most) | glyph numbers (least) |
|---|---|---|---|
| characters from fonts with no Unicode source | more than `UNMAPPED_SHARE` = 50 % | 0 % | 100 % |
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

## What the app does with it (#442 part B, batch B7; pinned by D-762)

- Preparing stops before voices, with a notice in English and German naming the pages, when
  unreadable pages hold more than half of the document's characters (`characters` summed
  over the unreadable pages, against all pages). No audio is written.
- A document with at least one unreadable page below that share gets the #187 report
  warning, naming those pages.
