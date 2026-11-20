# Review PR #436, round 2 (textprep batch 2 PR 5: hidden runs, affiliation marks, figure alt text, link language)

Head reviewed: e94cf00. It is fix 0cc4a9e on acde859, with main 7a3b3ec merged in. Round 1: plans/review-pr436-round1.md. Critical.

**Verdict: not approvable yet. There is one blocker (B1) and one should-fix item (S1).** Every round 1 item is fixed. B1 is the rest of round 1's B2: the narrower rule still drops a mass number when the element symbol has two letters. S1 is a guard without a test, which the PR body calls equivalent but which is not. One new leftover is filed as **#445**. A third round is needed, which is within the four rounds a critical PR may take.

## Round 1 items

All rows below were probed through the whole chain twice, against main 7a3b3ec. Every reading is the same on both runs.

- **B1, fixed.** Links and citations now read the text without hidden runs (`hidden_removals`, `read_around`, `edits_around`).
  - All nine rows of round 1 now read as main reads them, or better, in en and de. "Visit https://x.org↗ today." reads "today.", the DOI with a glued page-break marker goes whole, and "As shown [12]13 before." reads "As shown before.".
  - Further rows:
    - "Shown in [1, 13 2]" with a page-break marker inside reads "references 1 and 2", as a replacement piece and a removal.
    - "Visit ↗ ↗https://x.org↗ today." reads "today.".
    - "<https://x.org13>" and "(see https://x.org13)" read as main reads them without the marker.
    - "Mail SECRET a@b.org now." reads "Mail now.".
  - With "Page furniture" switched off, "Shown in [1, 13 2] and more." and "Visit https://x.org↗ today." read exactly as on main.
  - The PR now closes #434.
- **B2, partly fixed; see B1 below.** "Quantitative ¹H NMR of ¹³C-labelled sugars", "¹⁸F-FDG PET in ²³⁸U miners", "Spin ³He and ⁴He films" and German "¹H-NMR-Spektroskopie an ¹³C-markierten Zuckern" keep their numbers. "¹AI Lab", "¹UC Berkeley" and the corpus rows still lose their marks.
- **S1, fixed.** "²Österreichische Akademie", "³École Normale", "¹Ärztekammer", "²Überseemuseum" and "² Örebro University" lose their marks.
- **N1, done.** The quote is cut at 60 characters with "…".
- **N2, noted** in the PR body.

## Checks on e94cf00

- **Corpus:** 13 documents. Every script, report and work folder is byte-identical to acde859, so the 8 planned changes against main stand as reviewed in round 1. The corpus second-run test passes for all 13 documents.
- **Fast suite** (`HYPOTHESIS_PROFILE=ci`, PR source): 6549 passed, 2 skipped.
- **Token fuzz** (`fuzz5.py` and `cmp5.py`) on new seeds, against main 7a3b3ec. There were no crashes.

  | family | seed | texts | PR-only second-run differences |
  |---|---|---|---|
  | `FAMILY=hidden` | 41 | 1500 | 2 |
  | `FAMILY=sup` | 42 | 1500 | 0 |
  | mixed | 43 | 3000 | 4 |

  None of the six involves a link or citation that holds or touches a hidden run.
  - **Five of them** are a unit ("m²", "N.") at the block's start, after a removed citation, link or hidden run. Main shows the same shapes without any hidden run:
    - "(Smith, 2019), m², Müller" and "[3]. m² p < .05" read "m²" on run 1 and "m squared" on run 2;
    - "p < .05\nhttps://x.org\nN. Fig. 2" reads "N." and then "newtons.".

    These are #405-type shapes, so the author's account holds for them.
  - **One is new:** a hidden run between a number and its unit. de `Es sind 5 [Jane] m² hier` reads "5 m Quadrat" on run 1 and "5 Meter Quadrat" on run 2; without the run it reads "5 Quadratmeter". The units step reads past the hidden run, but `through_unread` cannot place a replacement that spans it.
    - I filed it as **#445** (v1.2, lane:textprep, risk:high).
    - It is rare (a print page breaking between a number and its unit), and run 1 no longer reads the hidden text, as main did.
    - Accepted as a leftover.
