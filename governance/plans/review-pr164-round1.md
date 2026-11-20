# Review of PR #164, round 1 (Issue #58, loose rule joins the wrong block)

Head reviewed: a61c8d4 (format commit 2e7ce2e + code), base main f3dba5a. Reviewer thread
"Review loose rule joins PR 164", 13 Nov 2026.

**Verdict: changes needed (one must-fix, two should-fix).** The behaviour matches D-329 to
D-336 and the corpus result is exactly as reported; the must-fix is a speed regression on
long documents.

## What I checked, and what held

- Whole diff against the plan and D-329 to D-336: `_hosts` (one line's box, no slack, per
  group, smallest box, tie by read order), `_stand` (after the line and after graphics
  already there, at the line's end), hosted groups taken out of `_place`, `split_at` keeps
  reading order at a no-separator cut, `formulas._flush` untouched. Module docstring updated.
- Corpus, main f3dba5a against the PR, all 7 papers: every block's kind, label and text are
  unchanged; the order of line ids is unchanged; text at offset holds for every line part.
  Exactly five graphics move: nowak `p1-d7`, `p1-d8` (footnote 2 @272 to footnote 1 @119,
  after `p1-l48`), liu `p1-d97` (@1225 to @1167, after `p1-l96`), biggs `p1-d5`, `p1-d6`
  (@68 to @62, after `p1-l6`). Nothing else moves.
- Format-only commit 2e7ce2e: removing the new `  {...}` field from its golden gives f3dba5a's
  golden byte for byte (111 lines carry the field). The code commit changes only the five
  graphics' lines.
- `sci2audio script --chapters all --ignore-settings` on all 7 papers, main against the PR:
  all 21 files (`.script.txt`, `.report.json`, `.report.md`) byte-identical.
- EPUB corpus book (`wells-the-time-machine.epub`), PR merged with main 586094f against main:
  blocks identical.
- ruff, format, lint-imports (3 kept), deptry: clean. Fast suite: 2290 passed, 19 subtests.
  Nightly Hypothesis profile on `tests/unit/test_layout*.py` and `test_core_properties.py`:
  376 passed. CI on a61c8d4: all checks green on Linux, macOS and Windows.
- Mutants (each run against `tests/unit/test_layout*.py`): caught: no skip past graphics
  already at the line's end; strict `<` in `_holds`; `split_at` back to the first part at a
  cut; hosts switched off; x ignored in `_holds`. Survived: see S1, S2, N1.

## Must fix

**M1. `_hosts` makes graphics placement quadratic in the length of the document.**
`src/sci2audio/layout/graphics.py`, `_hosts`: `read = {part.item: ... for every part of
every block}` is rebuilt for every page, so the work is pages × all parts. Measured on liu
repeated to a long document (ids renamed per page): 180 pages, `build_document` 2.8 s on main
against 3.7 s on the PR; 600 pages, 17.4 s against 36.9 s. A profile at 360 pages puts 5.4 s
of find_graphics' 6.7 s in `_hosts`. Books (EPUB with pictures, long PDFs) are in scope for
v1.0, and #132's round 1 already had to fix a slow step on long input. Fix: build the read
index once per document (for example in `find_graphics`, passed in), or only look a line up
when more than one box holds the group. Please report the same before/after timing on the
fix.

## Should fix

**S1. The "join" check in `_hosts` is untested.** Removing `if actions.get(k) != "join":
continue` passes every test. Without it, a group D-91 already made furniture (a repeated logo)
that lies inside a line's box would be taken out of its running head and moved into that
line's block. Add a test that pins it (for example a repeated mark inside a line box on
`repeat_pages` pages stays a RUNNING_HEAD furniture part).

**S2. The tie rule "on a tie, the line read first" (D-329) is untested.** Changing the tie key
to the line read last passes every test. Add a case with two holding line boxes of the same
size.

## Notes (no change needed)

- N1. The guard `all(p.item not in state.lines for p in rest.parts)` in `_assemble` is never
  false in any test or corpus file (dropping it passes). It is a sensible guard; keep it.
- N2. `split_at` now opens a piece at the last part that starts at the cut. With a line of
  empty text that has a graphic standing in it, the empty line would stay in the piece
  before. No source gives empty lines today (none in the 7 papers), so no change asked.
- `test_an_icon_joins_the_block_before_it` moved its icon out of the line's box: correct,
  since the old place is now the D-329 case, which the new icon test covers.
- Follow-up #163 (a mark inside a line cuts liu paragraphs) has no milestone yet; the
  coordinator decides.
