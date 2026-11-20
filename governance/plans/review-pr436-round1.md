# Review PR #436, round 1 (textprep batch 2 PR 5: hidden runs #193, affiliation marks #93, figure alt text #191, link language #428)

Head reviewed: acde859, which is 75c25ac with main 8fb51ac merged in. Plan: plans/textprep-v12-pr5-plan.md (D-692), with the approved deviation D-699 (`unread_marks`). Critical.

**Verdict: not approvable yet. There are two blockers (B1, B2), one should-fix item (S1) and two nits (N1, N2).** Since this round main has moved on to fbc4d12 (#433), so round 2 needs that main merged in.

## What I checked

- **Plan.** The change follows the plan and D-699. The PR body closes #193, #93, #191 and #428, and the commit messages carry no closing keywords. The new step order is hidden-runs as the first inline step and affiliation-marks right after footnotes.
- **#428, language.** Every caller of `link_removals` passes the language: `abbreviations.py:245`, `statistics_de.py:213` (always "de") and `citations.py:400`. `LinkStep.find` passes `context.language` to `_block_edits`, which has no default left.
- **Corpus:** 13 documents against main 8fb51ac.
  - Exactly the 8 planned documents differ: the scripts and reports of chi, arsiwalla, liu, waskom, biggs and the two Markdown notes, and the reports of the Time Machine EPUB. Every other file is byte-identical, including the work folders.
  - Each script change is the plan's row, word for word, and each is right as printed (D-57): only the affiliation marks go, and the two figures read their alt text.
  - `test_every_corpus_document_reads_the_same_on_a_second_run` passes for all 13 documents.
- **Golden files.** The regression files only add cases (english.toml +209 −0, german.toml +125 −0). The three snapshot diffs are the ones the PR body lists: the footnotes counts in `test_textprep_furniture.ambr`, waskom in `test_app_corpus.ambr`, and the German note in `test_layout_language.ambr`.
- **The oracle change.** `rebuilt_from_script` copies each block's picture alt texts from the first document, never from the script. `read_twice` still compares spoken text only. Accepted, as the PR body argues.
- **Fast suite** (`HYPOTHESIS_PROFILE=ci`, PR source): 6478 passed, 2 skipped.
- **Probes.** About 60 hand rows with tagged runs (`hidden`, `aria-hidden`, `epub:pagebreak`, `sup`, pictures), in en and de, ran through the whole chain twice, against main 8fb51ac. The plan's rows read as planned:
  - "Visible text", "after mid", "text.", "Haustür", "Die Probe wog 5 Kilogramm.", and "Es hatte 37 Grad Celsius am Tag." (the `unread_marks` row).
  - "Jane Roe, Ann Lee" and "Example University, Example Institute". A mark after the first heading stays.
  - "A figure is skipped. It shows: Is it a cat?; a dog.", "Eine Abbildung wird übersprungen. Sie zeigt: Ein Balkendiagramm.", the plain notice for empty alt texts, and the caption's name when a caption names the figure.
  - B1, B2 and S1 are the rows that do not.
- **Token fuzz:** the author's `fuzz5.py` and `cmp5.py` on new seeds, the whole chain twice, against main 8fb51ac.
  - `FAMILY=hidden`, seed 31, 1500 texts: 47 second-run differences on the PR only.
  - `FAMILY=sup`, seed 32, 1500 texts: none.
  - Mixed, seed 33, 3000 texts: 34 on the PR only.
  - There were no crashes. Every PR-only difference I looked at is B1.
- **Mutants:** see the section below.
- Nightly seeds and `ci:full` are left for the round expected to approve. The author's three-system run on acde859 is green.

## Fix list

### Blockers

**B1. A hidden run or page-break marker inside a link or citation, or touching one, makes run 1 keep what run 2 removes, and run 1 now reads a URL aloud that main removed.**
- **Why.** `hidden-runs` is the first inline step, so its edit wins the overlap. The links or citations edit is then set aside, and the link or citation is read as printed. On the second run the hidden text is gone, so the link or citation is found and removed.
- **The rule this breaks.** The four later steps read the text without hidden runs (`unread_marks`), but links and citations do not. That goes against "New skip rules must also apply to every rule the fuzz check covers" (TST-03, D-699).
- **The main reading.** Main removes these links, so for links this PR reads worse than main on the first run.

| printed (tagged run in brackets) | main | PR run 1 | PR run 2 |
|---|---|---|---|
| en `Visit https://x.org[↗ aria-hidden] today.` | `today.` | `Visit https://x.org today.` | `today.` |
| en `Smith, J. (2019). A paper. https://doi.org/10.1000/18[13 pagebreak] More.` | `Smith, J. (2019). A paper. More.` | `… A paper. https://doi.org/10.1000/18 More.` | `… A paper. More.` |
| en `See https://x.org/[a13 hidden] now.` | `now.` | `See https://x.org/ now.` | `now.` |
| de `Siehe https://doi.org/10.1000/18[13 pagebreak] und mehr.` | `und mehr.` | `Siehe https://doi.org/10.1000/18 und mehr.` | `und mehr.` |
| de `Siehe https://x.org/daten[13 pagebreak] und mehr.` | `und mehr.` | `Siehe https://x.org/daten und mehr.` | `und mehr.` |
| en `As shown [12][13 pagebreak] before.` | `As shown [12]13 before.` | `As shown [12] before.` | `As shown before.` |
| en `Shown in [1, 2][13 pagebreak] and more.` | as printed with 13 | `Shown in [1, 2] and more.` | `Shown in references 1 and 2 and more.` |
| en `Shown by Smith et al. (2019)[13 pagebreak] and more.` | as printed with 13 | `… (2019) and more.` | `Shown by Smith et al. and more.` |
| de `Wie gezeigt [12][13 pagebreak] wurde.` | as printed with 13 | `Wie gezeigt [12] wurde.` | `Wie gezeigt wurde.` |

An external-link icon marked `aria-hidden` next to a URL is a common shape in HTML-made EPUBs. #434 defers this, but it is a defect this PR introduces, and the PR body describes it as a second-run difference only.

**Fix:** the links and citations steps read the text without the hidden runs, while Page furniture is on, just as the four later steps read it without them through `unread_marks`.
- A link or citation found that way removes its printed text, and the hidden run inside it or next to it goes as well, without the two edits overlapping. One way is to give the removal as the pieces outside the hidden spans. Another is to let the hidden-run step leave out a stretch that such a removal covers. The choice is the author's.
- With Page furniture off, everything reads as it does today.
- Then close #434 in this PR. Alternatively, keep it for the cases the fix does not reach, and say in the body which cases those are.

**Tests** (each must fail on acde859, and each is checked on both runs):
- The nine rows above, as regression cases in the language shown.
- Two controls: a hidden run inside a URL with Page furniture off, and `Visit https://x.org ↗ today.` with a space, which already reads `today.`.
- The fuzz, `fuzz5.py` with `cmp5.py`, on `FAMILY=hidden` seed 31 (1500 texts) and mixed seed 33 (3000 texts). It must show no PR-only second-run difference where a link or citation holds or touches a hidden run. Name what is left, if anything.

**B2. Isotope and mass numbers in the title block are removed as affiliation marks.** The rule "before an affiliation" takes any small raised number that follows white space and comes before a capital. In a paper title on page 1, that removes the printed mass number (D-57). Main reads these as printed.

| printed (sup in brackets), en and de, in the title block | main | PR |
|---|---|---|
| `Quantitative [1]H NMR of [13]C-labelled sugars` | `Quantitative 1H NMR of 13C-labelled sugars` | `Quantitative H NMR of C-labelled sugars` |
| `[18]F-FDG PET in [238]U miners` | as printed | `F-FDG PET in U miners` |
| `Spin [3]He and [4]He films` | as printed | `Spin He and He films` |
| de `[1]H-NMR-Spektroskopie an [13]C-markierten Zuckern` | as printed | `H-NMR-Spektroskopie an C-markierten Zuckern` |

Isotope labels in titles are common in chemistry, physics and medicine.

**Fix:** narrow "before an affiliation" so that the four rows keep their numbers while the corpus and the plan's rows stay as they are. One way that meets every row:
- The mark stands at the block's start, at a line's start, or after a comma or semicolon. After any other white space it does not count.
- What follows, after at most one space, is a word of two letters or more that starts with a capital.

Recheck chi ("1Meta AI, 2University …"), arsiwalla, liu and the biggs line-start shape. **Tests:** the four rows as regression cases, in English and German, failing on acde859, plus "¹AI Lab" (a two-letter word) as a control that loses its mark.

### Should-fix

**S1. A mark before an affiliation that starts with a capital outside ASCII is kept.** `_AFFILIATION = re.compile(r" ?[A-Z]")` matches ASCII only, but `_NAME_END` takes any letter. These keep their marks:
- `²Österreichische Akademie` reads "2Österreichische Akademie" in the probe.
- `³École Normale`.
- `¹Ärztekammer Nordrhein, ²Überseemuseum Bremen` reads "1Ärztekammer Nordrhein, 2Überseemuseum Bremen" after "Anna Müller".
- `² Örebro University`.

German affiliations often start with Ä, Ö or Ü. **Fix:** take any capital letter there, for example `[^\W\d_]` with `isupper()`, together with B2's word rule. **Tests:** the de row with "²Österreichische" and "²Überseemuseum", and the en row with "École" and "Örebro". Both must fail on acde859.

### Nits

**N1. The hidden-run reason quotes the whole hidden text** (`hidden text "…" is not read`). A long hidden passage gives a very long report line. If you agree, cut the quote at about 60 characters with "…". Otherwise say in the PR why it stays whole.

**N2. Superscript citation numbers in a page-1 paragraph before the first heading** ("viral load in DNA¹² samples", "shown by Smith³ and others") are removed with the reason "affiliation mark". Main read them glued ("DNA12"), so the new reading is better. The reason is wrong, though. No change is asked for. Mention it in #431, or say in the body that the shape is known.

## Mutants

**The method holds up.** `mut3.py` runs the unmutated code first and stops unless it passes. It copies ROOT's `src` for each mutant and runs ROOT's own `tests/unit/test_textprep_*.py` with `HYPOTHESIS_PROFILE=ci`. Every KILLED line in `mut_pr5_final.txt` names a failing test. Mutant 54 survives there, and `mut_pr5_54.txt` shows it killed after 75c25ac.

**My rerun on ROOT = /home/user/wt436, a clean worktree at acde859.** Each run's baseline passed.
- **The author's mutants:** I reran 13 of the 55. All are killed, each by a test that hits its rule. They are:
  - 0 (`aria-hidden`), 7 (side by side), 9 (start white space), 12 (closing punctuation) and 16 (the first heading);
  - 19 (`fullmatch`), 25 (rise over a small run), 30 (`_NAME_END`) and 35 (`at_start`);
  - 41 (white-space folding), 47 and 50 (the two switches in `unread_marks`) and 54 (statistics through `unread_marks`).
- **Eleven of my own:** all are killed. They are:
  - in `footnotes.py`: `_AFFILIATION` taking any white space, the capital check on the name dropped, `at_start` without the comma, `_AFTER_NAME` without ";", the `taken` overlap check removed, both `unread_marks` switches forced on, and the rise without `RISE`;
  - in `placeholders.py`: alt text on a captioned figure, "…" not counted as an ending, and the "; " join.

  A twelfth, white-space folding, is the same as the author's 41.

The claim holds: no live guard is left without a test. B1 and B2 are gaps in what the rules cover, not in the tests.

## Next

Round 2 re-checks B1, B2, S1, N1 and N2 on a head with main fbc4d12 merged in. If it is expected to approve, it also runs the 13 corpus documents, the fuzz, the author's and my mutants, nightly seeds 2024 and 123456, and `ci:full`.
