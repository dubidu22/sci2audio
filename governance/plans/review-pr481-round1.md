# Review PR #481, round 1 (sentence-boundary batch PR 4: long-sentence cuts #460, German citations #455)

Head reviewed: e591e93. It is two commits on main 7d866bf:
- 0f4e46f, the regression cases that hold today's output (7 EN, 8 DE);
- e591e93, the change.

It is critical. Plan: plans/sentence-boundary-plan.md, PR 4 (D-719). The coordinator's checks (1) to (7) are answered below. The probes and the fixes I tried are in `plans/review-pr481-round1-probes/` (`fix481-r1.diff` holds both tried fixes).

**Verdict: not approvable yet.** There are two should-fixes, three nits, and two follow-ups that only need an Issue.
- **S1.** A long sentence is still cut inside brackets and quotations, in the corpus too (seaborn "(for example, | producing …)").
- **S2.** A year range of one year ("Wintersemester 2019/2020", "Fall 2019/2020") is now removed as a citation.
- **N1.** Two counter-tests the hand-off asks for are missing: a fraction near a year, and "S." as a name initial before a Roman-looking name (mutant 20 survives).
- **N2.** The body's second-run sentence is too strong: the cut moves on a second run more often than on main (random sentences only, the corpus is unchanged).
- **N3.** Two tests pin the even share and the fair rest (mutants 8 and 11 survive).
- **Follow-ups.** The second-run cut beside a multi-word reading, and "(Sommer 2019)" read as a citation, need Issues.

## What I checked

### (5) Corpus utterances on main and on the PR, all 13 corpus files
I dumped every utterance on both heads (`/home/user/probe/p478/utt.py`) and diffed them per file (`/home/user/probe/p481/uttdiff.txt`). Eight files change, with 17 places in all. Every change is a long sentence cut at another place, and no sentence start changes.

| file | place | main | PR | reading |
|---|---|---|---|---|
| chi | block 9 | "…including text classification, \| question answering…" | "…(PLUE) benchmark, \| to evaluate…" | better: two even parts at a clause |
| nowak | block 64 | "…that is, \| the probability…" | "…(in some fixed order), \| where the entry…" | better |
| nowak | block 147 | "Equation (11): \| The base case…" (14 characters) | one part, "…It is, therefore," | better: no clipped part |
| maass | block 15 | "Wir haben drei Zielgruppen: \| Endnutzerinnen…" | "…Wissenschaftlerinnen, \| die große Mengen…" | listed in the body (Maaß golden) |
| maass | block 55 | "…handelt, \| weiterhin…" | "…Urheberrecht, \| sofern es sich…" | listed (golden) |
| maass | block 80 | one part of 294 | "…Betroffenen, \| das sich…" | listed (golden) |
| arsiwalla | block 47 | cut at the second ";" | cut at the first ";" | even parts |
| arsiwalla | blocks 67, 127, 145 | cuts after 215 to 290 characters | cuts before "spiritual", "and leading", "as perceived" | even parts at commas |
| liu | block 50 | "…insulators, and van der Waals heterostructures, \| as well as" | "…insulators, \| and van der Waals…" | better: before "and" |
| seaborn | block 45 | "…ticks, \| and labels…" | "…matplotlib functions, \| and tweaks…" | listed (golden) |
| biggs | block 4 | "…Wagga Wagga, \| Australia…" | "…Stockholm, \| Sweden…" | same class: an affiliation list read as one sentence |
| biggs | block 32 | "…Gamma index, \| a widely…" | "…plans, \| and most frequently used…" | even parts |
| wells | blocks 115, 135, 237 | late cuts (263 to 298 characters) | cuts before "the jerking sun", "and surrounded", "and had" | better |

- **The goldens.** `test_app_corpus.ambr` changes only for Maaß (blocks 15, 55 and 80; chapter 1 goes from 22 to 21 utterances and chapter 6 from 140 to 141) and seaborn (block 45). These are exactly the places above. The other six files have no script golden.
- **Kehren** is not in the repo. Its two regression rows are cut at "…in dem Sinne, | dass …" and "…antwortet: | Es kritisiert …", as the body says (the part before the colon is 335 characters, so the second cut is needed).

