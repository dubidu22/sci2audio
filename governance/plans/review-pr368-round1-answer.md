# PR #368, answer to review round 1 (D-633)

New head: 697ca15. It holds the fix commit on a merge of main 0e830ee into 0919637, with no force-push. Every item is fixed in this PR and nothing is deferred.

- **S1, fixed:** `_AFTER_PUNKT` is now `\d Punkt \Z`: a digit must stand before "Punkt", as in the numbers step's own reading.
  - "Der Punkt 3. Mai war gut.", "Im Punkt 2. Teil steht es." and "Die Note war 2. Punkt 3. Platz." read their ordinals as on main.
  - Unit rows are in `test_german_ranges_and_dotted_numbers_read_the_same_on_a_second_run` (3 fail on 0919637). Two rows are also in `de-numbers-no-ordinal-after-punkt`.
- **S2, fixed:** `Wording.label_point` and `_LABEL_POINT` are removed. The notice now reads its label through `numbers_de.label_numbers_read`, which applies `find_numbers_de` to the label after the label word is spelled out. So the notice turns exactly the numbers the caption turns.
  - "Tabelle 2.1a", "Abb. 3.1a", "Abb. S3.1" and "FIG. 3.1" read as their captions do.
- **S3, fixed in this PR (as decided):** the same change reads "Abbildung 1.2-1.4" as "1 Punkt 2 bis 1 Punkt 4" and "Abb. 3,1" as "3 Komma 1" in notice and caption, on both runs.
  - "Abb. 3.1–3.4", "Abb. 3–5" and "Abbildung 1.2 und 1.4" also differed on a second run on main, and now agree.
  - `test_a_german_notice_names_the_figure_as_its_caption_reads` (15 labels) checks notice = caption on the first run and again after `rebuilt_from_script`. 8 of its rows fail on 0919637.
  - `de-notice-dotted-caption-labels` gains figures for "Tabelle 2.1a", "Abb. S3.1", "Abbildung 1.2-1.4" and "Abb. 3,1".
- **N1, done:** the PR table lists the date-range rows. That covers the three-date chain, "1.3. – 11.3.2020", the one-sided em dash and "Zwischen dem …", plus the S3 notice rows. The CHANGELOG line is updated.

Checks on 697ca15:
- Fast suite: 5414 passed, 1 skipped, 0 xfailed.
- ruff, ruff format, lint-imports and deptry are clean.
- All 13 corpus documents are byte-identical to main.
- Nightly seeds 7, 555 and 8080 on German numbers, placeholders and runner are clean.
