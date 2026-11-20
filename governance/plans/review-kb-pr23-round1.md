# Review of KB PR #23 (D-116 to D-120), round 1

Reviewer thread "Review KB decisions D-116 to D-120", 12 Nov 2026, ~23:10 UTC. Head reviewed: branch `kb/d116-output-69` (one file, `docs/kb/00-index/decision-log.md`, +5 lines).

Checked against: the coordinator's decision post (created_at 2026-11-12T22:47:40Z), `plans/issue69-output-plan.md`, and sci2audio PR #85 at bcc1045 (code read; `tests/unit/test_output_ffmpeg.py` and `tests/unit/test_output_faults.py` run locally: 26 passed in 1.28 s).

## What matches

- Status of all five: "Decided (Claude) (coordinator, 12 Nov 22:47 UTC, under D-80; Colin informed in the project chat at 2026-11-12T22:47:40Z)". The time equals the post's created_at.
- Post line 1 (WAV, 16-bit mono PCM, one rate, frame counts, sample-exact) = D-117. Matches `output/wav.py` and `write.py` (two streams: per chapter MP3, once for the M4B).
- Post line 2 (0.3 s between sentences, none at a clause cut) = D-116. "Of one block" in D-116 is the code's own term (`model.py`: "SENTENCE between sentences of one block"); fine. The code has no `Pause.CHAPTER`, and the first chunk of a chapter always gets the chapter pause, as D-116 says.
- Post line 3 (never overwrite unless asked, temporary name first) = D-119. `write.py` lines 81-86 match every claim: `FileExistsError` before writing, stale `.partial` files cleared, old read-along file removed first, read-along written last.
- Post line 4, second half (short real-ffmpeg tests in the fast suite) = D-118. `.claude/rules/tests.md` line 9 is the one added sentence.
- Post line 5 (licences) = D-120. Every version, flag and licence matches `THIRD_PARTY_LICENSES.md` "Bundled programs" and the plan's table.
- Cross references checked against the log: D-58 testing, D-61 core, D-80 autonomy, D-98 = Q4 cutter, D-99 = Q5 ffmpeg, D-102 = read-along. Q8 has no entry of its own, as D-116 says.

## Must fix

1. **Post line 4, first half, has no entry.** "ffmpeg is only allowed to open local files and pipes, never network addresses" was posted to Colin as a decision, but none of D-116 to D-120 records it. The code has it (`output/ffmpeg.py` line 21, `LOCAL_ONLY = ("-protocol_whitelist", "file,pipe")` on every input; tests `test_every_ffmpeg_input_is_limited_to_local_files` and `test_ffmpeg_refuses_a_network_address`). Suggested fix without a new number: add to D-120 one sentence, e.g. "Output opens every ffmpeg input with `-protocol_whitelist file,pipe`, so ffmpeg cannot open a network address even if a path looks like one (CLAUDE.md: no network call the user did not start)", and widen its subject to "…and how output runs them". A new D-121 is also fine if the author prefers, but check that no open PR has taken that number.

## Should fix

2. **D-118 "Output keeps six such tests (under 1 s in total)".** The six are the tests in `tests/unit/test_output_ffmpeg.py` (about 0.6 s here). The fault tests in `tests/unit/test_output_faults.py` also run the real binary on a few seconds of audio, so "six" undercounts. Name the file, e.g. "six such tests in `tests/unit/test_output_ffmpeg.py` (under 1 s in total), and the fault tests also run the real binary", so the count can be checked.

## Optional

3. D-116 opens with two parentheses in a row ("…plan (an implementation detail … Issue #69) (2.0 s before a chapter …)"). Reads more easily as "…plan (2.0 s before a chapter, …), which have no entry of their own and were set in sci2audio Issue #69."

## Merge

PR #22 merged as 1562e79, so #23 must be rebased onto main (text conflict at the top of the table only). Merge after fix 1 and fix 2 and the rebase.

## Round 2 (23:10 UTC)

Head 0de3063 (main 1562e79 brought in by a merge commit; diff against main is the five new rows only). Fix 1 done: D-120 subject widened, sentence on `-protocol_whitelist file,pipe` added, matching `output/ffmpeg.py` and `test_ffmpeg_refuses_a_network_address`. Fix 2 done: D-118 names both test files. Optional 3 done. Order D-120 … D-116 above D-115 is correct. Passed; squash-merged as deabf4f.