### (2) The cut never inside a quotation, bracket, number, abbreviation or citation remnant
- **Numbers, abbreviations and citations hold.** A kept or read abbreviation ("e. V.", "Az. 13 W 17/12", "z. B."), a number reading and a removed citation are never cut into. `_outside_replacement` covers them, and I shifted each one through every place of a 300-character window (`cuts2.py`).
- **Brackets and quotations do not hold (S1).** The rule ranks places without looking at brackets or quotes. These probes (`brk.py`) are cut on the PR, and they were cut on main as well:
  - "… (as we saw in the first study, | which …)";
  - "… and (as | the first and the second experiment …)", which is a cut right after the opening bracket;
  - "“we hear, what we read, | and we read …”";
  - German „…“ and »…« show the same.
- **The corpus has two such cuts on the PR:**
  - seaborn block 43: "…interpret a 2D array (for example, | producing a boxplot …)";
  - arsiwalla block 136: "(either due to stimulus uncertainty, hidden states of other agents, | or the agent's own limitations …)".

### (3) Second run and language
- **The corpus.** The utterances of a first run and of a second run over its script (`/home/user/probe/p481/corpus2.py`) differ in exactly the same places on main and on the PR. These are 42 utterances in Maaß, chi and the German note, all footnote and removed-text cases that existed before.
- **The regression cases.** The long-sentence rows cut the same on the second run (EN 5, DE 4).
- **Random long sentences** (`fuzz2.py`: 40 to 120 pieces with abbreviations, numbers, citations and quotes):
  - main differs on 1 of 2,700 (seeds 1, 2, 3 × 400 per language and 481 × 150);
  - the PR differs on 11 of 2,700.
- **The cause.** On the first run a read reading such as "u. a." or "3,5 %" is one replacement and is never cut into. On the second run its words "unter anderem" and "3 Komma 5 Prozent" are plain text. The cut nearest the even share then falls one word later, inside the reading ("… die unter | anderem …", "… 3 | Komma 5 …"). On main the "last place that fits" rule hit this far less often.
- **What holds.** The script text is identical (D-577), so this is a cut-placement difference only. It touches no corpus file. It is N2 plus a follow-up Issue, not a blocker.
- **Language.** The clause openers come per language (`data/en`, `data/de`). German "dass", "weil", "die" and English "which", "but" are both exercised by the regression rows.

### (4) The #455 citation shapes
| shape | test that fails without it (mutant) | counter-test |
|---|---|---|
| reprint year "1974/2004" | `_years` without the slash: see the mutant table | **missing: a period such as "2019/2020"** (S2) |
| slash authors "Heydorn/Koneffke" | `_authors` / `_names_ok` without the slash | "und/oder", "TCP/IP", "input/output", "eins/zwei" |
| Roman page "S. XV", "pp. iv–vi" | `_PAGE` digits only | "p. Mill" (en); **no German "S." name-initial case** (N1) |
| acronym before a page "WBGU 2011, S. 1" | `page_after` off | "(EU 2016)", "(NATO 1949)", "(WBGU 2011)" without a page |

- **S2, the probes** (`cites.py`, `cites3.py`, main → PR):
  - "(Wintersemester 2019/2020)", "(Haushaltsjahr 2019/2020)", "(Saison 1999/2000)" and "(Fall 2019/2020)" were kept on main and are removed on the PR;
  - "Wie Müller (2019/2020) zeigt" now drops "(2019/2020)" too.
- **Unchanged:** "(FY 2019/2020)", "(Schuljahr 2019/20)", "(DAX 2019/2020)", "(Anteil 1/2 2019)" and "S. C. Weber".
- **Pre-existing on main:** "(Sommer 2019)" and "(Wintersemester 2019)" are removed. This is the old class of a capitalised word plus a year read as author plus year. It needs a follow-up Issue, not this PR.
- **Correct new removals:** "(BMBF 2019, S. 4)", "(OECD 2019, S. 4)", "(EU 2016, S. 4)" and "(Lorenz 1974/2004, S. xv)".

