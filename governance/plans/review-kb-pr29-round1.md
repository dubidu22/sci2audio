# Review: sci2audio-design PR #29 (D-149 to D-153, issue #65), round 1

Reviewed 13 Nov 2026 against the coordinator's decision post (2026-11-12T23:36:27Z), plan
`plans/issue65-unicode-hyphens-plan.md` §3 U1 to U5, and the code of sci2audio PR #98 (head 7502486).

Result: **pass, no fixes needed.** Merged by squash.

| Row | Plan | Matches post | Matches plan | Matches code |
|---|---|---|---|---|
| D-149 | U1 | yes (no word list, own spelling, compound signals, two short lists) | yes; figures updated to the final code (488/495, 7 misses, 374 by own spelling), explained in the PR body | truth file has 495 hyphens, 7 `[[miss]]` tables, header says 374 of 495 |
| D-150 | U2 | yes | yes | `BUILT_IN_STEPS` ends with `unicode-clean-up`, `line-end-hyphens`; `test_characters_and_hyphenation_run_last` |
| D-151 | U3 | yes | yes | `spoken_text` collapses `\s+` (Unicode white space); `odd-spaces` regression case; ZWJ/ZWNJ kept |
| D-152 | U4 | yes | yes | issue #96 open, milestone v1.1 |
| D-153 | U5 | yes | yes (ˆ only inside a word, ı/ȷ, stray accents, apostrophe acute left) | `characters.py` and its tests cover each case |

Other checks:
- All five rows "Decided (Claude)", "Colin informed" 2026-11-12T23:36:27Z, matching the post.
- D-150 refines D-105: correct, D-105 sets the fixed coarse-to-fine registry order. D-105's status
  cell gains "; **refined by D-150**", the same pattern the log already uses (e.g. D-121).
- Placement: newest first, D-153 to D-149 directly above D-141; six cells per row.
- PR body references sci2audio PR #98 with "See ...", no closes/fixes/resolves.
- KB PR #28 (D-142 to D-148) is still open; it must place its rows between D-149 and D-141
  when it resolves the conflict.
