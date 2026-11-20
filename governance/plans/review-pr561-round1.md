# Review PR #561 (#466), round 1

- PR: dubidu22/sci2audio#561 "layout: plain-text title lines and list items are blocks of their own (#466)"
- Head reviewed: 3836204 (383620478442484ad1c8d59f5cbfa21123504943), parent 1797ceb; main is f919d81 (docs only since, no overlap).
- Reviewer: B3 review thread, Opus high, 18 Nov 2026.
- **Verdict: changes requested (2 must-fix, 1 should-fix).**

## Verified

- CI on 3836204: `CI passed` green (runs 44395336519, 44395383435); `tests (ubuntu-latest)`, `tests (macos-latest)`, `tests (windows-latest)` success in run 44395383435 (ci:full).
- Corpus comparison (REV-07): `run_script_job` on all 13 corpus documents, main f919d81 vs 3836204, each with its own `src`. Only the two text samples change (script, report.json, report.md); the scripts show exactly the title/subtitle cut and the two points apart. The other 11 documents are byte-identical.
- Golden moves match the plan (extraction text corpus, tagged corpus 8→10 and 7→9 blocks, layout language). `known-errors.toml`: the four #466 rows go, floors en/de recall 1.000.
- Overlap with #562 (B1, #442 A): disjoint files (#562: `extraction/pdf.py`, `extraction/__init__.py`, `extraction/legibility.py`, `core/content.py`, docs, its own tests; no snapshot). `read_text` builds `Page(...)` with keywords, so #562's defaulted `Page` field is compatible. No merge slot needed (C1 holds).

## Findings

**M1 (must fix). A spaced dash wrapped to a line's start makes a list item in the middle of a sentence.** `_BULLET` takes any line opening with "- ", wherever it stands in the paragraph. Plain text written in ASCII uses " - " as a dash (very common in German), and any hard wrap can put that dash at a line's start. On main the paragraph stays one; on 3836204:

```
('p', 'br')            Teilnehmer hörten die Texte - meist unterwegs
('ul', 'li')           - und beantworteten danach Fragen zum Inhalt
('ul', 'li', 'br')     der Texte.
```

Probe (`plans/b3-review/probe561d.py`, seed 11): German prose with two spaced dash pairs per paragraph, `textwrap.fill` at 60/66/72: **248 of 2000 paragraphs** get a list item mid-sentence (main: 0). The sentence is cut across two blocks, which is the #466 class of error in the other direction.
Required: a "- " / "* " / "• " line inside a paragraph opens an item only where the shape says list, not dash. A rule that passed my prototype (0 of 2000, samples unchanged): a bullet line opens an item when it is the paragraph's first line, or the line before opens or continues an item, or the line before ends in ":". Any equivalent rule is fine. Tests: the shape above stays `p` / `p, br`; the existing bullet tests and both samples keep their items.

**M2 (must fix). One long line makes every line of a hard-wrapped paragraph "short", and a German noun at a line's start then cuts it.** `_title` measures against the paragraph's **longest** line. A hard-wrapped paragraph that holds one long unbreakable token (a URL, a DOI, a path) has a longest line far above the wrap width, so ordinary filled lines fall under `TITLE_SHARE`; rule (b) then cuts before any line starting with a capital, which in German is every noun.
Probe (`plans/b3-review/probe561c.py`, seed 7): German prose with one 86-character URL, wrapped at 60/66/72 (`break_long_words=False`): **350 of 2000 paragraphs** are cut into two (main: 0). Also: `"Die Studie wurde von der\nDeutschen Forschungsgemeinschaft gefördert und lief …"` is cut after "der".
Required: an ordinary filled line of a hard-wrapped paragraph never counts as a title line because of one long token. My prototype (`plans/b3-review/proto.py`) measured `longest` over lines that hold a space (a lone token does not count) and got 0 of 2000 with both samples unchanged; another measure is fine if it passes the same probe. Tests: the URL paragraph shape stays one paragraph.

**S1 (should fix). The new prose property cannot reach either rule.** `test_prose_lines_of_a_paragraph_are_joined` draws only lower-case letters, so rule (b) (next line starts with a capital) and the bullet rule are never exercised; it would not have found M1 or M2. Add a Hypothesis property: words with capitals, spaced " - " dashes and at most one long token, joined and hard-wrapped (`textwrap.fill`, width 40 to 80, `break_long_words=False`), come back as one element (`p`, then `p, br`).

## Notes (no action)

- N1. Lists without a colon lead-in ("We found two things\n- a\n- b") stay joined under the M1 prototype rule, as on main; that is acceptable (no regression) if the author picks that rule.
- N2. Final round (REV-03): after the fix commit I dispatch `mutation.yml` for `sci2audio.extraction.text.x_paragraph_tags* x__items* x__run* x__title*` and the nightly property run on the new head; the author's `ci:full` stays required on the fix head (PR-05), since the fix changes reading rules.

## Answer format

One fix commit; answer each finding as fixed (with the test that fails on 3836204), deferred (issue) or declined (reason), in `plans/answer-pr561-round1.md`.