### (1) Known errors 11 → 9, and 100 random boundaries per language (seed 481)
- **The removed entries.** These are the two Lorenz entries (#455). The case "„Bewusstsein ist alles.“ (Heydorn 1974/2004, Seite 273) Danach …" now reads "„Bewusstsein ist alles.“ | Danach …", which matches the truth.
- **The 9 left** are the 4 #466 entries and 5 #477 entries. Their whys are unchanged from #478 round 2, where I checked them.
- **Floors.** They are unchanged and reproduced: en natural P 1.0000 R 0.9934, de natural P 1.0000 R 0.9916.
- **The sample** (`/home/user/probe/s478/sample.py <lang> 481`, `random.Random(481)`):
  - en: 50 hits and 50 not compared (ACL checklist items, table rows, title and caption lines; I read each, and all are real starts);
  - de: 93 hits, 1 optional (the "Fußnoten²" start) and 6 not compared (title, author, formula and table lines, all real starts).
- **No sampled start is wrong.**

### Tests first
- 0f4e46f's regression cases pass on main's source: 870 passed with `test_textprep_regression*.py` and the gate.
- e591e93 then changes only their expected cuts and the removed citations, as listed in the body.

### (6) D-718
- None of #467, #476 or #478 builds on `_cut_point` or on the citation patterns.
- **#478's removed-text sentence end** now fires for more citations. This is the intended effect: the Lorenz quotation now ends its sentence.
- **#467's gate** loses two entries and keeps its floors.
- The body's D-718 line says the same.

### (7) Windows flate-bomb test
The coordinator ruled it a one-off. I recheck it on the merged head's three-system run.

### Mutants
`/home/user/probe/m481/run.py`. Each mutant is applied to a copy of e591e93's src and tests, and these test files run with `-n 4 -m "not slow and not benchmark and not browser"` and `HYPOTHESIS_PROFILE=ci`: `test_textprep_utterances.py`, `test_sentence_boundaries.py`, `test_textprep_regression.py`, `test_textprep_regression_german.py`, `test_textprep_citations.py`, `test_textprep_links_citations_de.py` and `test_app_corpus.py`. The baseline passes: 1535 passed.

**Result:** 23 mutants were run. 18 are killed and 5 survive.

| # | mutant | result |
|---|---|---|
| 1 | ";" and ":" not ranked first | killed (`test_a_colon_wins…`, `test_cut_places_are_ranked`, regression) |
| 2, 3 | clause-opener rank off / empty opener list | killed (opener test, Maaß golden, regression) |
| 4, 5 | dash / space no place | killed |
| 6, 7 | `MIN_PIECE` 0 / fair filter without the first-part check | killed |
| 8 | fair filter without the rest check | **survives** (N3) |
| 9 | no even-share target (last place of the best rank) | killed |
| 10 | a tie goes to the earlier place | survives. This is a note: a tie at exactly equal distance ("x x x …", 152 words, gives 153/150 on the head and 151/152 on the mutant), and neither reading is more right |
| 11 | the even share is taken over the window, not over what is left | **survives** (N3) |
| 12 | `max(2, …)` → `max(1, …)` | survives. **Equivalent**: `_cut_point` runs only when the window is over `max_chars`, and `left >= counts[-1] > max_chars`, so the ceiling is at least 2 |
| 13 | `left` not lowered after a cut | killed |
| 14 | `_WORD_AFTER` without an opening mark | killed |
| 15 to 17 | `_years` / `_authors` / `_names_ok` without the slash | killed (citation tests, gate, regression) |
| 18 | `_PAGE` digits only | killed |
| 19 | `_PAGE` without the letter look-ahead | survives. This is a note: it decides only a glued "S. Xff."/"S. Vf.", which the head keeps as printed and the mutant removes. Keeping the text is the safe side |
| 20 | `_PAGE` with "d" and "m" | **survives** (N1): "(Müller 2019, S. Dix)" and "(Smith 2001, p. Dix)" are then removed |
| 21, 22 | acronym without `page_after` / always an acronym | killed |
| 23 | clause-opener list without its lower-case check | killed (`test_a_broken_clause_opener_list_names_the_file`) |

## Fix list

### Should-fix

**S1. No long-sentence cut inside an open bracket or quotation.**
- **Fix.** Rank every place inside an open bracket or quotation after every place outside one. Count the depth over the window: brackets "([{" and the language's quotes, which are “ ” « » in English and „ “ » « in German. Never treat a straight quote or an apostrophe as an opening mark.
- **Tried** (`fix481-r1.diff`, `_inside` plus `rank + 5 * inside[i]`):
  - all seven `brk.py` probes now cut outside the bracket or quote;
  - a sentence that is all inside one bracket still cuts at a space;
  - in the corpus, only seaborn 43 ("…“wide-form” data, | typically producing … (for example, producing a boxplot …) …") and arsiwalla 136 ("…incomplete social, | behavioral and sensorimotor data (either due to …) …") move;
  - the sentence, citation, regression and corpus tests pass apart from the seaborn golden, which then needs this one update.
- **Tests:**
  - an English bracket with a comma inside;
  - a cut that would fall right after "(";
  - an English and a German quotation, „…“ and »…«;
  - an all-inside bracket that still cuts;
  - all of them fail on e591e93.

**S2. A one-year range is no reprint.**
- **Fix.** `YEAR/YEAR` is a reprint only when the second year is more than one year after the first: "2019/2020" is a winter term, a season or a fiscal year.
- **Tried:**
  - a check `_no_period` in `_is_citation` and before the narrative `years_only` match;
  - every probe above stays as printed again;
  - "Heydorn 1974/2004", "1968/2004" and "1890/1990" are still removed;
  - the citation, regression, gate and corpus tests pass (1344 passed).
- **Counter-tests (fail on e591e93):**
  - "Das galt (Wintersemester 2019/2020) für alle.";
  - "Das galt (Saison 1999/2000) für alle.";
  - "This held (Fall 2019/2020) for all.";
  - a narrative "Wie Müller (2019/2020) zeigt".

### Nits

**N1. Add the missing counter-tests from the hand-off:**
- "S." as a name initial before a name that reads as a Roman numeral with "d" or "m": "Das zeigt (Müller 2019, S. Dix) klar." and "This held (Smith 2001, p. Dix) too." stay. They kill mutant 20;
- a fraction near a year: "Der Anteil (1/2 2019) sank." stays.

They pass today, so they only pin the behaviour.

**N3. Pin the even share and the fair rest.** Take the two tests in `plans/review-pr481-round1-probes/test_gaps481.py` into `test_textprep_utterances.py`. Both pass on e591e93, and each fails on its mutant (I checked).
- "A semicolon that leaves a clipped last part is not taken": 308 characters with "b," at 162 and "d;" 18 characters before the end. The head gives 162/145; mutant 8 gives 289/18.
- "Three parts share the whole sentence evenly": 140 × "word". The head gives 234/234/230; mutant 11 gives 199/249/250.

**N2. Correct the body's second-run line.** "The cut sees the same text" is not true for read abbreviations and numbers.
- **Suggested wording:** "A cut beside a multi-word reading ('u. a.' → 'unter anderem', '3,5 %') can fall one word later on a second run, because the second run sees the reading as plain words. The script text is identical (D-577), and no corpus file changes."
- Add the same sentence to the module docstring.
- Name the follow-up Issue.

### Follow-ups (need Issues, not this PR)
1. **Second-run cut beside a multi-word reading** (lane:textprep, v1.2.x).
   - On random long sentences the PR moves 11 of 2,700 cuts on a second run, against 1 of 2,700 on main. With S1 applied, 10 of 600 move for seed 481.
   - The probe is `fuzz2.py`. One possible rule: rank a space between the words of a known multi-word reading below any other space.
2. **"(Sommer 2019)" / "(Wintersemester 2019)" read as a citation** (pre-existing; lane:textprep, v1.2.x). A capitalised common noun plus a year passes as author plus year.

## Round 2
- **The fix commit:** S1, S2, N1 to N3 and the two Issues in the body.
- **The checks I rerun:**
  - the probes, the corpus utterance diff (I expect only seaborn 43 and arsiwalla 136 to move against e591e93), and the second-run fuzz;
  - all mutants plus S1 and S2 variants.
- **If clean, the final-round checks:**
  - nightly seeds (2024, 123456) on the textprep property tests, and the fuzz;
  - `ci:full` for a three-system green run on the exact head;
  - the flate-bomb test on Windows.
- **Then the merge**, on the coordinator's standing go.
