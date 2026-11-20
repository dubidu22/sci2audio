# Review PR #495, round 1 (#480 C1: the pieces of a cut sentence are joined), CRITICAL, final round

Head reviewed: c7b6f98 on main 5812d2d, branch `app/joined-sentences-c1`, 14 files, +939 −37. Plan: plans/480-joined-sentence-plan.md, approved as D-730 (C1 critical: the read-along format document is a contract). The author's `ci:full` run on c7b6f98 is green on all three systems: `tests (macos-latest)`, `tests (windows-latest)`, `tests (ubuntu-latest)`, plus browser (Chromium), ZAP, CodeQL, licences, lint and layers, security and `CI passed`.

**Verdict: approvable.** No findings. All final-round checks (mutation, nightly seeds, the branch nightly, three systems) are done in this round, so this is the final round.

## What I checked

### Against the plan and D-730
- **`Pause.CLAUSE`** sits between NONE and SENTENCE. `OutputSettings.clause_pause` is 0.25 s, checked in `__post_init__` and mapped in `pause_of`. `plan_audio` gives CLAUSE to every `continues` utterance, and a `pause` edit inside a cut sentence still wins through `strongest`.
- **The trim.** `edge_trim` works in 10 ms frames. A frame counts as quiet when it is more than 45 dB under the chunk's own peak. Each trim keeps 30 ms and cuts at most 0.8 s per side. A chunk that is all silence is never trimmed. `_trim_joins` trims only the start of a CLAUSE chunk that does not begin a chapter, and the end of the chunk before it. The trim happens while the chunks are assembled: the speech cache on disk is untouched. `frames_of` streams only the kept frames, and the timeline places `kept` frames, so read-along times stay exact by construction.
- **The read-along file.**
  - `"joins": true` is written only on a chunk that continues a sentence, and the version stays 1.
  - `from_json` defaults the key to false and refuses a non-bool value with `ReadAlongError`.
  - `docs/readalong-format.md` has the new row, a "Joined chunks" section and a Changes note.
- **Old and new readers (D-730).**
  - `tests/unit/readalong_v1_0.py` is the v1.0.0 reader. It is identical to the tag apart from its docstring, and it reads a new file with `joins`.
  - The new reader reads an old file with no `joins` key as all false.
- **A skipped piece** passes `continues` on, as it passes its pause. `linked` is reset at a chapter change.

### Mutation (23 hand mutants, run one at a time from a clean tree with `scratchpad m490/mut495.py` and `run495.sh`)
- **21 killed**, each by a test aimed at it: the keep floor and the cap, the −45 dB level both ways, one-sided trims, the start/end swap, `kept` against `frames` in the timeline, `setpos` skipped, the all-silence guard, CLAUSE→NONE in `plan_audio`, `clause_pause` mapped to 0, the `__post_init__` check, the enum order, chapter firsts, `joins` dropped or defaulting to true, and the negative-skip guard.
- **2 equivalent:**
  - **T2**, `>=` against `>` at the quiet level: the two differ only when a frame's peak equals the level exactly. Samples are 16-bit integers, and the level is `peak * 10 ** (-45 / 20)`. An exhaustive check of every peak from 1 to 32768 finds no integer level, so no frame can equal it.
  - **T11**, no reset of `linked` at a chapter change. A chapter's first utterance never has `continues` (textprep never cuts across a chapter), so `linked` is already false there. `write.py` also excludes chapter firsts from `joins`.

### Nightly seeds
`HYPOTHESIS_PROFILE=nightly`, seeds 2024 and 123456, on the 12 files that cover the output, the read-along and the audio plan (`test_output_joins.py`, `test_app_audio_plan.py`, `test_app_audio_job.py`, `test_app_audio_faults.py`, `test_output_{faults,ffmpeg,long,parts,subtitles}.py`, `test_web_{listen,player,position}.py`): 282 passed for each seed.

### The branch nightly, with real voices (run 44031738776 on c7b6f98)
- **`test_joined_sentences.py`** passed in English and German on ubuntu, windows and macos. It measured **0.310 s** at the cut on every system, against the 0.78/0.80 s English and 0.56/0.58 s German measured before. The bound is `clause_pause` + 0.1 s.
- **Property-based tests (many examples)**, benchmarks and browser (Chromium): green.

### Red jobs against main fc7406a (D-731, main nightly run 44032949050)
Every test that fails on the branch also fails on main. Main's WebKit macOS job has one more failure, `test_markers.py::test_add_note_over_the_page_and_the_panels_keyboard_order`; that test comes from #490 and is not on the branch.

| job | failing on the branch (c7b6f98) | failing on main (fc7406a) | match |
|---|---|---|---|
| slow tests, ubuntu / windows / macos | `test_cli_end_to_end.py::test_convert_reads_an_epub_and_keeps_its_cover` | the same on all three | yes |
| browser (webkit, ubuntu) | `test_listen.py::test_below_1280_px_a_click_on_text_inside_the_panel_leaves_it_open` | the same | yes |
| browser (webkit, macos) | 10: `test_focus.py` (four tests), `test_library.py` search, `test_listen.py` (four tests), `test_player_speed.py` by keyboard | the same 10, plus the `test_markers.py` test | yes |
| browser (firefox, ubuntu) | 3 failures (mark colour, dock, speed select) and 1 error (`test_player_position.py`, next run offers to continue) | the same 3 and the same error | yes |

No #495 file is in any of these tests' paths: they cover the EPUB cover and browser behaviour from #489, #451 and earlier. As D-731 says, the author thread files the untracked ones.

### Base
- Main has moved to fc7406a (#490). `git merge-tree` of main into c7b6f98 is clean (tree 62d018e), and the two diffs since 5812d2d touch no common file.
- The fast suite on that merged tree: 6987 passed, 3 skipped (read-only as root, junctions, one platform skip).

## Merge
- Merge main fc7406a into the branch (a merge, not a rebase).
- Confirm that `git diff fc7406a <new head>` equals the reviewed diff.
- Add `ci:full` and wait for `tests (macos-latest)`, `tests (windows-latest)` and `tests (ubuntu-latest)` to be green on the new head (rule 8).
- Squash-merge, pinned to that head. #495 does not close #480: C2 does.

## Done
- Main fc7406a merged into the branch: head **19afadc**, tree 62d018e (the tree I tested). `git diff fc7406a 19afadc` is byte-identical to the reviewed `git diff 5812d2d c7b6f98`.
- Green on 19afadc: `tests (macos-latest)`, `tests (windows-latest)`, `tests (ubuntu-latest)`, browser (Chromium), ZAP, CodeQL, licences, lint and layers, security and `CI passed`.
- Squash-merged, pinned to 19afadc. Main is now **3c7482f**, and its tree is identical to the reviewed head's.
- #480 was closed by the merge, because the PR body says "C2 ... closes #480" and GitHub reads that as a closing keyword. I reopened it: C2 closes it.
