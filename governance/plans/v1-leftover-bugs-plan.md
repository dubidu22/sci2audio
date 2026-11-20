# Leftover v1.0 issues: triage and plan (D-443)

Thread "Clear leftover v1.0 bugs before release", 13 Nov 2026. Base: main 4bc809b (PR #194 merged).
All behaviour below was reproduced on 4bc809b with the full step chain (`run_steps`, strict).

## 1. Testing issues from 10 Nov

| Issue | Criteria on main | Action |
|---|---|---|
| #4 regression corpus + properties | Properties for every step (per-step tests plus `test_the_built_in_steps_never_fail_and_are_idempotent` over all built-in steps), 126 cases in `tests/regression/english.toml` run by one parametrised test, the 14 audit rows pinned by `test_the_14_audit_rows_are_all_there`, failures print a before/after diff (`testing.regression.diff`). PRs #83, #86, #94, #103. Known idempotence counterexamples are tracked in #159, #160. | Close |
| #6 conformance suite | `sci2audio.testing` has `check_text_step` and `check_voice_engine`: spans, step id + reason on every edit, declared languages, no network, `api_version`. Built-in steps pass in CI (`test_textprep_conformance.py`); Kokoro passes nightly on 3 systems (`test_kokoro_passes_the_conformance_suite`). PRs #83, #94, #88. Criterion 4 (docs for plugin authors) was always v1.1. | New v1.1 issue for the docs, then close |
| #9 voice round trip | `tests/integration/test_voice_kokoro.py`: slow WAV test, faster-whisper small round trip with WER limit 0.10, worst 3 sentences in the report, nightly on Linux, macOS, Windows, CPU torch on Linux, models cached. Last nightly (13 Nov): WER 0.008 / 0.012 / 0.012, all passed. PR #88. | Close |

## 2. The 13 review bugs

Reproduced readings (first run → second run where they differ):

| Issue | Input | Today |
|---|---|---|
| #109 | `Data at https://x.org/\nand more text follows.` | `Data more text follows.` |
| #110 | `the Olympics (2016) were held` | `the Olympics were held` |
| #145 | `( see Smith (2019))` / `It holds [12]. (See Smith (2019).)` | `` / `It holds. (See Smith.)` (nightly property red since 13 Nov) |
| #151 | `the CI: [1, 3].` / `two CIs [1, 3] and [2, 4].` | `the confidence interval.` / `two confidence intervals and references 2 and 4.` |
| #159 | `0­K`, `5­kg`, `5 ​mg` | `0K`, `5kg`, `5 mg` → second run reads the unit |
| #160 | `ﬀ´ℓˇℓ`; `5 x86K` | second run differs |
| #102 | `This holds (Smith, 2019, https://x.org/a).` | `This holds (Smith, 2019).` → second run `This holds.` |
| #111 | `See [12, 13] and (Smith, 2020).` | `See references 12 and 13 and.` |

### PR A, textprep batch (critical: adds English regression cases)

#109, #110, #145, #151, #159, #160. Each about an hour or less.

- #109 (`links._continues`): after `/ - _ ~ = & ? # %` the next-line word joins only if it holds `/ . _ - = ? #` or a digit, or is not in the English word list.
- #110 (`citations._names_before`): a year bracket after a word that follows an article is not a narrative citation, unless "et al." or a second author shows it is one.
- #145: the step is right (D-172 extended): a bracket of lead words and a narrative author-year citation goes whole; `(See Smith (2019).)` goes whole too. The property's "outside" filter learns the same; one regression case per row.
- #151 (`citations._numeric`): "CI:", "CIs", "CI =" before a bracketed pair mean an interval; a second pair joined by "and" after an interval is an interval too.
- #159: units and abbreviations steps run through `notation.through_unread` (small adapter from `Edit` to `Candidate`).
- #160: (1) the Unicode step composes an accent after a ligature it unfolds in the same run; (2) the units step pins one reading of `5 x86K` for both runs.

Golden files: new cases appended to `tests/regression/english.toml` (the issues require them); no existing `expected` line changes; the spoken scripts of the 7 corpus papers must stay byte-identical. If any of them changes, I stop and ask the coordinator.

### PR B, app batch (non-critical unless #118 joins)

- #104: the report's out-of-range line counts chapters from 1, as the table does; the JSON keeps 0-based indices in `ignored_chapters`. No snapshot changes (none in the corpus defaults).
- #118 only if the coordinator agrees to a golden change: its own criteria require the corpus report golden files to change (94 lines in `test_app_corpus.ambr` quote "“” → left out" or "“-” → left out"). A line break would show as "↵".

### To v1.0.1 (larger than small)

- #102: the link inside a citation bracket is taken by the links step, which runs first (D-167), so the fix crosses two steps and the overlap rule, and the "See <link> for the code," part needs a reading decision.
- #111: one citation run across a numeric and an author-year bracket needs a reading decision (read as "references 12 and 13 and Smith"? removed?) and changes both citation paths.
- #112: "every chapter" in `JobSettings` changes the job.json/audio.json records and resume comparisons; it is a speed improvement, not a bug.
- #117: the start token through a 0600 redirect file needs the file:// to http redirect checked in three browser engines on three systems, plus clean-up; low risk on a one-person desktop.
- #87: blocked upstream. kokoro 0.9.4 and misaki 0.9.4 (latest on PyPI, checked 13 Nov 21:40 UTC) still declare `<3.13`. The README pipx note stays; check again before #80.

## 3. Decisions needing D-numbers (coordinator assigns)

1. #145: a bracket of lead words and a narrative author-year citation goes whole, like D-172's numeric one.
2. #110: an article before the word before a year bracket makes it not a narrative citation, unless "et al." or a second author.
3. #109: a next-line word joins a URL cut after `/` etc. only if it looks like a path.
4. #151: "CI:", "CIs", "CI =" before a bracketed pair, and a second pair after "and", are intervals.
5. #102, #111, #112, #117, #87 move to v1.0.1.
