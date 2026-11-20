# Answer to the review of PR #561, round 1

Review: `plans/review-pr561-round1.md` (head 3836204). One fix commit on `layout/plain-text-structure-466` (hash in the hand-back message). All three findings fixed; nothing deferred.

## M1 (fixed): a spaced dash at a line's start opened a list item mid-sentence

`extraction/text.py`, `paragraph_tags`: a line with a list marker opens an item only where the shape says list: as the paragraph's first line, right after a line that opens or continues an item (the element being continued is `ul`/`ol`), or after a line ending in a colon. That is the rule the reviewer proposed, applied to bullets **and to the first line of a numbered run** (two dates wrapped to two line starts in a row, "am\n3. Oktober und am\n4. November", would otherwise make a run). The module docstring says so.

- Reviewer's probe `probe561d.py` (seed 11): **0 of 2000** (was 248).
- Tests failing on 3836204: `test_a_spaced_dash_wrapped_to_a_line_s_start_stays_in_its_sentence` (the shape in the report), `test_a_list_after_a_colon_or_another_item_opens_items` (colon lead-in makes items; the same lines after prose without a colon stay wrapped lines), `test_a_numbered_run_after_prose_without_a_colon_stays_in_its_sentence` (dates mid-sentence stay; after "Die Termine:" they are items).
- Existing bullet and numbered tests and both samples keep their items (their lists stand first in their paragraphs, or after a colon in the test).
- N1 accepted: "We found two things\n- a\n- b" stays joined, as on main.

## M2 (fixed): one long token made the filled lines short

`paragraph_tags`: `longest` is the longest line **that holds a space**; a paragraph whose lines all lack one falls back to its longest line. A URL or DOI on a line of its own no longer sets the width.

- Reviewer's probe `probe561c.py` (seed 7): **0 of 2000** (was 350).
- Test failing on 3836204: `test_one_long_token_does_not_make_the_filled_lines_short` (German prose with an 86-character URL, wrapped at 50 with `break_long_words=False`, the URL alone on its line).
- The second example of the report ("Die Studie wurde von der" / "Deutschen Forschungsgemeinschaft …") is cut only when the wrap itself is uneven, that is when "der" ends a line far shorter than the others although "Deutschen" would have fit: that is the title shape by every measure the plan allows, and hand-wrapped text does not do it. With an even wrap (the test above holds this very sentence) it stays one paragraph.

## S1 (fixed): the property could not reach either rule

New Hypothesis test `test_hard_wrapped_prose_with_capitals_dashes_and_a_long_token_is_one_paragraph`: words of 1 to 12 letters (2 to 12 when capitalised), capitalised or lower case, spaced `-` dashes, at most one 86-character URL inserted anywhere, joined after a leading word and hard-wrapped with `textwrap.fill` at width 40 to 80, `break_long_words=False`: the paragraph comes back as `p`, then `p, br`. It fails on 3836204.

## Checks on the fix

- `ruff check`, `ruff format --check`: clean.
- `test_extraction_text.py`: 74 passed; 4 of its new tests fail on 3836204 (the property and the three M1 tests), the M2 test fails there too (run alone).
- Corpus snapshots and `known-errors.toml`: unchanged by the fix (the samples' lists stand first in their paragraphs).
- Hand mutants: the 11 of round 0 plus 5 new ones (the anchor reduced to each two of its three parts, the anchor removed, the space filter of `longest` removed): 16 of 16 killed.
- Fast suite and my own `ci:full` on the fix head: in the hand-back message.
