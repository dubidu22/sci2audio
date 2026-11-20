# PR #601 review, round 1 (head 7a87a97, base 678fe3c)

Web batch B17 (#299, #407, #381), non-critical. Verdict: **changes requested, one fix.**

## Checked
- Diff matches plans/web-batch-b17-plan.md. C3 holds: no web/strings line, app/report.py and document.html untouched; player.py change limited to the cache key and the shared helper `file_version`. api.py docstring only.
- CHANGELOG Unreleased has the #299 and #407 Fixed lines (D-768); #381 has none, as planned.
- #407 tests fail on main (main's player.py, both new tests red) and pass on the branch.
- Old files: `audiobook_stamp`, `audiobook_bounds` and `load_readalong` key on the same (st_ino, st_mtime_ns, st_size) triple as before for files older than RACY_NS, so no behaviour change there.
- #299 browser test fails on main's app.js ("Locator expected to be disabled", line 57) and passes on the branch; 10/10 local Chromium repeats green. It awaits the analysis report (`written` event) and the reloaded page's script (`#choose-all` enabled), the click waits for the reloaded page's enabled button, and the test awaits the PUT. No key chords, no pixel equality.
- #381 tests (a)–(c) and the renamed test match AC-381.1–AC-381.4.
- CI on 7a87a97: Linux tests, Chromium 1/2 and 2/2, lint, licences, security, ZAP, CodeQL, CI passed green; WebKit 1/2, 2/2 and Firefox 2/2 green (reported only); Firefox 1/2 still running at report time.

## Fix list (one fix commit)
1. **R1-1 (audiobook_stamp racy guard untested).** Mutant: in `audiobook_stamp`, key a fresh file on its stat triple instead of hashing it afresh (drop the `version is None` branch's `_hash16`). All of tests/unit with -k "stamp or readalong" stays green (23 passed). The plan names this guard as a behaviour change, so it needs a test failing without it. Add to tests/unit/test_web_player.py: a fresh read-along file (mtime now), call `player.audiobook_stamp(path)` once (primes `_stamp`), rewrite it in place with same-size content (`open("r+")`, same inode), restore the mtime with `os.utime(ns=(seen, seen))`, assert the stamp equals the new bytes' sha256[:16]. (The existing stamp assertion in `test_a_fresh_readalong_file_rewritten_in_place_is_read_again` is the first stamp call, so it never meets a cached value.)

## Notes (no change asked)
- The plan's step "change the speed first on the settled page" was dropped from the browser test; the awaited PUT plus `output_folder` (None by default) still show the choices are remembered. Fine as is.
- `app/config.py::file_id` keeps its own RACY_NS copy (layer rule), as the plan said.
