# Plan: sci2audio Issue #48, ACL checklist titles read as headings

Thread "Read ACL checklist titles as headings", 13 Nov 2026. Lane: layout. Critical (golden files change), so this waits for the coordinator's approval. Main at 955fea1.

## 1. What I measured

- On both ACL papers that print the checklist (chi p13, hardt p8) the title "ACL 2023 Responsible NLP Checklist" is block 181 / 119, a PARAGRAPH, style 10.9 pt bold: the style of the numbered subsections ("2.1 …"). That is why the font rules miss it (D-84).
- The page shows what sets it apart: **a rule is drawn under the title across the whole text width** (drawing p13-d1 / p8-d1: x 70.5 to 524.8, 0.8 pt thick, top at y 83.8, inside the bottom of the title line's box, y 71.4 to 85.5; the title text runs x 81.8 to 258.2). Since #58 (D-329 to D-333) that rule already stands in the title's own block as a graphic part (`{p13-d1@34}` in the golden file).
- The lines the issue names as not headings hold no such rule: hardt's "Single Sentence" and "Two Actions" (bold 10.9, p6) hold no graphic at all. The bold table header rows ("Structure Example", "PP-BERT …") are no longer PARAGRAPH blocks: they sit inside TABLE placeholders since layout step 3 PR D1.
- On all seven corpus papers, the only bold or larger short PARAGRAPH blocks that hold any graphic part are the two checklist titles (a thin rule) and biggs' "4,5, Derek Lane" on p1 (ORCID icons, 8 × 8 pt: not thin, and before the first numbered heading). nowak's corpus file has no checklist pages.
- The checklist entries stay paragraphs under the current rules and under the new one: "A For every submission:" ends with a colon, and "B ✓ Did you use …" has no printed number (the ✓ is not a word character), and neither holds a rule.

## 2. Proposed rule: a ruled heading

After the first numbered heading, an **unnumbered heading candidate** (today's `_short`: bold or larger, at most 3 lines and 20 words, at least 2 letters, not ending in `. : ; ,`) whose own block holds **a rule drawn under its last line** is a **level-1 heading** without a printed number.

A rule under the line is a drawing among the block's parts that is:

1. thin: at most `line_width` em high (existing setting, the one graphics uses for "a line");
2. under the line: its top between the middle of the last line's box and `heading_rule_gap` em below that box (new setting, 0.5 em);
3. across the line: it starts no later than the line's text and ends no earlier, within `align` em (existing, 0.3 em);
4. longer than the words: it reaches at least `heading_rule_reach` em past one end of the line's text (new setting, 1.0 em), so an underline of the words themselves (an underlined link) does not count.

The heading still has to pass the existing check that a heading stands over text no larger than the body text. The level is always 1, also after a common title over the appendices (the truth puts chi's checklist at level 1 after "Supplementary Material: Appendices"): a rule across the page starts a part of its own. Numbered headings after it keep whatever appendix shift they had (question 2).

The check reads the block's own graphic parts, placed there by the graphics step (#58, D-90), not the page's drawings. That way a rule a table or figure took is never seen, and the heading rule agrees with where layout already put the rule. `find_headings` runs after `find_graphics` in `build_document`, so the parts are there. The module docstring of `headings.py` gets one paragraph for the rule.

Size: about 40 lines in `layout/headings.py` and `layout/settings.py`, plus about 150 lines of tests.

## 3. Alternatives weighed

| | Signal | Why not chosen |
|---|---|---|
| A (chosen) | A rule drawn under the line, wider than its words | |
| B | The issue's first idea: the line opens a page after the references and appendices, with lettered bold entries ("A For every submission:", "B ✓ …") below it | It fits the ACL checklist's content, not its typography. Layout would need to know where the references end and to parse lettered entries with check marks, and a checklist set in another way would be missed. |
| C | The first text block on its page, bold, unnumbered, after the last numbered heading | Page breaks are accidents of typesetting: a bold label such as hardt's "Two Actions" that happened to open a page would become a heading. |
| D | The page's column count changes (two columns to one) | Too narrow: a checklist printed in two columns would be missed, and a one-column appendix page with a bold label would be caught. |
| E | The title is set 1 em in from the left edge of the text (x 81.8 against 70.9) | A weak signal on its own; indented bold labels are common. |
| F | The PDF outline (#24) | The ACL PDFs carry none (measured for #24). |
| G | The words "ACL" or "Checklist" | Ruled out by the issue's acceptance criteria and by D-84. |

## 4. Expected golden-file changes (measured with a throwaway prototype, not pushed)

On all seven papers, only the two intended blocks change.

- `test_layout_corpus.ambr`
  - chi: block 181 `paragraph` → `heading` (no label). Section tree: "Supplementary Material: Appendices" ends at 181 instead of 229, so do "D More Implementation Details" and "D.3 Software Tools"; a new level-1 section "ACL 2023 Responsible NLP Checklist", blocks 181-229.
  - hardt: block 119 `paragraph` → `heading`. "A Appendix" and "A.2 Substitutions" end at 119 instead of 167; a new level-1 section "ACL 2023 Responsible NLP Checklist", blocks 119-167.
  - nowak, arsiwalla, liu, waskom, biggs: identical.
- `test_app_corpus.ambr` (hardt is one of the two papers with a script and report golden): a new chapter 13 "ACL 2023 Responsible NLP Checklist" (page 8, selected, 73 utterances), so chapter 12 "A Appendix" drops from 99 to 26 utterances. 13 edits on pages 8 and 9 (2 page numbers, the checklist footnote's text and its introduction, 9 "e.g.") now name chapter 13 instead of 12, in the JSON and the Markdown report. The script gets the chapter line "# 13. ACL 2023 Responsible NLP Checklist" before the title. No spoken text changes otherwise.
- `test_app_corpus.py` `CHAPTERS`: chi and hardt each end with "ACL 2023 Responsible NLP Checklist".
- `test_layout_corpus.py` `NOT_YET_HEADINGS`: both entries removed (the dict stays, empty, as the mechanism for future gaps). The corpus heading test then finds 75 of 75 truth headings.
- Every other snapshot (extraction, textprep corpus goldens, CLI goldens) is unchanged. The full fast suite with the prototype: 2768 passed, 1 skipped.

## 5. Tests

- Corpus: the two truth headings found (75 of 75); the golden diffs above, explained in the PR body.
- Unit tests in `tests/unit/test_layout_headings.py`, on made-up pages with a numbered heading first:
  - a bold body-size line with a rule under it across the column is a level-1 heading without a label;
  - the same line without the rule stays a paragraph (the "Single Sentence" case);
  - an underline exactly as wide as the words stays a paragraph (rule 4);
  - a rule more than 0.5 em below the line, a thick bar, and a rule shorter than the line each leave it a paragraph (rules 1 to 3);
  - a ruled line before the first numbered heading (a title framed by rules) is not a heading;
  - a ruled line ending in a colon is not a heading;
  - after a common title over the appendices, a ruled heading is level 1 and a numbered appendix heading after it keeps its shift;
  - a numbered heading with a rule under it keeps its numbered level.
- Mutation check before opening the PR: drop each of the four rule conditions and the "after the first numbered heading" guard in turn; some test must fail each time.
- Spoken-script diff (`sci2audio script … --chapters all --ignore-settings`) on all seven papers, main against the branch: only the new chapter line in chi and hardt.
- The Hypothesis property tests for layout run unchanged.

## 6. Questions (each with my recommendation)

1. **Level of a ruled heading after a common appendix title.** Recommended: always level 1, as the truth has it for chi. Alternative: 1 plus the appendix shift (level 2 in chi), which contradicts the truth.
2. **Does a ruled heading end the appendix shift for numbered headings after it?** Recommended: no, leave the shift as it is. No corpus paper has a numbered heading after the checklist, and a ruled common title over the appendices would otherwise switch its own shift off. Alternative: reset the shift to 0 after a ruled heading.
3. **Only in documents that number their headings, after the first numbered heading?** Recommended: yes for v1.0. Before the first numbered heading a rule more often frames the paper's title (NeurIPS-style rules above and below the title); documents without numbered headings already take their heading styles from repeated larger styles, and no corpus paper needs more there. Alternative: also in unnumbered documents, with the title guarded some other way. I would not file an issue unless a real paper needs it.
4. **The new chapter is selected by default.** Recommended: yes; the truth says the checklist "is read under its title", like the rest of the paper. Alternative: unselected by default like the reference list (a chapter-selection change in `app`, out of scope for #48; it would get its own issue).
5. **Two new settings, `heading_rule_gap` = 0.5 em and `heading_rule_reach` = 1.0 em.** Recommended as stated; the measured values are 0 em (the rule lies inside the line's box) and 1.0 em left / 24 em right. Alternative: no new settings, reusing `paragraph_space` and `short_line` (their meanings differ, which makes later tuning confusing).
6. **Read the rule from the block's own graphic parts (#58, D-90), not from the page's drawings.** Recommended, for the reason in §2. Alternative: search the page's drawings for a rule under the line, independent of the graphics step; it would also see rules a table or figure took.

## 7. Risks and out of scope

- A bold table header row with a wide rule under it that is not inside a TABLE placeholder (a table without a caption that the float walk did not take) could become a heading. Tables with captions are placeholders, so the risk is limited to uncaptioned tables; the "after the first numbered heading" guard and the need for a one-to-three-line block not ending in punctuation narrow it further. None in the corpus.
- No change to extraction, core, the outline rules (D-270 to D-273) or the text steps.
- No KB edits: the coordinator passes the decisions to the daily KB thread.
