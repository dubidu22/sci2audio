# Answer to the review of PR #530, round 1

Fix commit: a42b511 on layout/german-pdf-456-459 (one commit, on 91d0b79). Main not merged in (the reviewer merges main at merge time).

| item | what was done |
|---|---|
| F1 | Fixed in `furniture._Page._notes` + new `_own`: the notes stack is collected as before, then rows **at its foot** are given back to the furniture rules while they are one line, alone on its page row (`self.alone`), and either a page number by shape (`_PAGE_NUMBER`) or repeated word for word (`_exact`, numbers kept, D-323) at their height (`head_drift`) on `repeat_pages` pages. The repeat table is built once per document in `find_furniture` and passed to `_Page`. Only trailing rows are trimmed, so a repeated line inside a note (a short "Ibid." row on two pages between other note rows) stays a note line. Test `test_a_small_footer_set_tight_under_the_notes_stays_furniture` (your probe: 7 pt footer at y 747, 8 pt under the notes): fails on 91d0b79, passes now; the footer is a running head on all 4 pages and no note text holds it. A note number alone stays a note: its row also holds its text (`test_footnotes_in_the_bottom_band_are_neither_footers_nor_running_heads` green). |
| F2 | Same rule (page-number shape). Test `test_a_small_page_number_set_tight_under_the_notes_stays_a_page_number` (your probe: 8 pt numbers 55 to 58 at y 747): fails on 91d0b79, passes now; `page_labels` ("55", "56", "57", "58"), no note ends with the number. |
| Fixture change | `journal_page(notes=True)` used the same note text on every page, so its last row ("down to the paper's foot.") stood word for word at one height on all 4 pages, which is exactly a footer by D-323. The note texts now name their page ("Note one of page 2, row 0.", "down to the foot of page 2."); the test's assertions check every page's notes by name. Not a weakening: the case it guards (note numbers "1" and "3" at the same height on several pages, and small note rows in the bottom band) is unchanged. |
| T1 | `test_a_small_line_tight_under_the_notes_away_from_their_rule_is_not_a_note`: a one-off 7 pt "Received 3 May 2017" at x 400, 4 pt under a note row, in the footer band, stays a footer. Kills the mutant without the column check (checked by hand). |
| T2 | `test_a_mark_at_the_start_of_a_longer_line_is_no_hanging_label`: a line whose first run is "1" followed by an italic run in the same line, a piece 20 pt to its right, body prints mark 1: no second note. Kills the mutant without `row[0].text.strip() == text` (a plain one-run line could not, since `_MARK` must match the whole first run). |
| T3 | `test_a_short_rule_in_the_upper_half_shields_no_lines_from_the_furniture_rules`: a short thin rule at y 30 over a small head "Journal of Tests N" at y 34 on 3 pages: the heads stay running heads. Kills the mutant without the lower-half check. |
| T4 | Removed the check: `levels` only holds styles of headings found by `_numbered`/`_unnumbered`, all of which come from `self.short` (bold or larger); outline additions come later. Docstring says so. |
| N1 | Filed #535 (lane:layout, P3, milestone v1.2.x): a page number printed inside the running head line as the page's label. |
| N2 | No action. |
| Mutations | Re-run by hand on a42b511: column check, own-line check, lower-half check, trailing-row trim each fail a test. |
| Corpus | Every block of the 8 corpus papers identical to main 96de4a3 (kind, role, label, text); no golden or snapshot moved, `test_app_corpus.ambr` unchanged. |
| Kehren (with PR B's extraction, measuring only) | 14 running heads, notes labelled 1 to 5 with 2/3 and 4/5 separate, headings Zur Aktualität …, I, II, III, Literatur, Internetquellen. Unchanged from round 0. |
| Fast suite | 7,022 passed, 3 skipped locally (`-n auto`). |
