# Roadmap: share first (19 Nov 2026, D-795)

Decided by Colin, 19 Nov 2026 06:58Z ("lets do it like that", cmsg_011gr2YyZJypGaV6NbzgSXQE4x4sXTrVCmWBkZ4DBnKEMY), on his 06:54Z message: the product does not need to be perfect; get to the point where others can install it and give feedback.

## New order

1. Finish the three batches already running, nothing else in v1.2:
   - B9 textprep (PR #621): #414 #415 #402
   - B13 layout (PR #620, PR 3 #354, PR 2 #322): #156 #238 #322 #354
   - B14 extraction (PR #609): #175 #328 #329 #602
2. Installers batch (app/release lane, critical, plan first, Opus high): macOS, Windows and Linux installers with the app window (#215) and smoke tests on three systems (#13). Then tag and publish; the publishing parked by D-721 resumes with it.
3. Testers install it; collect feedback.
4. v2 holds everything else until feedback says what matters.

Not in the tester release: public plugin interface (#216), plugin conformance docs (#203), update check (#217). They stay in milestone v1.4.

## Open issues per milestone after the moves (19 Nov ~07:05Z)

| Milestone | Open issues | Note |
|---|---|---|
| v1.2 (#4) | 11 | B9, B13, B14 only |
| v1.3 The Working Reader (#8) | 1 | #437 WebKit nightly flake |
| v1.4 (#5) | 20 | #215 #13 installers; #525 quarantined Windows test (release precondition, D-796); #216 #203 #217 plugin/update check (stay out of the tester release); 14 layout/extraction/web items |
| v1.5 Study layer (#9) | 7 | unchanged |
| v2 (#10, new) | 72 | improvements deferred until first tester feedback |
| Later (#6) | 16 | unchanged |
| v1.0.1 (#3) | 0 | emptied |
| v1.2.x (#7) | 0 | emptied |
| v1.1 (#2) | 0 issues | only the parked release PR #426 |
| v1.0 (#1) | 0 | |

## What moved

- New milestone v2 (#10): "Improvements deferred until first tester feedback (D-795)".
- From v1.2.x (#7), 51 issues to v2 (#525 then went on to v1.4, see below, so 50 stay in v2): #628 #627 #626 #625 #624 #623 #622 #619 #617 #615 #614 #613 #612 #608 #607 #606 #605 #604 #603 #599 #597 #596 #595 #594 #592 #591 #590 #589 #588 #587 #586 #584 #581 #580 #579 #578 #576 #573 #571 #570 #567 #566 #565 #564 #563 #540 #531 #525 #517 #346 #296 
- #602 moved from v1.2.x to v1.2, because it belongs to the running B14 batch (PR #609).
- From v1.2 (#4), 11 issues to v2: B10 #379 #405 #150; B11 #292 #249 #468; B15 #355 #367 #356; B18 #618 and its parent #442 (comments on #442 and #618 say part 3 is deferred to v2; the B18 plan, D-789, stays on file).
- From v1.0.1 (#3), 11 issues to v2: #314 #260 #255 #252 #246 #209 #117 #112 #111 #102 #87 
- v1.1 (#2) had no open issues, only the parked draft release PR #426, which was left as it is.
- Nothing was closed.

## Points to note

- D-796 (coordinator ruling, 07:03Z): quarantined tests are fixed before the release. #525 (Windows keep-alive event test, quarantined) moved from v2 to v1.4 as an installers-release precondition. #437 (WebKit nightly pattern, v1.3) was left in place: it tracks the reported-only WebKit leg and no quarantine of it was found; its acceptance waits on #502.
- v1.4 still holds 14 layout, extraction and web items besides the installer and plugin issues; they were not part of this move.
