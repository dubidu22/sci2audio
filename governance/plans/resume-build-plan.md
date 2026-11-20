# Plan: resuming a paused audiobook build (Colin, 17 Nov 08:24Z) — CRITICAL

Main 3c7482f. Lane app (+ web: the job card and app.js; not player.js, not the Listen page).

## 1. Diagnosis (reproduced on main with the fake voice and real ffmpeg)

Reproduction: finished build exists → "Hörbuch erstellen" → output-exists card → "Diese
Dateien ersetzen" (POST overwrite=true) → Pause after 3 of 6 sentences → Resume.

| Step | Result on main |
|---|---|
| Output folder after Pause (mid-speech) | the earlier finished .mp3/.m4b/.readalong.json, untouched |
| Resume (app.js `restart(false)`) | job fails at once: `output-exists`, the card in Colin's screenshot |
| "Diese Dateien ersetzen" | done: **reused 3, spoken 3** (voice called only for the 3 missing sentences) |
| "Sprachzwischenspeicher leeren" | deletes every spoken sentence: **real loss**, one click, no confirmation |

So: **progress is not lost with "Diese Dateien ersetzen"**; it is lost only with the cache
button, which the card puts right next to it. The files named in the warning are **not
partial output** of the paused run: the audio job writes the audiobook only after the last
sentence is spoken (`run_audio_job` → `_encode`), and a cancelled encode removes the files
it newly made (`_remove_new`). They are the earlier finished audiobook the person already
agreed to replace.

**Cause:** Resume posts `overwrite: false` (app.js `job-again` → `restart(false)`), while the
paused run was started with `overwrite: true`. The server keeps no record of that choice
(`JobRecord` has settings, not overwrite), so the page cannot carry it. Every paused
*replace* run therefore hits the existing-files check (D-163) again on Resume. A paused
*first* build is not affected (test_cancelling_while_speaking_keeps_the_chunks covers that).

Also checked:
- CLI: Ctrl-C says "run the same command again to continue"; the same command carries
  `--overwrite`, and chunks are reused. Not affected; no change.
- position.json / audiobook.json: written or removed only after a successful run
  (`tasks.audio_work`); Pause and Resume leave both alone. Not affected.
- Pause during the *encoding* phase of a replace run: output removes the old read-along
  first (D-119, documented), so the old set is already broken; Resume must then go on
  without asking. Covered by the fix below and a regression test.
- Server restart after Pause: the paused card is gone (jobs live per server run); the next
  "Hörbuch erstellen" asks once, which is right for a finished earlier build. Replace then
  reuses the cache.

## 2. Fix

1. `web/jobs.py` `JobRecord` keeps `overwrite: bool` (audio jobs; False for others);
   `snapshot()` and `models.JobOut` gain `overwrite` (additive API field).
   `api.start_job` passes `body.overwrite`.
2. `_making.html`: the card carries `data-overwrite`; app.js Resume / "again" posts the
   paused job's own `overwrite` instead of `false`. Result: a resumed replace run never
   shows the existing-files card; a resumed first build still sends false, so a file that
   appeared from elsewhere meanwhile is still refused.
3. The existing-files card keeps its confirmation (genuinely finished earlier build), but:
   - no cache button on it (clearing the cache is never needed to replace, and it is the one
     button that loses the spoken sentences);
   - when the cache holds sentences it says so: "Die bisher gesprochenen Sätze bleiben
     erhalten; Ersetzen spricht nur, was fehlt." (EN + DE strings).
4. The cache button on the paused/failed/done cards goes behind the same confirm box the
   Cancel button already uses (#433, D-694): it names what is lost ("N gesprochene Sätze,
   X MB") before the DELETE. *(Safety mechanism; recommended. If you prefer to keep this PR
   to the bug only, I drop item 4 and file an issue.)*

No change to the app layer, the output contract, the chunk cache, the CLI or player.js.
Overlap with #503: none in files (it changes api.py's marker routes, player.py, player.js);
I touch api.py only in `start_job` (one argument). If both touch CHANGELOG.md, the later
PR merges main.

## 3. Tests (each fails on main)

- `test_web_audio.py`: finished build → replace run paused mid-speech → the job JSON says
  `overwrite: true` → Resume as the card sends it → done, no `output-exists`,
  `reused == chunks_done at pause`, voice called only for the rest.
- Regression, partial-files case: replace run paused during encoding (gate in the fake
  ffmpeg) → Resume → done, complete new set incl. read-along.
- Kept: a plain start over a finished build still fails `output-exists`; a resumed first
  build still sends `overwrite: false` and is refused if a file appeared meanwhile.
- `test_web_prepare.py`: card has `data-overwrite`; exists card has no `cache-free` and
  shows the kept-sentences line; free button sits in a confirm box.
- Browser (`tests/browser`): replace → Pause → click Resume → lands on a running/done job,
  never the existing-files card; the cache confirm box opens on click, DELETE only after
  confirming; axe clean.

Known-errors entry: none applies (that list is for reading errors). Labels: `lane:app`,
`lane:web`, `risk:high`, `bug`, milestone v1.3 (a v1.3 job card defect). Author `ci:full`
before hand-off. Size: ~60 lines of code, ~250 lines of tests.