- **The author's round 2 mutants** (`mut_pr5_r1.txt`, `mut_pr5_r1b.txt`): 24 of 26 are killed, each naming a failing test. Ruling on the two survivors:
  - **7, `end = kept[span.end]`: equivalent, accepted.** The characters between the edit's last read character and the next read one are all unread, and they are whole unread spans. The pieces skip them, so the same pieces come out, also with two touching spans, and for an insertion `kept[span.end] == kept[span.start]`.
  - **11, `if skip_start > at` → `if True`: not equivalent, see S1.** The PR body says two hidden-run removals never touch, but they do. A removal before closing punctuation takes the white space before it, back to the end of the previous one. In "Shown [1, 2 x y] here." with x and y hidden in two runs, the removals are (12, 13) and (13, 15). Unmutated, this reads "Shown here.". With the mutant, the citations step makes an empty removal and the run fails with `StepError: text step 'citations' failed: a remove edit needs a non-empty span and no replacement`.
- **CI with `ci:full`** on e94cf00: `tests (ubuntu-latest)`, `tests (macos-latest)` and `tests (windows-latest)`, the browser run, lint and layers, licences, security and CodeQL are all green. `mergeable_state` is clean.
- Nightly seeds are left for round 3, which is expected to approve.

## Fix list

### Blockers

**B1. A mass number before a two-letter element symbol is still removed at a line's start, at the block's start or after a comma.** The rule now needs a capitalised word of two letters or more after the mark. Element symbols such as He, Li, Rb, Sr, Yb and Cs are such words. So in a title, or in an abstract on page 1 before the first heading, where APS and Nature papers put no heading, the printed mass number goes (D-57). Main reads all of these as printed.

| printed (sup in brackets), title block | PR |
|---|---|
| en `[87]Rb Bose-Einstein condensates in orbit` (block start) | `Rb Bose-Einstein condensates in orbit` |
| en `Bose-Einstein condensation of\n[87]Rb in microgravity` (line start) | `… condensation of Rb in microgravity` |
| en `We trap ultracold atoms of\n[6]Li and [40]K in a lattice and of\n[171]Yb, [87]Sr and [133]Cs.` | `… of Li and 40 thousand … of Yb, Sr and 133Cs.` |
| en `[3]He spin filters` (block start) | `He spin filters` |
| de `Kondensate aus\n[87]Rb im Orbit` (line start) | `Kondensate aus Rb im Orbit` |

(The "40K" reading, "40 thousand", is the same on main, so it is not part of this item.)

**Fix:** a mark "before an affiliation" does not count when the word after it is the symbol of a chemical element. Use a fixed list of the 118 symbols, or the two-letter ones with one-letter symbols already excluded by the two-letter rule. Another rule that meets every row is also fine.
- **Tests** (each fails on e94cf00): the five rows as regression cases in the language shown, on both runs.
- **Controls that keep losing their marks:** "¹AI Lab", "¹UC Berkeley", "²Österreichische Akademie", and the chi, arsiwalla, liu and biggs corpus rows.

### Should-fix

**S1. The `if skip_start > at` guard in `edits_around` has no test, and it is not equivalent.** Two hidden-run removals can touch (see above), and without the guard a citation or link around them gets an empty removal, which makes the step fail.

**Fix:** add the row en `Shown [1, 2 x y] here.`, with `x` and `y` hidden in two separate runs, as a unit test of `edits_around` or as a regression case. It reads "Shown here." on both runs, and it must fail with mutant 11 applied. Also correct the PR body's sentence that says the two removals never touch.

## Leftovers

- **#445:** a hidden run between a number and its unit (new, filed by this review).
- #431 and #405 are already filed. #434 is closed by this PR.

## Next

Round 3 checks B1 and S1. If it is expected to approve, it also runs nightly seeds 2024 and 123456, a fuzz pass on new seeds, a rerun of mutant 11 and a sample of the new mutants, and `ci:full` on the new head.
