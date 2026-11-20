# PR #377 round 1: answer

New head 5dd8377: fix commit 3f757a8, then main 514dc2f merged in (clean merge; the merge brings only #373's web and app files). No force-push.

## B1: keys count only where the document lists them (fixed)

- `citations.listed_keys(document)` collects every key printed as an entry label at the start of a line, followed by an author. The author is either initials before a surname ("[Knu84] D. Knuth", "[GKL+19] A. Gray") or a surname with its initial ("[EN16] Englehardt, S."). `_Rules` gets this set from `CitationStep.find`.
- `_keys(inside, listed)` returns keys only when every key in the bracket is listed and none is on the look-alike list. Otherwise the bracket stays as printed. The same check applies to the lead-word aside brackets, so "(see [Zz99])" stays.
- The entry needs an author, which goes beyond the review's suggestion. Without it, a sentence that starts with a key ("[MH17] zeigen das.", "[MH17] found it.") listed its own key. Then the second run read "Reference MH17 found it." while the first run kept "[MH17]". The identifier-bracket property test caught this.
- Tests:
  - Regression cases. Every key case now ends with a headed list that prints the keys. The new cases `citations-key-shapes-without-entries-stay` (en) and `de-citations-key-shapes-without-entries-stay` (de) cover [Mn12], [Al13], [EU27], [UK21], [Ctrl12], [AB12] to [AB20], [Ab12, Cd34], an unlisted [MH17], [PM10] even when it is listed, [CO2], [C60] and [GPT4]. Both fail on a578dc0.
  - `test_key_shapes_no_entry_prints_stay`: your nine rows, in en and de, each with a numbered list and with no list (36 cases).
  - `test_key_shapes_an_entry_prints_are_citations`: three of the rows, in en and de, with a matching entry.
  - `test_listed_keys_are_the_entry_labels_at_a_line_start`.
- maass changes exactly as at a578dc0. Its list prints "[EN16] Englehardt, S.; …", so all 10 body keys stay citations. All 13 corpus scripts are identical to a578dc0.

## S1: no trailing last lines (fixed)

`_Run.list()` returns the blocks up to the last entry. A short dated block counts as an entry's last line only if another entry follows it. New: `test_a_short_dated_sentence_after_the_list_is_read` ("We thank all in 2020 for help.", "Received 3 May 2020."). The positive test now expects a final "(2020)." to be read. Liu's blocks 90 and 129 stay in the list.

## S2: a run right after another heading is not unheaded (fixed)

`unheaded_list` remembers whether the run's first entry follows a heading block, with only furniture, footnotes, placeholders or captions between them, and whether that heading names no reference list. Such a run is no list. A heading that is a reference title but has no section, so layout found the heading but not the section, still lets the list go. New tests:
- `test_numbered_entries_right_after_another_heading_have_a_heading`: Notes, Endnotes, Anmerkungen and Appendix B, each with furniture between the heading and the entries.
- `test_an_unheaded_list_after_a_section_s_text_and_after_a_reference_heading_goes`: "Results", then text, then entries is still removed.

## N1: an entry needs an author besides its year (taken)

An entry counts toward the half only if it holds a year and an author (same author pattern as above, `references._ENTRY_AUTHOR`). New tests:
- `test_a_numbered_body_list_with_years_but_no_authors_stays`: "[1] In 2011 we ran step 1 …" to "[6]", with and without a heading.
- `test_an_entry_s_author_is_found`: N. Nagaosa, Y.-G. Choi, J.-i. Inoue, "Fahl, S.", D. Garc´ıa Ovalle.

Liu's list is unchanged: blocks 53 to 133.

## Checks on the new head

- Fast suite: 5690 passed, 1 skipped (after the main merge). ruff, format, lint-imports and deptry are clean.
- Mutants, each caught: no heading check, trailing last lines returned, no author condition, every heading treated as a non-reference heading, no listed-key check, no listed check for aside brackets.
- Token fuzz on main 342a8f5, two variants: the old one (no list) and one with a headed list printing [MH17], [Ho16], [Ma16], [GKL+19], [Fa14a] and [PM10]. Seeds 7 and 555, 10,000 texts each. No text differs on a second run on the branch that does not on main.
- Corpus: all 13 scripts are identical to a578dc0, so they match main 342a8f5 except maass (keys) and Liu (list).
