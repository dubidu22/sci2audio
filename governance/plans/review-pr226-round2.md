# Review PR #226 round 2

Reviewed c53418e (the author's fixes on 76fd74a), 14 Nov 2026 ~01:35 UTC. Merge hold lifted by the coordinator at 01:27Z (release/1.0 = b25f192).

## Fixes

- **F1 fixed.** `app.js` `rememberedVoice()`: on Make, the settings PUT keeps the saved voice when it is a known option in another primary language; an empty or unknown saved voice, or one in the same language, is replaced by the page's voice. The job still uses the page's voice. New browser test `test_a_german_book_keeps_the_remembered_english_voice`: saved `bm_george` with language de → Thorsten preselected and spoken, saved voice stays `bm_george`; then on an English page `af_bella` is chosen and remembered. The author reports it fails on the old app.js. Logic checked by reading: matches the rule asked.
- **F2 fixed.** CHANGELOG says "(#211, VA-07)"; the PR body's Feature ID is VA-07 only.
- **F3 fixed.** `test_a_german_file_with_a_wrong_checksum_keeps_nothing`: wrong bytes of the right size for the German weights file give a DownloadError about the checksum; only that file was fetched; no target and no leftovers remain; `missing_files(["de"])` still lists it.

## Merge of main (done by this review thread)

Main had moved to b25f192 (release PRs #224, #225), and CHANGELOG.md and README.md conflicted. Merge commit 9d01b1f, pushed as a fast-forward (no force-push):
- CHANGELOG: the German voice line moves under `## [Unreleased]` → `### Added`, above `## [1.0.0]`.
- README: main's new install section kept. Step 3 now names both voice packs (355 MB English, 330 MB German), `voices download --language en|de`, and the rule that a text is read by a voice of its own language. The feature line says "28 English voices and the German voice Thorsten". The README test (`test_readme.py`) pins only the "What the rules do" example, which is unchanged.
- Locally on 9d01b1f: ruff check, ruff format --check and lint-imports are clean, and the fast suite gives **3413 passed, 1 skipped** (it now includes #222's German textprep tests).

## Verdict

Review passed. Merge by squash once CI on 9d01b1f is green.

## Merged

Squash-merged 14 Nov 2026 as 3715c38 (head 87f94fd, after main was merged in twice more for #232 and #228 with no conflicts; CI green on 87f94fd). Nothing deferred.
