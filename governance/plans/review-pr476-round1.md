# Review PR #476, round 1 (sentence-boundary batch PR 2: flush-right and centred lines, join rule, #454)

Head reviewed: edc2df6, one commit on main 1c45cab. Plan: plans/sentence-boundary-plan.md, PR 2 (D-719). Critical, because layout golden files change.

**Verdict: not approvable yet.** There are three should-fixes, all in `Paragraphs._breaks` and `_inside`:
- one corpus reading is wrong: Liu's date is joined to the affiliation;
- the join rule swallows real paragraph and entry starts that begin in lower case;
- "i." and "a." lists are joined.

Each has a verified fix that leaves the rest of the corpus unchanged.

## What I checked

### Every block the PR changes in the corpus
I dumped the blocks of all 13 corpus files on main and on the PR (`/home/user/probe/p476/dump.py`) and diffed them by kind and text. Only two places change. The 700-odd other golden lines are block numbers moving down.

**1. nowak p1, the link.** `https://github.com/rycolab/` | `prefix-parsing` is now one block.
- **Right.** It is one link broken at a line end.
- On main, the links step dropped the first half and "prefix-parsing" was read aloud as a sentence of its own. Now nothing of the link is read, as for every other bare link line.

**2. liu p1, the centred front matter.** Three blocks are now one.
- **Half right.** On the page (rendered at 110 dpi; pdftotext boxes):
  - the affiliation is two italic lines, x0 81.3 and 152.5, both centred on x ≈ 308;
  - "(Dated: April 5, 2024)" is an upright line under them at the same pitch.
- Joining the affiliation's two lines is right. It is one affiliation cut after "Technologies,", which is the very shape of #454.
- Joining the date to it is not right. The page sets it as a separate item, and the script now reads "…Sydney 2052, Australia (Dated: April 5, 2024)" in one breath. That is a sentence start lost (S1).

**Other front matter.** No other title-page or front-matter block changes.

### The new tests fail on main
I put the PR's `test_layout_paragraphs.py` on main. These four fail on main, as the PR body says:
- motto;
- upper-case motto;
- centred;
- lower-case going on.

The other 40 pass.

### Sentence gate and per-file scores
These are unchanged on edc2df6:
- English natural sets: P 0.9967, R 0.9900;
- German natural sets: P 0.9874, R 0.9916;
- no new and no gone errors.

None of the sentence-set files' blocks change.

### #466 is out of scope
This is correct. #466 is in the plain-text reading (`extraction/text.py` and the plain-text paragraphing), while this PR changes only the PDF row joiner `layout/paragraphs.py`.

### Probes of the join rule
These are synthetic layouts with the test helpers (`/home/user/probe/p476/test_probe476*.py`), run on main and on the PR:

| layout | main | PR |
|---|---|---|
| "a) … / b) … / c) …" short items | 3 items | 3 items (lists.py splits "a)" again) |
| "i. we read … / ii. we listen … / iii. we compare …" | 3 blocks | **1 block** (S3) |
| a paragraph whose last line ends without a stop ("…on our website"), then an **indented** new paragraph "pandas reads the table …" | 2 | **1** (S2) |
| the same without an indent and without extra white | 2 | 1 (only the short line signals the start; this is the plan's accepted risk) |
| author-year references, an entry ending in a link without a stop, then an outdented "van Dijk, T. …" | 2 | **1** (S2) |
| code lines without a caption ("for word in words / if word in stop / continue") | 4 | 1 (note only, see below) |
| a capitalised flush-left poem | 3 | 3 |

## Fix list

### Should-fix

**S1. Liu's date is read on after the affiliation.**
- **The cause.** In centred rows the short-line rule is skipped. That joins line 1 to line 2, which is right, and line 2 to the date, which is wrong.
- **The signal.** On the page, the affiliation is italic and the date is upright.
- **Fix:**
  - In `_breaks`, when `_aligned` finds a shape (flush right or centred), a change between italic and upright rows ends the paragraph, as a change of weight does. A row is italic when most of its letters are in italic runs. (Taking "all runs italic" fails: Liu's first line starts with an upright "1".)
  - I checked this on the PR: Liu becomes affiliation (one block) plus date (its own block). Nowak's link stays one block. No other corpus block changes, and the PR's 44 paragraph tests pass.
- **Tests:**
  - a centred italic affiliation of two lines with an upright date under it gives two paragraphs (fails on edc2df6);
  - the liu golden, and `test_liu_s_list…` back to 52 to 132 (count 133);
  - update the PR body's liu bullet.

**S2. The join rule overrides a real first-line indent and a hanging-indent outdent.**
- **The probes.** An indented paragraph that starts in lower case ("pandas", "iOS", "e.g.") after a line without a stop is swallowed. So is an author-year entry "van Dijk, …" (also "de", "von", "di") after an entry ending in a link.
- **The evidence.** A real first-line indent (the row after it back at the left) is a stronger sign than a lower-case start.
- **Nothing in the corpus needs the override.** With `_goes_on` cancelling only the short-line rule, the corpus blocks are byte-identical to edc2df6 (`mutA.jsonl` = `pr.jsonl`). Only the synthetic poem test fails, because its third line was given an indent.
- **Fix:**
  - The join rule cancels the short-line rule only. Indent and outdent still split unless `_aligned` finds a shape.
  - In `test_a_line_ending_inside_a_sentence_goes_on…`, set the third line at the left.
  - Add the two probes as tests: the indented lower-case paragraph stays apart, and the outdented "van Dijk" entry stays apart.
  - Update the docstrings and the body.
- **Note for the coordinator.** This narrows the plan's wording ("an indent, outdent or short-line break is not taken"). The plan's stated aim, that headings, captions and lists are not joined, is kept.

**S3. "i." and "a." lists are joined.**
- **The cause.** `lists.py` knows "i)", "(i)", "a)" and "(a)" and splits those again, but it does not know "i." or "a.". On main, the short-line rule kept such items apart.
- **Fix.** `_inside` is false when the next row opens with a roman numeral of up to four letters, or a single letter, followed by "." or ")" and a space. The regex is `^(?:[ivxl]{1,4}|[a-z])[.)]\s`. "e.g." and "i.e." do not match, so they still join.
- **Test.** Three short "i. / ii. / iii." rows stay three paragraphs (fails on edc2df6).

### Note (no change needed)
- Code lines set as body text without a caption now join into one block. On main, each line was its own block. Neither reading is good, and code in papers sits in floats, so I leave this alone.

## Round 2
Round 2 checks S1 to S3 and diffs the corpus blocks again. Expected changes against main:
- nowak's link becomes one block;
- liu's two affiliation lines become one block, with the date still separate.

Round 2 also reruns the probes and the sentence gate. If it is the final round, it adds the heavy checks:
- mutation of `layout/paragraphs.py` with `tests/unit/test_layout*.py`;
- nightly seeds;
- the fast suite;
- a three-system run (`ci:full`).
