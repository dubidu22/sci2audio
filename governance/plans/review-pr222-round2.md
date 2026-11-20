# Review of PR #222, round 2

Reviewed 14 Nov 2026 at head de91438 (one commit on top of e54e0c4). Main moved to f1a334a (#218, browser tests only, no overlap). I checked the PR merged with that main locally.

**Verdict: passes.** All three fixes from round 1 are done as asked. #223 stays deferred (v1.2).

## Fixes checked

1. German conjunctions after a suspended hyphen. `HyphenWords` gains `abbreviated` (u, o, vs, resp; each counts only with its full stop) and `paired` (("als", "auch")), and "versus" joins `suspended`. English leaves both new fields empty.
   - Read right in probes: "sowohl Lehr-/als auch", "als" with a line break before "auch", "Kinder-/u. Jugend", "U.", "Lehr-/vs.", "Haupt-/resp.", "Lehr-/versus".
   - Still joined, as meant: "Materi-/als", "Materi-/als auchx", "Werk-/statt", "so-/wie", "Kinder-/u Jugend" (no full stop), "Lehr-/vs Lern".
   - English: "Kinder-/u. Jugend" still joins in an English job.
   - Two new german.toml cases: de-hyphen-suspended-als-auch and de-hyphen-suspended-abbreviated-conjunctions.
   - Known limit, not a defect: "des Materi-/als auch" (a split word followed by "auch") keeps the hyphen. Telling it apart would need meaning.
2. Five German reference titles added, with case de-reference-list-combined-title and six probes in the agreement list.
3. The golden header no longer points to a file outside the repository.

## Checks

- Fast suite on the PR merged with main: 3364 passed, 1 skipped (ci profile).
- Nightly Hypothesis profile on the hyphen, placeholder, German regression and conformance tests: 322 passed.
- English byte-identity again: all 10 corpus documents give identical script, report.json and report.md to main.
- CI on de91438: see merge note.
