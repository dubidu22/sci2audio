# Review PR #569, round 3 (final round, critical)

Reviewed: test-only fix commit **7704d3f**. Verdict: **approved, merged** as **5a605e5** (squash, pinned to 7704d3f). #470 closed.

## Round-2 items

| Item | Result |
|---|---|
| R1 ancestor swap | `test_s10_a_folder_above_swapped_after_the_check_is_seen_by_its_real_path`: the output folder is swapped for a link to the person's folder, which holds `.DS_Store` and copies of the audiobook files. Every file of the person's keeps its bytes, the moved folder keeps every file, and `kept` lists the folder and each file as `changed` with the project folder. It kills s2, and it ran on windows-latest (not skipped). |
| R2a s8 | The S5 test asserts the `folder` field. It kills s8. |
| R2b s9 | The S10 file-swap test asserts the `folder` field. It kills s9. |
| R2c j4 | Browser `test_more_files_stay_than_the_answer_names_and_all_are_counted` (KEPT_LIMIT+3 files). It kills j4 in Chromium. |

## Final-round checks

- **Product code:** none changed since d2f3acd (diff: two test files only).
- **Mutation:** clean baseline 180 passed, 3 skipped. 46 hand mutants on d2f3acd and 7704d3f (the same product code): 43 killed (28 of round 1, 11 new in round 2, and s2, s8, s9 and j4 now) and 3 equivalent (r15, r23, s3, as reasoned in rounds 1 and 2). I re-ran s2, s8, s9 and j4 on 7704d3f myself.
- **Nightly seeds:** not applicable (no Hypothesis tests).
- **Three-system run:** ci:full run 44418455912 and Linux run 44418448672 on 7704d3f are green on ubuntu, macOS and Windows, with Chromium browser shards, ZAP and CodeQL. One reported-only leg is red: WebKit 2/2 in `test_player.py::test_a_skipped_figure_shows_and_lights_up_its_notice` (wait_for_url timeout). This PR doesn't touch that test, it is known as #411, and the leg was green on d2f3acd.
- **MRG-03:** main 675d1c6 overlaps only in CHANGELOG.md, in another section, and merges cleanly, so I made no branch update.

## Notes

- N1 to N6 of rounds 1 and 2 stand.
