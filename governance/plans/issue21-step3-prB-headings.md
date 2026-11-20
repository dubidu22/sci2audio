# Issue #21 step 3, PR B: headings and the section tree (design for review)

Branch `layout/headings-21`, built and tested on main plus #46's commits. It opens once #46 is merged, so the branch holds only layout changes.

## Module

`layout/headings.py`, run after paragraphs in `build_document`.

## Rules

**Candidates.** A candidate is a PARAGRAPH block that:
- has at most 3 lines and at most 20 words,
- has at least 2 letters,
- is bold (95% of the letters in the main size are bold) or larger than the body size,
- does not end in `. : ; ,`.

A block's style is (main size, bold).

**Numbered headings.** A printed number (`2`, `2.1`, `A`, `A.1`) gives the depth, and the label is that number. Each depth's style is decided by majority vote. A numbered block in another style is not a heading.

**Unnumbered headings.** An unnumbered block is a level-1 heading in three cases:
- (a) its style equals the depth-1 style;
- (b) its whole text is a usual section name from the new settings tuple `section_names`: Abstract, Summary, Acknowledgements, Acknowledgments, References, Bibliography, Appendix, Appendices (English, for v1.0);
- (c) it comes after the first numbered heading and its style is more prominent than every numbered style. In this case all later headings move one level down, as the truth does for appendices under a common title.

**Numbered or not.** A document counts as numbered only when at least 2 candidates carry a number. Otherwise the heading styles are the larger-than-body styles used at least twice over text that is not larger than body, ranked by prominence.

**Front matter.** Working back from the end, a heading is dropped when the next text block is larger than body and is not itself a heading. This removes the title, author and affiliation lines.

**Sections.** A section runs from its heading to the next heading at the same or a higher level.

## Results

- Sections equal the truth headings (text and level, in order) for **73 of 75**, with no extra headings.
- Heading labels are checked against the numbers in the truth text.
- The 2 misses are the ACL checklist titles, which are bold at body size like the subsection headings and table headers. They go to Issue #48 and are listed in `NOT_YET_HEADINGS`. A test checks that both entries are real truth headings.
- **Golden diff:** exactly 73 blocks change from paragraph to heading. Only kind and label change, which a script verified. Each paper also gets a sections listing.
- **Tests:** 14 synthetic unit cases, plus a Hypothesis property (every section starts at a heading whose lines give its title). The nightly profile passes, and 382 fast tests pass.
- `test_layout_paragraphs.paragraphs()` now counts HEADING blocks as text blocks. Those tests check where blocks break, not what kind they are.

## Open choice

The `section_names` tuple is an English word list. It only widens which styles count for those exact names, and it is passed in through the settings. It is the only way to find arsiwalla's Abstract, which is set smaller than its section headings. The alternative is to accept 72 of 75. **Recommendation:** keep the tuple and record it as a KB decision.
