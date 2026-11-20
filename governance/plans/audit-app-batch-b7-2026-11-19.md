# Light batch audit: app batch B7 (19 Nov 2026)

Scope: the merged diffs of #577 (ee02e56: #442 part B, #187) and #583 (9333ce0: #493, #544), read together on main 9333ce0. I looked for cross-PR inconsistencies, contract touches and the user-file write path. The plan is plans/app-batch-b7-plan.md (D-772). Auditor: the app-lane review thread.

Result: **no defect found and no new issue needed.** #584 (the project folder name on another volume) is the one leftover, filed during #583.

## Cross-PR consistency (both changed `app/audio.py` and `app/job.py`)

- **Order in `run_audio_job`:**
  - The #577 stop (`unreadable`, line 471) comes right after `read_document` and before `voice_for`, `_check_targets` (line 496) and `_encode`.
  - So an unreadable PDF never reaches #583's name probes in the person's folder. Nothing is created there, not even a probe file.
  - In the web, `audiobook_folder` runs before the job, as for any failed first run (#577 N1).
- **Script job:** the analysis still runs on an unreadable PDF (#577). `script_files` (#583) probes the stem only for names with newer characters. The report with the `unreadable` key is written under the same, possibly retried, name that the web's `_script_files()` finds again on page load.
- **CLI:** `convert` stops with exit 5 before any probe or write. The `--with-script` pre-check (`cli.py` `script_files(...)`) probes only names with newer characters. The README and `--help` agree on exit 5.
- **CHANGELOG (D-768):** both lines are on main (Added: unreadable PDFs; Fixed: retried names), and #572's line is kept by the merge.

## Contract touches

- No layer contract, core dataclass, plugin or text-step interface changes, and `lint-imports` is green on main.
- New public names:
  - `sci2audio.app.UnreadableTextError` (a subclass of `UnreadableFileError`, so CLI exit 5 is unchanged in `cli.py`);
  - `sci2audio.output.audiobook_targets`;
  - `output.names.older`, `retried` and `refused`.
- `output/names.py` imports only the standard library.
- Report JSON: `unreadable` is added only when set, so the corpus goldens are unchanged. One CLI golden line changed (`--help`, exit 5), named in #577's body.
- Web error kind `unreadable-text` (en, de).

## User-file write path

- #583 is the only change that touches the person's folders:
  - names are decided once (`audiobook_targets`) for the check before speech, the writer, the take-back on failure and the records;
  - a hidden probe is made with O_EXCL only for names with characters newer than Unicode 3.2.
- CRIT-02 holds (review rounds 1 and 2, plus my probe for the script files).
- #577 adds no write. Its stop prevents writes.

## Notes (no action)

- B1: `legibility` now runs twice per PDF audio job (in the stop and, for the analysis, in `build_report`). Each is one pass over the text, which is cheap next to the voice.
- B2: the stop is decided on the whole document, not on the chosen chapters (D-762). If that should change, it is a product question for Colin.

## Out of scope, and issues

- #584 is open for the project folder name. #442 stays open for part 3 (recovery, Colin's roadmap call).
