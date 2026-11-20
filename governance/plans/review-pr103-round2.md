# Review of PR #103, round 2 (head 5994d46)

All round 1 items are answered item by item; I checked each one on 5994d46.

- M1 fixed: the three repros give one edit each ("(mirror)." / nothing); a 30,000-text fuzz through
  `check_edits` raises nothing for either step.
- M2 fixed: "Foo bar. https://x.org/a. Bar baz." reads "Foo bar. Bar baz."; "It holds. (Smith, 2019). Then
  more." reads "It holds. Then more."; ".." added to the corpus leftovers. The corpus golden file changes in
  one line (Chi "Zimmeck et al. (2019)." now takes the full stop, so "Zimmeck et al. MAPS" — the cutter keeps
  "et al." as an abbreviation, so these two sentences become one utterance; acceptable).
- M3 fixed: 5,000 nested brackets take 0.49 s, no crash.
- S1 fixed: "Code: https://x.org/a is where it lives." now gives 'the label "Code:" goes too'.
- S2 fixed: "[1] " x 20,000 takes 0.24 s (was 17 s); timing tests added.
- S3 fixed: "cf. reference 4", "e.g. reference 3".
- S4 fixed: "x@ucla.edu.The end" reads "The end".
- F1 to F3 filed as #109, #110, #111; N1 corrected in the PR body; N2 in KB PR sci2audio-design #31.
- Nightly Hypothesis profile on links, citations, conformance and regression: 224 passed.

## New in round 2

**R2-1 (must fix): CI fails after main moved.** main is now 3ef8ac5 (#71, PR #99). "tests (ubuntu-latest)"
fails in tests/unit/test_app_audio_faults.py (lines 103, 116, 145: 39 utterances where #99 expects 41),
because the merge ref runs #99's tests with the #66 steps. Merge main (no force-push), find which two
utterances go and why, and derive the expected counts from the fixture instead of a hard-coded 41.

**R2-2 (should fix): the new "numbered" exclusion swallows real citations.** S3 added
`CitationWords.numbered`, matched case-insensitively, so a bracket after "algorithm", "equation", "theorem",
"lemma", "step", "line", "figure", "table" ... is never a citation:
"We train with the EM algorithm [5]." / "the Schrödinger equation [4] holds" / "by Bayes' theorem [3]." /
"the first step [7] is" all keep "[N]" in the spoken text. Citations after these lowercase nouns are common
in CS and physics papers. Count only a capitalised label word ("Eq.", "Fig.", "Table", "Section",
"Algorithm", "Theorem", ...), i.e. a label used with its number, and add the four sentences above as cases
that must still be citations. This is a change to D-171, so the KB PR #31 row must say exactly what it is.

**R2-3 (must fix, from the KB PR #31 review): "Reference" and "References" before a bracket.** D-172 (plan
1.3 rule 2) names "Ref.", "Refs.", "Reference", "References" as words replaced along with the bracket, but
`CitationWords.refs` holds only "ref." and "refs.". "in Reference [12], it holds" reads "in Reference, it
holds"; "see References [3, 5] for more" reads "see References for more". Add "reference" and "references"
to `refs` (so they read "reference 12", "references 3 and 5"), with unit and regression cases for both.

## Round 2 fixes checked (head 4d8013c, main 3ef8ac5 merged in 8ce1f10)

- R2-1 fixed: the #71 audio tests count chunks from the fixture's own script (`audio_fakes.chunk_count`); the
  two utterances that went are two long author-year lists in PyMedPhys that the cutter used to split.
- R2-2 fixed: label words count only when capitalised; "the EM algorithm [5].", "the Schrödinger equation [4]
  holds", "by Bayes' theorem [3].", "the first step [7] is" all lose the citation; "Eq. [3] holds" stays.
- R2-3 fixed: "in Reference [12], it holds" reads "in reference 12, it holds"; "see References [3, 5]" reads
  "see references 3 and 5"; "References [2] showed this." reads "Reference 2 showed this.".
- Local: ruff, format, lint-imports (2 kept), deptry clean; fast suite 1477 passed, 46 snapshots passed;
  nightly Hypothesis on links, citations, conformance, runner, utterances and regression: 315 passed;
  fuzz of 30,000 texts clean; timing probes under 0.5 s.
- CI on 4d8013c green on Linux, macOS and Windows; branch up to date with main.

Verdict: approved; squash-merged as d30e6e7 on 13 Nov 2026.
