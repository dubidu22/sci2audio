# Review PR #421, round 1 (non-critical: Voices, Privacy, Not found, the removal disclosure, #390)

Head reviewed: **3cd37cf** (52adfd9 with #420's branch 980911d merged in). The diff is against #420's head, as stacked. One round at medium depth; at most two.

**Verdict: approvable once it carries #420's fixes. One small test is asked.** The restyle keeps the behaviour, and the removal still asks the same confirmation.

## What I checked

- **The removal keeps the same confirmation path (D-359 to D-362).** It is still a `<details class="remove">` disclosure, and the press of its one button is the confirmation. That button:
  - is still `<button type="button" class="… remove-now">`, with the same `data-document` and `data-audio`;
  - is still found by `app.js` with `button.remove-now` (line 180, unchanged);
  - is still replaced by the busy note while a job works on the document (its test now checks the new class string).

  The summary only gains classes, an aria-hidden icon and a `<span>`. The new browser test removes the document by keyboard on the document page and checks the request and the folder.
- **The danger button:**
  - The wording is unchanged: "Remove {name} now" / "{name} jetzt entfernen". It names the document, as before.
  - `button.danger` exists since batch A: error colour with an outline in that colour, so the warning is not carried by colour alone.
  - The sprite has no trash icon, so the summary uses `x`. That's fine.
- **No internet:**
  - The only new links are `/` and `/privacy`.
  - No inline style, no `//`.
  - Batch A's no-internet test passes over the new templates.
- **Voices:**
  - One panel per pack. Each file appears once, in its own pack, with its licence (new unit test).
  - The consent checkbox stays `required`, with the same form, digest and job page.
  - The download button names the size still missing. That is right, because the download skips files already in place (`voices/download.py`).
- **CSS:** batch A's tokens only (`--desk-2`, `--rule-strong`, `--error`, `--wait-wash` through `.note`), no hard colours.
- **Runs on 3cd37cf:**
  - Web unit tests: 241 passed, 2 skipped. The files were test_web_pages, test_web_remove, test_web_languages, test_web_design and test_web_library.
  - Browser (Chromium): 22 passed. The files were test_quiet_pages, test_remove, test_listen_outside, test_library and test_axe.
  - PR checks: all green, including CI passed.

## Findings

**N1. The size on the download button is tested only when nothing is installed.** There, missing equals total. A mutant `size=missing` → `size=total` in `voice.html` passes the unit tests (`-k "voice or setup or download"`: 292 passed).

## Fix list

1. N1: add a unit test with the English pack installed and the German one missing. The button must say "Download the voice (<German size>)", not the total.
2. Merge #420's round 1 fixes into this branch with a merge, never a force-push. #420's S1 changes `privacy.work`, which this PR also changes ("The library and each document's page…"), so keep both changes in English and German.

## Next round

Round 2 checks only the merge of the fixed #420 and the N1 test.
