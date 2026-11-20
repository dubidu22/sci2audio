# Review: PR #245, round 1 (release-day PR for 1.0.0, base release/1.0, draft)

14 Nov 2026 ~03:55 UTC on head 98388c2 (base b25f192). Content review only: **do not merge**; the merge waits for Colin's hand steps and the coordinator's go.

**Verdict: content approved, no fixes needed.** What remains is Colin's and the last commit's.

## Checked

- One file, `docs/listening-tests/1.0.0.md`. Its table header and the M4B check are the same as `docs/listening-tests/template.md`. Only three things differ: the version in the title, the voice line, and one paragraph explaining that 1.0.0 chooses the ten rows later releases reuse.
- Voice line "af_heart, speed 1 (the defaults)" matches the code: `DEFAULT_VOICE = "af_heart"` (voices/kokoro_engine.py) and `speed: float = 1.0` (app/settings.py).
- All ten paragraph references checked against `sci2audio script --ignore-settings` output on this branch's code. For each row, the chapter number and title match the command's chapter list, and every quoted start or phrase appears in the listening script: seaborn ch. 2 "Summary" and ch. 3 "Statement of need"; chi ch. 5 "3 Experiment Results" (with "Rows 2 to 9") and ch. 9 "Ethics Statement" ("100 thousand steps", "9 kilograms"); hardt ch. 7 "5 Results" ("48.8 to 85.8") and ch. 5 "3 Data" ("Table 1 is skipped."); nowak ch. 3 "1 Introduction" ("Footnote 1.") and ch. 4 "2 Preliminaries" ("Formula 1/2 is skipped."); liu ch. 1 (its only chapter; "2∆ represents a gap", "plus or minus"); arsiwalla ch. 3 "1 Introduction" ("Footnote 1.", "Roger Penrose has been"). Row 2's citations (Tukey, 1977) and (Hunter, 2007) are in seaborn's report as left out.
- Corpus licences: all six papers are listed in `tests/corpus/LICENSES.md`. The sheet names paragraphs by position and their first few words only, so no corpus text is copied.
- `docs/baseline.md` needs no change in this PR now: the M4 rows are already placeholders for Colin's numbers. The changelog date is planned as the last commit. The release workflow's build job refuses a tag without a date (#225 F3), so a forgotten date cannot ship.

## Before the merge (not author fixes)

- Colin fills in the sheet (scores, date, listener, device, M4B check), and his M4 rows go into `docs/baseline.md`.
- The last commit sets `## [1.0.0] - YYYY-MM-DD` on the tag day.
- The branch is behind `release/1.0` (now 87ba1f5 after #234). Bring it up to date before the merge.
- Merge by squash only after the coordinator's go. The `release/*` ruleset (D-491) is still Colin's step, so check "CI passed" by hand.
