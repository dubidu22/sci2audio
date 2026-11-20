# Review PR #562 round 1 (#442 part A, critical: core dataclass, lane:infra)

Head reviewed: 55eec0e94f23b563ef893667c2e8365c510c1c6c. Reviewer: B1 review thread (Opus high), 18 Nov 2026.
CI on the head: "CI passed" green; ci:full runs 44396301746 and 44396314426 green on ubuntu, macOS and Windows.
Round 1 of at most 4 (REV-02).

## Verdict: CHANGES REQUESTED (2 must fix)

## Verified

- **Additive core change (C1, for B3 PR 2):** `Page.unmapped: int = 0` is the last field, plus the read-only property `Page.characters`; `to_data` leaves the default out (`to_data(Page(1)) == {"number": 1}`), `from_data` reads old data; the check runs only when `unmapped > 0`. No other core type changes. No golden moves (CI snapshots).
- **AC-442.1 rule (narrowed per D-762):** sfnt directory read is bounded (numTables checked against the data length); per character only after a font is found sourceless. Colin's #442 file (uploads, measured only): 3 pages, unmapped 2152/2152, 2447/2447, 2003/2003, rare-pair share 21.6 to 24 %, all unreadable. Kehren: 0 unmapped, every page readable.
- **AC-442.2:** the fixture's shift-by-29 text is found by letter pairs alone, the "far" order by foreign letters.
- **AC-442.4:** 13 corpus documents, 0 unmapped, none unreadable (test). Corpus extraction speed main vs PR (best of 3): within noise on all 8 papers (arsiwalla 2013 vs 1800 ms).
- **Can `unmapped` exceed `characters` and make `Page()` raise inside extraction?** No: every counted `_Char` is one non-space character that `_text_line` writes into the line text, and nothing normalises run text.
- **False positives beyond the corpus** (pages of 45 lines, `_page` directly): 116 licence pages 0 flagged; 954 man pages 1 (jcmd, `-XX:` options give "xx", 5.2 %); 31,662 /usr/share/doc pages 59 (all Japanese text, foreign letters: right for EN/DE voices); 5,805 Python source pages 7 (encoding tables, locale aliases). English prose: none.
- Commit messages and body: no closing keyword; "Part A of #442" keeps the issue open.
- Hand mutants (plans/b1-review-mut562.py; ROOT = PR worktree; tests `tests/unit/test_extraction_legibility.py tests/unit/test_core_content.py`; clean baseline 70 passed): 6 of 13 killed. Survivors are listed under M2 and N3.

## Findings

**M1 (must fix). The font program is copied for every embedded font on every page, before the map-error check.** `_SourcelessFonts.has` looks the font up (`_sourceless` → `FPDFFont_GetFontData`, a copy of the whole program) the first time it sees a font name on a page, whatever the character; the map error is asked after. The approved plan (section 1.1) says the font is looked up only for a character that has a map error. Cost measured with plans/b1-review-bigfont.py (200 pages, one embedded 6.2 MB TrueType font, all text mapped): main 6509 ms, PR 8026 ms (+23 %); with the fix below 6511 ms. Fonts of Asian scripts are often that size, and the PR's own docstring states the reverse order ("the map error is asked only for a font without one").

Exact fix in `extraction/pdf.py`, `_SourcelessFonts.has`:
```python
if raw.FPDFText_HasUnicodeMapError(textpage, index) != 1:
    return False
sourceless = self._fonts.get(name)
if sourceless is None:
    sourceless = self._fonts[name] = _sourceless(textpage, index)
return sourceless
```
and the class docstring's second paragraph to say so (the font is looked at once per page, and only for a character PDFium could not map). Checked locally: the 17 legibility tests pass, Colin's file still gives 6602 unmapped. Add one test that fails on 55eec0e: reading a page with mapped text only (for example `glyph_number_pdf(GERMAN[:1], to_unicode=True)`) never calls `_sourceless` (monkeypatch it to raise).

**M2 (must fix). Branches of the rule and of the limits that no test reaches** (mutant survives on 55eec0e). Add exactly these tests:
1. `_names_no_glyph` as a table (pure function, bytes built in the test): `\x00\x01\x00\x00` with tables `glyf`, `head` only → True; same plus `cmap` → False; plus `post` → False; `true` and `OTTO` tags without cmap/post → True; `ttcf` → False; numTables 0 → False; directory cut short (numTables 3, 20 bytes) → False; a Type 1 program (`%!PS-AdobeFont`) → False; empty bytes → False. Kills: `count == 0` guard removed, `_SFNT` without `true`/`OTTO`.
2. `PageLegibility.unreadable` at its boundaries, built directly: `unmapped` exactly half of `characters` → readable, one more → unreadable; 99 pairs all rare → readable; 100 pairs with 5 rare → unreadable, with 4 → readable; 49 letters all foreign → readable; 50 letters with 10 foreign → unreadable, 9 → readable. Kills: `>` to `>=` on `UNMAPPED_SHARE`, `>=` to `>` on `MIN_PAIRS`.
3. U+FFFD and private-use characters count as letters and as foreign: a page of 60 private-use characters (U+E000 onward) is unreadable and has `letters == foreign == 60`; same with 60 U+FFFD. Kills: `_broken` without the private-use check, and `or _broken(char)` dropped.

## Notes (no change asked)

- N1 The font cache is keyed by PDFium's font name, not the font handle the plan named. Two embedded fonts with one name and different programs on one page would share an answer; subset tags make this rare (Colin's file: KAMHII+, KAMHKI+, KAMHLI+, KAMICJ+). Fine as is.
- N2 docs/unreadable-pdf-text.md says English and German words "never" hold the rare pairs; "savvy", "XXL", "Jr." do. The 5 % limit absorbs them; wording only.
- N3 Surviving mutants judged equivalent in practice: dropping the embedded check (a non-embedded font gets PDFium's substitute, which has a cmap) and dropping `bool(needed)` (font name lookup failing while the character has a box). No test asked.
