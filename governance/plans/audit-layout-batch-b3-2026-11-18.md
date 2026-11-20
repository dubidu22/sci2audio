# Light batch audit: layout batch B3 (18 Nov 2026)

Scope (light audit): the merged diff of #558 (c51e846, #529 #535) and #561 (0bbb991, #466) read together, for cross-PR inconsistencies and contract touches only. Main at 0bbb991 (also holds #562, 215405c, B1).

## Result: no cross-PR inconsistency, no contract touch. Two deferred items had no issue; filed #570 and #571.

## Checks

1. **Disjoint paths.** #558 changes the PDF path only (`layout/furniture.py`, `layout/build.py` `_Layout`, `layout/settings.py`). #561 changes the plain-text reader (`extraction/text.py`), which feeds the tagged path: `build_document` sends documents without boxes to `build_tagged` before `_Layout` is built, so `head_labels` and `_left_entries` never see a text file, and the new `ul/ol, li` tags never reach the PDF rules. No shared file, snapshot or regression row between the two PRs.
2. **Shared golden `test_app_corpus.ambr`.** Only #558 moved it (431 `printed_page` values, PrivacyScore). #561 left it unchanged (its corpus comparison showed only the two text samples' own outputs moving). C2 needed no regeneration.
3. **Contracts.** Neither PR touches `sci2audio.core`, the lint-imports layers, the text-step interface or `docs/readalong-format.md`. #558 changes values of an existing report field (`printed_page`), not its shape; saved projects keep their old values until prepared again. #562's additive `Page.unmapped` is untouched by #561's `Page(...)` call (keywords).
4. **Docstrings vs behaviour.** `layout/tagged.py` module docstring (a wrapped line of a text file is tagged `br`; `li` → LIST_ITEM, D-415) still describes #561's output correctly. `extraction/text.py` and `furniture.py` docstrings were updated by the PRs themselves and match the final code (checked in review rounds).
5. **Settings.** `LayoutSettings.contents_rows` (new) sits beside `contents_reach`; no doc lists layout settings, so nothing else to update. `TITLE_SHARE` is a module constant in extraction, named in its docstring, as planned.
6. **Sentence gate.** `known-errors.toml` floors en/de recall 1.000 after #561. B6 (#479) edits the same file next (batch plan: B6 after B3 PR 2); it starts from these floors.

## Deferred items

- #561 "Out of scope": a title line between two prose lines is cut only after it → **#570** (filed, no milestone).
- #561 "Out of scope": list item labels differ between PDF and tagged readers → **#571** (filed, no milestone).
- #558 "Out of scope": one-piece contents rows and the German journal's own contents page are marked "not planned" in the PR (declined with reason, covered by its outline, #456); no issue needed.

## Review figures for the ledger

| PR | rounds | findings | real defects caught | post-merge |
|---|---|---|---|---|
| #558 | 2 | 1 S (tests, from mutation) | 0 code defects; 3 untested behaviours | main green (run 44402524588) |
| #561 | 3 | 2 M + 2 S | 2 code defects (dash → list item 248/2000; long token → paragraph cut 350/2000) | main green (run 44406972892) |

Lesson for layout/text-reader reviews: fuzz structure rules with `textwrap.fill` over realistic prose (spaced dashes, one long token, German capital nouns) on main vs PR; the PR's own Hypothesis strategies drew lower-case text only.
