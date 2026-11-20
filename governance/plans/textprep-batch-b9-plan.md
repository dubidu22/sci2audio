# Textprep batch B9: citation lists and join words (#414, #415, #402)

Status: **Approved D-791, 19 Nov 06:06Z** (decisions A and B as recommended; F3 files the ruling question; German noun limit of #402 pinned and documented). Critical: English and German regression rows, one changed English row, see 5.
Author: textprep lane thread "Fix citation lists and join words", 19 Nov 2026 ~06:30Z. Base: main b6355cc (B6 #616 merged).
Read: `next-batches-2026-11-19.md` (rows 414/415/402, B9, §4), D-776, issues #414 #415 #402 (all three have acceptance
criteria, PLAN-04 met), CLAUDE.md, `.claude/rules/tests.md`, `textprep-batch-b6-plan.md` (template),
`review-pr616-round1.md` (what the reviewer checks), REVIEW LESSONS in `memory/MEMORY-archive-2026-11-18.md`,
`citations.py` (`_numeric`, `_pair`, `_spoken`, `_cited_once_inner_citations_go`, `_listed_inner_names`, `_year_shell`,
`_shells`, `_parts`), `links.py` (`_block_edits`, `_dangling_join`, `_join_after`), the D-668 rows of `english.toml`.

## 0. What reproduces on b6355cc (probe: `run_steps`, then `rebuilt_from_script` and `run_steps` again)

Every row reads the same on run 1 and run 2, so these are reading bugs, not second-run breaks.

| issue | printed | reads today | wanted |
|---|---|---|---|
| #414 | `It holds [1], [2] and [3] here.` | `It holds, references 2 and 3 here.` | `It holds here.` |
| #414 | `It holds [1], [2], [3] and [4] here.` | `It holds, references 3 and 4 here.` | `It holds here.` |
| #414 | `It holds [1, 2], [3] and [4] here.` | `It holds, references 3 and 4 here.` | `It holds here.` |
| #414 | `As shown in [1], [2] and [3], it holds.` | `As shown in reference 1, references 2 and 3, it holds.` | `As shown in references 1, 2 and 3, it holds.` |
| #414 | `Es gilt [1], [2] und [3] hier.` | `Es gilt, Quellen 2 und 3 hier.` | `Es gilt hier.` |
| #414 (found) | `[1], [2] and [3] show it.` | `Reference 2 and reference 3 show it.` (loses 1) | `References 1, 2 and 3 show it.` |
| #414 (found) | `Refs. [1], [2] and [3] show it.` | `Reference 1, references 2 and 3 show it.` | `References 1, 2 and 3 show it.` |
| #414 (found) | `As shown in [1], [2], [3], it holds.` | `As shown in reference 1, it holds.` (loses 2, 3) | `As shown in references 1, 2 and 3, it holds.` |
| #414 (found) | `It holds [1], [2] here.` | `It holds, here.` | `It holds here.` |
| #414 (or) | `It holds [1], [2] or [3] here.` | `It holds, or reference 3 here.` | AC: stays as today (follow-up F1) |
| #415 | `((Smith, 2019) 2021) is cited.` | `is cited.` | `Smith is cited.` |
| #415 | `(see (Smith, 2019); (Lee, 2018)) is cited.` | `(see Smith) is cited.` | `Smith and Lee is cited.` |
| #415 | `((Smith, 2019) (Lee, 2018)) is cited.` | `is cited.` | `Smith and Lee is cited.` |
| #415 | `((Smith, 2019); and (Lee, 2018)) is cited.` | `is cited.` | `Smith and Lee is cited.` |
| #415 | `(Jones, 2020; ; (Smith, 2019)) is cited.` | `is cited.` | `Jones and Smith is cited.` |
| #415 (flat form) | `(Smith, 2019; and Lee, 2018) is cited.` | `Lee is cited.` (loses Smith) | `Smith and Lee is cited.` |
| #415 (flat form) | `(Jones, 2020; ; Smith, 2019) is cited.` | `is cited.` | `Jones and Smith is cited.` |
| #415 (one item) | `((Smith, 2019)) is cited.`, `(see (Smith, 2019)) is cited.` | `is cited.`, `(see Smith) is cited.` | `Smith is cited.` (see 2.3, decision B) |
| #402 | `We thank Smith and https://x.org here.` | `We thank Smith and here.` | `We thank Smith here.` |
| #402 | `Wir danken Müller und https://x.org hier.` | `Wir danken Müller und hier.` | `Wir danken Müller hier.` |
| #402 (found) | `We thank Smith, Lee, and https://x.org here.` | `We thank Smith, Lee, and here.` | `We thank Smith, Lee here.` |

The two flat forms matter: #415's criterion is "reads its names as the flat form does", and the flat forms of rows 4 and 5
lose names too. So the flat forms are fixed in the same change (same cause: `_parts` does not skip an empty part or a join
word right after ";"); without that the nest rows cannot meet the issue's "wanted" column.

**Corpus (13 sources, default settings, block text of main b6355cc):** no list of two or more square brackets, no nest of
round brackets around a citation, and one join word before a link (`sci2audio-sample-note`: "the project page and
https://example.org/data; see also", already handled by `_dangling_join`, since ";" follows, and "page" is lower case). So
I expect the corpus scripts unchanged on both runs; the PR body gives the measured diff (script, both runs, all 13 sources).

## PR split

**One PR**, `textprep/citation-lists-b9`, labels `lane:textprep`, `risk:high`. Closes #414 #415 #402. Milestone v1.2.
Recommendation: one PR, not two. All three add rows to `english.toml` and `german.toml` and a CHANGELOG line, and
`citations.py` imports `link_removals` (#402 changes what it returns), so two PRs would conflict in the row files and need
the citation tests re-run on the second anyway; #402 is small (~25 lines). Files: `textprep/citations.py`,
`textprep/links.py`, `tests/regression/english.toml`, `tests/regression/german.toml`, `tests/unit/test_textprep_citations.py`,
`tests/unit/test_textprep_links.py`, `tests/unit/test_textprep_links_in_brackets.py`,
`tests/unit/test_textprep_links_citations_de.py`, `CHANGELOG.md` (D-768). Not touched: `wording.py` (its `references`,
`list_comma`, `list_and` already say "references 1, 2 and 3" / "Quellen 1, 2 und 3"), word lists, `utterances.py`,
`known-errors.toml`, `tests/sentences/`, goldens, snapshots, CI, anything outside textprep.

Earlier rules this PR revisits: the D-668 pair rule (#257, `_pair`), the #372/#375 listed inner names (D-668,
`_listed_inner_names`, `_year_shell`), the #278/#279 nest rules (D-605: "((Smith, 2019)) is cited" kept "as before"),
and `_join_after` (#257, D-668). Each keeps its own rows; changed expectations are listed in 5.

## 1. #414 a list of citation brackets is one citation

**Cause.** `_numeric` decides each square bracket alone; only `_pair` joins two, and only an aside bracket to a second
one after "and". In a list the first brackets are asides (the word before them is "[1]," or a verb), so they go one by one,
leaving their commas, and the last two meet the pair rule. A needed first bracket ("in [1]") is read alone, and the
brackets after it are asides of no word, so they go ("in [1], [2], [3]" reads "in reference 1").

**Change.** One structural rule: a **bracket list** is a run of two or more sibling square brackets (same parent, in text
order) set off only by "," (each gap is `\s*,\s*`), with an optional last join ", and" / " and" (German " und"), where
every item passes the checks a single numeric citation passes today (not glued to a word, no number glued after the last
item, not a German decimal interval, not after a maths or statistics sign or word, not one of the statistics step's
interval brackets), and all items are of one kind: whole numbers, lists and ranges (`_NUMERIC`), or listed keys
(`_keys`). A bracket with a page (`[12, p. 3]`) is no item (as in the D-668 pair): the list ends before it.
The list is then judged as **one citation**, by the words before its first bracket, exactly as a single bracket is:
- an aside: the whole list goes, one removal from the first "[" to the last "]" (with the space before, as today):
  "It holds [1], [2] and [3] here." reads "It holds here.";
- needed (a word of `before`, a reference word "Refs.", or the subject): read once, "references 1, 2 and 3" (items
  flattened, ranges as "2 to 6", as `_spoken` already reads "[1, 2] and [3, 4]"); "Refs." goes into the reading as today;
  at a sentence start with a capital ("References 1, 2 and 3 show it.").
"or"/"oder" never joins a list (AC 2): "[1], [2] or [3]" is no list and reads as today.

**Where.** The runs are found **once per look** in `_once`, in one left-to-right pass over the square brackets (a dict
from each run's first opening to its members), so a block of n brackets costs O(n), not a scan per bracket (#268, D-599).
`_numeric` then decides a run at its first bracket and returns `[]` for the others (as `_paired` does today for a pair's
second bracket). The pass reads only the gap between neighbouring brackets, so the D-599 work budget is unchanged.
`_pair` becomes the two-item case of the run, keeping D-668 (decision A below).

**Decision A (needed for the approval): what a two-item list reads.**
- An **aside-first pair joined by "and"** keeps D-668: "between [1] and [3]" / "It holds [1] and [3] here." read
  "references 1 and 3" (the row `citations-a-pair-of-numeric-citations-the-sentence-needs` is unchanged on this line).
  Reason: "between" takes exactly two; changing that is not asked for. A list of three or more after an aside word goes
  whole, which is what #414 asks. The asymmetry for "It holds [1] and [3] here" (read, though an aside) becomes follow-up F3.
- A **needed-first pair** ("It was shown in [1] and [3].") today reads "reference 1 and reference 3" (row
  line 4). With the list rule it reads **"references 1 and 3"**, as the needed list and the D-668 pair read.
  **Recommended: change it** (one reading over the whole list, the issue's own wording; the row's expected line changes,
  listed in 5). Alternative: keep it and exclude two-item needed lists by one more condition.
- A **comma-only list** ("It holds [1], [2] here." reads "It holds, here." today; "in [1], [2]" reads "in reference 1")
  is beyond the AC's wording (it asks for a last "and"). **Recommended: include it**, because it is the same run without
  its join word and excluding it needs an extra condition; the alternative is a follow-up issue.

**Not changed.** "or"/"oder" lists and pairs (row line 5 "It holds or reference 3 here." unchanged; F1); a list mixing
numbers and keys; a list holding a paged bracket (each bracket as today, F4 if it misreads); brackets joined by "–"
("[1]–[3]" reads "It holds– here.", F2); a statistics list "CIs [1, 3], [2, 4] and [5, 6]" (stays the statistics
step's, pinned by a test).

## 2. #415 subject nests keep every name

**Cause.** `_listed_inner_names` lists an inner bracket only when ";" or "," sets it off on one side and nothing else
stands on the other; `_year_shell` needs two inner brackets; a lead word before the first item stops the listing; and
`_parts` (flat form) keeps a join word right after ";" in the next part ("and Lee, 2018" is then not a citation part) and
an empty part ("; ;") makes the bracket mixed.

**Change**, each a widening of an existing condition, so the reading comes from the same code (the flat-form names):
1. **Separators** (`_listed_inner_names` and `_parts`): a separator is ";" or "," with an optional join word after it
   ("; and", ", and", "; und", "&"), or a run of them with nothing between ("; ;"). An empty part is skipped, so
   "(Jones, 2020; ; Smith, 2019)" is the two parts "Jones, 2020" and "Smith, 2019". The join word is read as the list's
   own "and" (the names are joined by `_subject`'s `list_and`), so "Smith and Lee is cited", never "Smith and and Lee".
2. **Side by side**: two or more inner brackets with only white space between them are items when the outer bracket holds
   nothing else outside them (besides lead words, 3, or a year shell's year, 4): "((Smith, 2019) (Lee, 2018)) is cited"
   names both. "((Smith, 2019) Jones, 2020) is cited" keeps "Jones is cited" (its rest is a citation part, not a bracket;
   pinned today, unchanged).
3. **Lead words before the first item**: "(see (Smith, 2019); (Lee, 2018)) is cited" names both, as the flat form "(see
   Smith, 2019; Lee, 2018)" does; the lead words go with the bracket (as `lead_before` takes them today).
4. **One citation in a year shell**: `_year_shell` accepts one inner bracket when the bracket is the subject or after a
   noun word: "((Smith, 2019) 2021) is cited" reads "Smith is cited". As an aside it still goes whole in `_shells` (#339),
   unchanged ("It holds ((Smith, 2019) 2021) here." reads "It holds here.").

**Decision B (needed for the approval): the one-item nests.** "((Smith, 2019)) is cited" reads "is cited." and "(see
(Smith, 2019)) is cited" reads "(see Smith) is cited." today, pinned by three unit tests as "as before" (D-605,
`test_an_empty_nest_as_the_subject_goes_whole`, one row each in `test_textprep_links_in_brackets.py` and
`test_textprep_links_citations_de.py`). They are the one-item cases of rows 1 and 2: with 2.3 and 2.4 they would read
"Smith is cited." unless excluded. **Recommended: let them read "Smith is cited."** (the flat form's reading, and the
same rule as row 1), and change the three tests, each with its reason; the alternative is one exclusion and a follow-up.

**Budget (D-599).** No new look and no new scan: each widened condition reads only the gaps between an inner bracket and
its neighbours (already read today) or the outer bracket's own text (already capped at `_LOOK_BACK` in
`_lead_around_gone`). The slow linear-time tests in `test_textprep_citations.py` get the new shapes (nests 2,000 deep of
"((Smith, 2019) (Lee, 2018))" and "(see (Smith, 2019); and (Lee, 2018))"); a nest beyond the budget stays as printed, as now.

**Not changed.** Aside nests go whole as today ("It holds ((Smith, 2019) (Lee, 2018)) here." reads "It holds here.").
Mixed brackets keep their prose ("Data ((Smith, 2019); foo (Lee, 2020) 2021) here." unchanged).

## 3. #402 a join word before a removed last link goes with it

**Cause.** `_dangling_join` takes a join word before a link only when nothing follows the link; `_join_after` takes one
after it. The third shape, join word before the link and words after it, keeps the join word.

**Change.** One function `_join_before`, called in `_block_edits` where `_join_after` is, for a link removed alone
(`bare`, no lead word or bracket went with it) and only when no join word went after it (so "Smith and https://x.org and
Lee" still reads "Smith and Lee", one "and"): the join word right before the link ("and", "or", "und", "oder", and the
comma forms ", and", ", or", the alpha joins `_join_after` uses) goes too when the word before it starts with a capital
and is not the sentence's first word (a name; in German also a noun), mirroring `_join_after`'s cue on the other side.
So "We thank Smith and https://x.org here." reads "We thank Smith here.", and "It rains and https://x.org shows it."
keeps its "and" (AC: the join word stays where it joins clauses). Words after the link are what tells this shape from
`_dangling_join`'s, which keeps its rule and runs first.

**Known limit (said in the docstring and the PR body).** In German every noun has a capital, so "Wir messen die Daten und
https://x.org zeigt sie." would lose its "und" too ("... die Daten zeigt sie."); with the "und" kept it reads "... die
Daten und zeigt sie.", which is no better: the removed link was the clause's subject either way. A unit test pins it, so
the reach is explicit.

**Consumers of `link_removals`** (lesson: grep every consumer of a changed contract): `citations.py` (links' spans for
`_clear_of_links`, `_around`, the second-run rewrite), `abbreviations.py:246`, `statistics_de.py:219`. A removal that now
starts at the join word: checked by a unit test per consumer that a citation or abbreviation right before the join word
reads the same ("[1] and https://x.org here": the word before "and" is "]", so no change; "z. B. Müller und https://x.org
hier" keeps "zum Beispiel Müller hier").

## 4. Second runs, sentence gate, goldens

- Every new reading is stable on a second run by shape: an aside list or nest leaves plain text; a needed list reads words
  with no bracket left; a removed join word leaves nothing to decide. The rows run the D-577 script check and B6's
  second-run cut check (`test_the_utterances_cut_the_same_on_a_second_run`); no new entry in `SECOND_RUN_EXCEPTIONS` or
  `SECOND_RUN_CUT_EXCEPTIONS`.
- Sentence gate floors and `known-errors.toml`: untouched (the natural sets hold none of these shapes).
- Goldens and snapshots: none should move (corpus, 0). If a corpus script moves, I stop and report it before the PR.

## 5. Regression rows (written first, failing on main, then the rules)

`english.toml`:
- `citations-a-list-of-citation-brackets-is-one-citation` (#414): blocks `It holds [1], [2] and [3] here.`,
  `It holds [1], [2], [3], and [4] here.`, `It holds [1, 2], [3] and [4] here.`, `It holds [1], [2] here.`,
  `As shown in [1], [2] and [3], it holds.`, `[1], [2] and [3] show it.`, `Refs. [2–6], [8] and [9] show it.`,
  `It was found in [MH17], [Fa14] and [Ka20].` with a References section listing the three keys; expected
  `It holds here.` ×4, `As shown in references 1, 2 and 3, it holds.`, `References 1, 2 and 3 show it.`,
  `References 2 to 6, 8 and 9 show it.`, `It was found in references MH17, Fa14 and Ka20.`.
  Goal: a list of brackets joined by commas and a last "and" is one citation: it goes whole as an aside, or is read once.
  (No "or" row: its reading today is wrong and a row must not lock it in, lesson; a unit test pins only that it is not
  joined, F1.)
- `citations-subject-nests-keep-every-name` (#415): the issue's five rows plus the two flat forms; expected per 0.
- `links-a-join-word-before-a-last-link-goes` (#402): `We thank Smith and https://x.org here.`, `We thank Smith, Lee,
  and https://x.org here.`, `It rains and https://x.org shows it.`; expected `We thank Smith here.`,
  `We thank Smith, Lee here.`, `It rains and shows it.` (the last pins the clause join the AC keeps).
- **Changed expectation** (only with decision A recommended): `citations-a-pair-of-numeric-citations-the-sentence-needs`,
  line 4 `It was shown in reference 1 and reference 3.` → `It was shown in references 1 and 3.`; its goal text gains
  "a needed pair reads once over both".
`german.toml`:
- `de-citations-a-list-of-citation-brackets-is-one-citation`: `Es gilt [1], [2] und [3] hier.`, `Wie in [1], [2] und
  [3] gezeigt, gilt es.`, `[1], [2] und [3] zeigen es.`; expected `Es gilt hier.`, `Wie in Quellen 1, 2 und 3 gezeigt,
  gilt es.`, `Quellen 1, 2 und 3 zeigen es.`
- `de-citations-subject-nests-keep-every-name`: `((Müller, 2019) 2021) wird zitiert.`, `(vgl. (Müller, 2019); (Lee,
  2018)) wird zitiert.`, `((Müller, 2019) (Lee, 2018)) wird zitiert.`, `((Müller, 2019); und (Lee, 2018)) wird zitiert.`,
  `(Jones, 2020; ; (Müller, 2019)) wird zitiert.`; expected `Müller wird zitiert.`, `Müller und Lee wird zitiert.` ×2,
  `Müller und Lee wird zitiert.`, `Jones und Müller wird zitiert.`
- `de-links-a-join-word-before-a-last-link-goes`: `Wir danken Müller und https://x.org hier.`, `Es regnet und
  https://x.org zeigt es.`; expected `Wir danken Müller hier.`, `Es regnet und zeigt es.`

## 6. Unit tests and test-harness changes (all of them)

- `test_textprep_citations.py`: the list rule, parametrized (aside / needed / subject / ref word; 2, 3, 4 items; Oxford
  comma; ranges and multi-number items; listed keys; German); what is no list (an "or" list is not joined and not read
  as "references 1, 2 or 3"; numbers mixed with keys; a paged bracket ends the list; a bracket glued to a word; "CIs
  [1, 3], [2, 4] and [5, 6]" stays the statistics step's; "[1,2; 3,4]" German decimals; a number glued after the last
  item); the #415 nest shapes and their one-item cases (decision B); each case on both runs. Slow linear-time cases: a block
  of 20,000 brackets "[1], " in one list and in lists of three; the two deep nests of 2.
- `test_textprep_links.py`: `_join_before` cases: list (en, de, Oxford comma, "or"), clause join kept (lower-case word
  before), sentence's first word ("And https://x.org shows it." keeps nothing to remove), one "and" kept when a join word
  goes after ("Smith and https://x.org and Lee"), a lead word that went with the link (not `bare`) keeps the join, the
  German noun limit of 3 pinned, and the consumer checks of 3 (citation and abbreviation before the join word).
- `test_textprep_links_in_brackets.py`, `test_textprep_links_citations_de.py`, `test_textprep_citations.py`: the three
  one-item tests of decision B change (only if approved), each with a comment naming #415; the row "(see (Smith, 2019);
  (Lee, 2018)) is cited." → "Smith and Lee is cited." (that is #415 row 2, required by its AC).
- Hypothesis: the citation property strategy `_SIBLINGS` in `test_textprep_citations.py` gains "[1], [2] and [3]" and
  "((Smith, 2019) (Lee, 2018))" so the existing properties (no crash, spans valid, idempotent, second run) cover the new
  shapes. No other harness change: no change to `make_document`, `rebuilt_from_script`, `said`, the regression loader,
  `SECOND_RUN_EXCEPTIONS` or `SECOND_RUN_CUT_EXCEPTIONS`. Nothing weakens the D-577 script check.
- Hand mutants of the new code (the method of `plans/b6-mutants/hand.py`: clean worktree, baseline green, each mutant
  alone, the citation, links and both regression files, `-x`): every condition of the run finder (gap pattern, kind check,
  each per-item check, the "or" exclusion, page exclusion), of each widened #415 condition, and of `_join_before` (capital
  check, first-word check, `bare`, no-join-after). Each survivor gets a test that names its rule; an equivalence claim comes
  with a counterexample search (lesson). Logs in `plans/b9-mutants/`, the table in the PR body.

## 7. Checks before hand-off

Fast suite, ruff, format, lint-imports, deptry; the slow linear-time tests of citations and links; Hypothesis `dev`
profile with fresh `.hypothesis` plus 3 extra seeds on the citation and links property tests; a fuzz of the three shapes
(`plans/b9-probes/fuzz.py`: random lists of 1 to 6 brackets with random items, joins, lead words and sentence contexts,
random nests of the #415 kinds, random join word + link + rest; en and de; both runs; checks: no crash, second run equal,
no "references" with a lost number, no doubled join word, bracket balance); the corpus script diff main vs branch (13
sources, both runs; expected none); the hand-mutant run; then `ci:full` (critical) and Linux CI green before hand-off;
`ci:full` removed after. Ledger line per PR. One CHANGELOG line under Fixed: "A list of citation brackets such as
"[1], [2] and [3]" is read as one citation, subject citations in nested brackets keep every name, and "and" before a
removed link at the end of a list goes with it (#414, #415, #402)."

## 8. Follow-up issues to file (proposed milestone v1.2.x)

- F1: "or"/"oder" lists and pairs of citation brackets: "It holds [1], [2] or [3] here." reads "It holds, or reference 3
  here."; "It holds [1] or [3] here." reads "It holds or reference 3 here." (#414's AC keeps them as today).
- F2: a range of brackets "[1]–[3]" reads "It holds– here." (the dash stays).
- F3: an aside pair "It holds [1] and [3] here." reads "references 1 and 3" (D-668's rule for "between [1] and [3]"
  also reads aside pairs); with B9 a list of three after the same words goes whole. A ruling on whether the pair keeps
  D-668 everywhere or only after "between"/"zwischen".
- F4 (only if the probes show a misreading): a list holding a paged bracket ("[12, p. 3], [4] and [5]").

Size: ~90 lines of rule code (list runs ~45, nest conditions ~30, `_join_before` ~15), ~300 lines of tests and rows.
Review: Opus high (critical), up to four rounds; final round ci:full, mutation, nightly seeds.
