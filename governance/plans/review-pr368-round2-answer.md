# PR #368, answer to review round 2 (D-636)

New head: d0fb704, one commit on 7936a1c (your merge of main 3fcba56), with no force-push. Both items are fixed and nothing is deferred.

- **S1, fixed:** `_NoticeStep.find` reads the label's numbers only for German and only with `Category.NUMBERS_AND_UNITS not in context.switched_off`, the check `footnotes.py` makes.
  - With the numbers switched off, "Abb. 3.1" and "Abbildung 1.2-1.4" read as printed in notice and caption, as on main, and on both runs.
  - `test_with_the_numbers_switched_off_a_german_notice_keeps_its_label_as_printed`: 2 rows, both fail on 7936a1c.
  - Mutation check: dropping the switch check fails 2 tests.
- **S2, fixed:** `label_numbers_read(label, after)` now reads the label followed by the caption's text after it (`after` is `block.text[len(block.label):]` when the caption starts with its label, else ""), and applies only the candidates that end inside the label.
  - "Tab. 1/2:", "Abb. 3/4:", "Abb. 1/5:", "Abb. 2/3:" and "Abb. 12/13:" keep the fraction in notice and caption.
  - The controls "Abb. 3/4 Verlauf der Werte." and "Abbildung 3/4. Verlauf der Werte." read "3 Viertel" in both.
  - `test_a_german_notice_reads_its_label_in_the_captions_context`: the 5 rows fail on 7936a1c, and the 2 controls pass on both.
  - Every row is checked on the second run too, through `rebuilt_from_script`.
  - `de-notice-dotted-caption-labels` gains the figure "Abb. 3/4: Verlauf der Werte.".
  - Mutation check: reading the label alone again fails 6 tests.

Checks on d0fb704:
- Fast suite: 5423 passed, 1 skipped, 0 xfailed.
- ruff, ruff format, lint-imports and deptry are clean.
- All 13 corpus documents are byte-identical to main.
- Nightly seeds 7, 555 and 8080 on German numbers, placeholders and runner are clean.
- The PR body has the round 2 section, and #370 is out of scope.
