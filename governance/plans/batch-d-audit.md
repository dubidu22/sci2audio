# Working Reader batch D: light batch audit (D-627, workflow rule 6)

Scope: #444 (D1, 71ca0aa), #446 (D2, 12fd90d), #451 (D3, 1bace26) on main 1bace26, read as the merged diff of the three squash commits (the textprep PR #436 and docs PR #453 in the same range are left out). Plan: plans/working-reader-batch-d-plan.md (D-704). Cross-PR inconsistencies and contract touches only; no PR re-reviewed, no code changed, no issues opened. Audited 16 Nov 2026 ~17:45Z.

**Result: 5 findings. Contract touch 0, inconsistency 2, cosmetic 3.** Batch sound. One finding (F1) is a small user-visible keyboard defect that I would put in an issue; the rest are notes.

## Findings

### F1. P leaves the focus on the panel button, so Space and the arrows stop being shortcuts (inconsistency, D1 × D3)
- `src/sci2audio/web/static/player.js:459` (D3): the P key presses `#panel-toggle` with `.click()`.
- `src/sci2audio/web/static/player.js:625` (D1): `set(false)` moves the focus to the toggle on every close, wide windows included (written for the button and the narrow overlay, before keys existed).
- `src/sci2audio/web/static/player.js:446`: Space and ←/→ on a focused control do what the control does.
- Together: at 1280 px or wider, P closes the panel and the focus lands on the toggle. The next Space opens the panel again instead of playing, and ←/→ do nothing until the person clicks elsewhere. The same holds after leaving Focus with F or Esc (focus returns to `#focus-on`, line 414, so Space re-enters Focus), but that return is what the plan asked for.
- Not covered: `tests/browser/test_focus.py::test_every_key_on_the_listen_page` presses P, P, then F; it never presses Space or an arrow after P.
- Suggested issue (coordinator decides): a P press should not move the focus (toggle through `set()` without the focus step when the key, not the button, closed it), with a browser test "P then Space plays".

### F2. The CLI and the web card read D-695 differently at a chapter's end (inconsistency, D2 vs batch C)
- `src/sci2audio/cli.py:641`: the CLI line names the chapter of the sentence just spoken (`chapter_number`), never stepping on `chapter_done`.
- `src/sci2audio/web/pages.py:706` (`_stopped_in`) and `src/sci2audio/web/static/app.js:667` (`chapterNow`): the web steps to the next chapter when `chapter_done` is set.
- The D2 plan asked for the stepping reading ("the same reading as the web card"); review #446 round 1 accepted the deviation as consistent with D-695. Both readings are correct for what each line shows (CLI: the chapter whose sentences are counted; card: where the job stands). Note only, no issue needed; worth one line in the KB so a later thread does not "fix" one to match the other.

### F3. Changes counts include edits the sheet deliberately does not mark (cosmetic, D1)
- `src/sci2audio/web/player.py:650` (`_changes`) counts every accepted edit in a read block.
- `src/sci2audio/web/player.py:669` (`_marks`) leaves out line-end hyphen joins, blocks cut whole, replacements that look like the print, and edits inside placeholders read as a notice.
- So a category can show "26 changes" with nothing struck on the sheet (e.g. unicode clean-up on nowak). The panel hint says "the changes this audiobook was made with", so the count is defensible. Note only.

### F4. Settings cookies: same handling, slightly different plumbing (cosmetic, D1/D3)
- Setting is uniform: one loop in `choose_appearance` (`pages.py:1306-1313`), each value through its `known_*` allow-list, same cookie flags (path /, SameSite strict, HttpOnly, COOKIE_AGE). Reading: `theme_of` and `keys_of` go to every page through `_page` (`pages.py:189-190`), `announce_of` is passed by hand to Listen and Settings only (`pages.py:1118`, `1284`). Defaults differ on purpose (announce off, keys on).
- Leftovers: `settings_page` docstring (`pages.py:1273`) still says "Appearance, language and announcements"; the keys form's Save button reuses the `settings.announce_save` string (`settings.html:71`). Note only.

### F5. Search query cap only on the server (cosmetic, D2)
- `src/sci2audio/web/pages.py:398` cuts the query to 200 characters; `librarySearch()` in `app.js` does not. A query over 200 characters filters differently with and without the script. The folding itself is the same in both (`library.folded` and `app.js folded`: lower case, NFKD, marks dropped, ß → ss), and both compare against the one server-made `data-find` text. Negligible.

## Checked, no finding

- **Contract touches: none.** No file under `sci2audio/core`, `textprep`, `layout`, `extraction`, `output`, CI, packaging, golden or regression data changed in the three commits. `player.py` only imports `EditKind` and `Status` to read the run. `AudioRecord.made_with` is a web-side field reading the existing `sci2audio` key that `app/audio.py:826` already writes; no record format changed. The CLI line text changed ("Speaking chapter N of M"); no document pins it, and its test was updated.
- **Version guards.** The two guards are separate and each lives in one place: position.json is keyed by the read-along stamp (`player.py:246-265`, #153), the marks by `audio.json`'s version (`player.py:574`, D-704b). Listen's counts are hidden exactly when the marks are (`count=None`, template `listen.html:144`). Consistent.
- **Keys versus Focus, panel and dialogs.** One shared `typing()` (app.js) serves `?` and the Listen keys; both handlers skip when a dialog is open and when Ctrl, ⌘ or Alt is held; Esc leaves Focus before the typing rule and with the keys off; the panel's own Esc runs first and its `preventDefault` stops the page handler; P is ignored in Focus; the scroll-by-hand listener skips keys the shortcuts took. Data-keys off removes the single keys and their hints (`base.html`, `listen.html:80-81`, `:122`) and keeps Esc and the rail item.
- **Drawn disabled.** Every new server-drawn button wired by script is drawn disabled and enabled when wired: dock, timeline, Focus on/off, chapter buttons, panel toggle/close/tabs, voice Play, rail shortcuts item, sheet close. Drop hint shown only once wired.
- **Duplicated state logic.** `clock()` (pages.py:1045) and `clockOf()` (player.js) give the same strings; dock ticks are server-only; the search text is made once on the server. No EventSource is opened by page load (voice samples follow a job only on click).
