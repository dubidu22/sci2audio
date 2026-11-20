# KB batch for the next KB PR (pending)

Collected by the KB thread. D-742 to D-769 were merged as KB PR #55 (74640aa, 18 Nov 23:07 UTC). The next KB PR is the one for 20 Nov (one per day, D-626), branched from sci2audio-design main 74640aa or later, merged by the KB thread without review.

## Decisions

### D-795 (19 Nov 2026) Decided: ship to testers first (Colin)
- Colin, 19 Nov 06:54Z: "It's ok if the product is not perfect. I want to get to the point faster, where i can tell others about it, let them install it and gain feedback." Approved the coordinator's proposal at 06:58Z: "lets do it like that."
- Only the running batches finish in v1.2: B9 (#414 #415 #402), B13 (#156 #238 #322 #354), B14 (#175 #328 #329 #602).
- Next: installers for macOS, Windows and Linux with the app window and smoke tests (#215, #13), then tag and publish (publishing parked by D-721 resumes). Plugin interface (#216, #203) and update check (#217) stay out of that release (milestone v1.4).
- New milestone v2 (#10), "Improvements deferred until first tester feedback". Moved to v2 on 19 Nov ~07:05Z: 51 issues from v1.2.x (now empty), 11 from v1.2 (B10 #379 #405 #150, B11 #292 #249 #468, B15 #355 #367 #356, B18 #618 and #442), 11 from v1.0.1 (now empty). #602 moved v1.2.x to v1.2 (B14). Nothing closed.
- Counts after: v1.2 11, v1.3 1, v1.4 20, v1.5 7, v2 72, Later 16.

### D-796 (19 Nov 2026) Decided (Claude): quarantined tests block the tester release
- The standing rule holds: a quarantined test is fixed before the next release. #525 (quarantined Windows keep-alive test) moved from v2 back to v1.4, the installers release, commented as a release precondition. #437 stays in v1.3: it tracks the reported-only WebKit nightly leg, not a quarantined test; its acceptance waits on #502.
- Details: plans/roadmap-share-first-2026-11-19.md. Supersedes the #442 part 3 open point below (deferred to v2).

## Open points carried over (no D-number yet)
- #442 (v1.2, P1, lane:extraction): part A merged (#562); part B in B7; part 3 (glyph-ID recovery) is Colin's roadmap call (D-761).
- Colin still to confirm the Kehren motto (PR #476, D-719).
- App PR 3 (#569, #470) was open at 23:05 UTC on 18 Nov; record its merge.

Next free D-number: D-770.

- D-830 (19 Nov 17:12Z, Decided (Claude), recorded): sci2audio 1.4.0 released. Colin approved the PyPI deployment; release run 44547770638 green end to end. GitHub release v1.4.0 (tag 083d0bc on 5c18f8c) carries the macOS dmg, Windows setup.exe, Linux AppImage, source archive (FFmpeg, LAME, espeak-ng), wheel, sdist and SHA256SUMS.txt; 1.4.0 on PyPI. All lanes closed; v2 backlog waits for tester feedback and Colin's next ask (D-795).
