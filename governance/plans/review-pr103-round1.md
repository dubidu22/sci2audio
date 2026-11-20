# Review of PR #103 (#66 links and citations), round 1

Reviewed head bf3c8b7 (main 395e4c9), 13 Nov 2026. Review thread "Review citations and links PR".

## What I ran

- Fast suite: 1377 passed, 45 snapshots passed. ruff, format, lint-imports (2 kept), deptry: clean.
- CI on bf3c8b7: green on Linux, macOS and Windows.
- `HYPOTHESIS_PROFILE=nightly` on test_textprep_links, test_textprep_citations, conformance, runner and
  tests/regression: **1 failed, 214 passed** (see M1).
- A random fuzz of 30,000 short texts built from links, citations, brackets and repair words through
  `check_edits` for both steps: citations clean, links fails (M1).
- Timing probes up to 100k characters (S2) and a deep bracket nest (M3).
- Trial merge with PR #98 (conflicts in registry.py, `__init__.py`, both snapshots and two test files, as
  expected): with the steps of both PRs, "https://aclanthology.org/2023.acl-\nshort.4" is claimed whole by
  `links` and the hyphen step is set aside (D-170 and #98's N1 hold).

## Golden edits against the PDFs

I read every accepted edit outside reference lists in `test_textprep_citations_links_corpus.ambr` (all 8
papers) and checked a sample against `pdftotext` of the PDFs (Chi "Approaches such as (Qin et al., 2022)
could", Arsiwalla "(see also [15] for a recent perspective on this point)", Liu "Refs. [53, 58]" and
"Refs. [68, 69]", Chi "Calculated using https://mlco2.github.io/impact,", Biggs "acm2.\n13207"). All correct:

- D-171: Liu's "Tr[⟨ρˆ⟩ ˆj]", "[n (−1) E ]", "[S (0) E ]", Nowak's "p: R → [0, 1]" stay; no numeric bracket
  outside a reference list is left in the spoken text (my own scan of every paper's script).
- D-172: 21 read as references are all prepositions or "Ref./Refs." ("discussed in [26, 61, 86, 93, 128]",
  "Refs. [53, 58]", "( [53] discusses", "8See [47]"); asides after "in 1974 [97]" and "in 2004 [89]" go.
- D-173: narrative names kept (Jelinek and Lafferty’s, Baker’s, Kocijan et al. "(2022)[p. 8]", Floyd/Warshall/Roy);
  subject "(Dasigi et al., 2019)[p. 1] note" and "such as (Qin et al., 2022) could" keep names; mixed
  "(RNNGs; ...)" reads "(RNNGs)"; nested "(e.g., BERT (Devlin et al., 2019))" reads "(e.g., BERT)"; Hardt's
  comma-split and "Spe-\nnader" bracket goes whole; "(Dated: April 5, 2024)" stays. No author-year bracket is
  left in any script outside reference lists.
- D-168 and D-170: "released at https://github.com/JFChi/PLUE." reads "released."; "github.\ncom/citp/...",
  "DanHardtDK/\nellipsisGPT3", "podcasts.ox.ac.\nuk/...", "https:\n//doi.org" are joined; Chi note 5,
  Arsiwalla's "∗x.d.arsiwalla@gmail.com" and Nowak's "https://github.com/rycolab/" read nothing.
- D-175: a script over all 587 link and citation edits on the corpus: every reason quotes the item as printed.

Liu's unheaded reference list (its "[1] " entry numbers and "Nature Nanotechnology (2023)") is #92.

## Must fix

**M1. The links step proposes overlapping edits, so in a real job the whole step fails for that document.**
The nightly profile fails `test_no_link_is_left_and_only_links_and_repair_words_go` with "edit ... characters
31-87 overlaps edit ... 66-86". `_pointer` (and the bracket repair) can reach past a later link run, and that
run then gets its own edit. Non-strict runs record a StepProblem and drop *every* link edit of the document.
Repros: "See https://a.org (mirror at www.b.org/x)." ; "(see https://a.org/x and also www.b.org/y)" ;
"cf. www.b.org/y See 10.1000/xyz". Fix: a repair that would cover a later run either takes that run into
the same edit (the reason names both links) or falls back to the plain rule; add the three as unit cases;
the nightly profile must pass.

**M2. A removal at the start of a sentence leaves doubled punctuation.**
links: "Foo bar. https://x.org/a. Bar baz." reads "Foo bar.. Bar baz."; "Foo bar. https://x.org/a, then more."
reads "Foo bar., then more." (`_whole_sentence` is checked after `_with_space` has moved the start before the
space, so `_SENTENCE_START` no longer matches). citations: "It holds. (Smith, 2019). Then more." reads
"It holds.. Then more." (no such rule at all). Fix both, and add ".." and ".," to the leftover checks of the
property tests and the corpus test.

**M3. citations crashes on deeply nested brackets.** `"(" * 5000 + "Smith, 2019" + ")" * 5000` raises
RecursionError in `_Rules._visit`. "No crash on any text" is required of every textprep module
(.claude/rules/tests.md). Walk the tree iteratively (or cap the depth) and add the case to the tests.

## Should fix

**S1. The label rule claims "the whole sentence goes" when the link does not end the sentence.**
`_SENTENCE_END = r"\A[.!?]?(?:\s|\Z)"` matches any white space. "Code: https://x.org/a is where it lives."
gives the reason 'with the label "Code:" the whole sentence goes' but removes only "Code: https://x.org/a".
"Contact: a@b.org or see https://c.org/x." reads "or.". Require a sentence end or the end of the text.

**S2. citations is quadratic in the length of a block.** `"[1] " * 20000` (80k characters) takes 17 s in
citations (links: 0.02 s): `_numeric` splits all of `text[:node.open]` and `_SENTENCE_START.search` scans
`text[:start]` for every bracket (same `_SENTENCE_START` pattern in `_is_subject` and in links). Look back
over a bounded window only; add a timing test like #86's (100k characters).

**S3. "Reference" is capitalised after an abbreviation.** "as shown before, cf. [4], and" reads
"cf. Reference 4"; "e.g. [3]" reads "e.g. Reference 3"; "Eq. [3] holds" reads "Eq. Reference 3 holds".
`_SENTENCE_START` takes any ". " as a sentence end. Do not capitalise after the abbreviations in
`before`/`lead` (or reuse the cutter's abbreviation list).

**S4. An e-mail domain runs into a glued next sentence.** "x@ucla.edu.The end" reads "end": the domain is
matched case-insensitively. Let the top-level domain stop before a capital after ".", or file an issue.

## Follow-up issues (please file, link in the reply)

- **F1. D-170 after "/" takes a plain next-line word.** "Data at https://x.org/\nand more text follows."
  reads "Data more text follows." (the word "and" is lost). Not on the corpus; the approved rule, but a lost
  word. Look for a continuation that is a path-like word, not a plain English one.
- **F2. Narrative rule after any capitalised word.** "the Olympics (2016) were held" reads "the Olympics were
  held" (the year is lost). A place, event or journal before a year bracket.
- **F3. A numeric and an author-year aside joined by "and".** "See [12, 13] and (Smith, 2020)." reads
  "See references 12 and 13 and."; "self-attention [12] and (Smith, 2019) here" reads "self-attention and
  here". Could join #102.

## Notes (no code change)

- N1. The PR body says a footnote mark in Chi and Arsiwalla is set aside "because the mark sits glued to the
  address". The two set-aside edits are the footnote intros of the link-only notes (Chi 5, Arsiwalla ∗),
  which the whole-text edit wins, exactly as D-168 says. Please correct the sentence.
- N2. For the KB PR: D-168 now has three refinements beyond the plan's five rules (a short "See/Visit/cf."
  pointer sentence or bracket goes whole; rule 1 also takes a preposition before the bracket when
  punctuation follows; a comma or semicolon left before ".", ",", ";" or a closing bracket goes). D-173's text
  should say brackets are worked outermost first, with the inner brackets of a kept bracket looked at in turn
  (the plan said innermost first; the results are the same on the corpus).
- N3. "values in [1, 10] are used" reads "values in references 1 and 10": the accepted risk of D-171.

## Verdict

Changes requested: M1 to M3, S1 to S4, issues F1 to F3, N1. The corpus output is right; the defects are in
text the corpus does not hold. After the fixes: nightly profile, fuzz repros, re-run, merge main if #98 lands
first.
