# Light audit: web batch B17 (2026-11-19)

Batch: one PR, #601 (#299, #407, #381), squash-merged ff7bf8d on main b32612d. Reviewer: B17 review thread (Opus medium). Scope: the merged diff, cross-PR consistency and contract touches only.

## Findings: none blocking, no new issue
- Contract touches: none. No core dataclass, no layer contract, no golden file, no regression case, no docs/readalong-format.md change; lint-imports green. C3 held: no web/strings line, app/report.py and document.html untouched by #601 (main's document.html change came from #598, app lane, and does not touch `#make` or `data-events`).
- Cross-lane: the only conflict with the parallel lanes was CHANGELOG.md (#593/#598 Fixed lines), resolved by the author's merge of main keeping every line; the PR diff against main was otherwise unchanged (checked file by file except CHANGELOG).
- Cache keys: after #601 every stat-keyed cache in web/ (`audiobook_stamp`, `audiobook_bounds`, `load_readalong`) uses `file_version` (ino, mtime_ns, size, racy guard). No other web/ cache keys on mtime+size (web/figures.py uses mtime only to order crops for pruning). `app/config.py::file_id` keeps its own RACY_NS copy and `app/audio.py` keys on (dev, ino, size, mtime_ns): two copies of the same rule across the app/web boundary, which the layer rules require. Noted, no change.
- #299: the one-line disable runs only on pages drawn with `data-events`; if the event stream is lost the page already says the server can't be reached, and a reload enables Make. Acceptable.
- Reported-only WebKit legs failed once each on 309f516 (make_audiobook wait_for_url; listen timeline seek), green on re-run, untouched tests: #437 instability, not a batch defect.

## Ledger
Review: 2 rounds, 1 finding (R1-1 untested racy guard in audiobook_stamp), 0 deferred, 1 CI re-run (reported-only WebKit, by the author). Post-merge defects: none known.

## Post-merge (04:30Z)
main went red on Windows after ff7bf8d: the two new #407 tests wrote the read-along with write_text / open("r+"), and Windows turned "\n" into "\r\n", so the size and hash assertions failed (src correct). The PR ran Linux only (non-critical). MRG-04: the author's test-only fix #610 (write bytes, ci:full green on three systems) merged as fc076e9; main CI green on all three systems (run 44457554324). Lesson: a test that compares a file's size or hash writes bytes, never text.
