# Review: PR #251, round 2 (final commits before the merge, D-570)

14 Nov 2026 ~16:30 UTC on head 27165ec (base release/1.0 ca52ab3).

Checked and correct:
- 27165ec: `## [1.0.0] - 2026-11-14`, which passes release.yml's date guard.
- 8483525: `Homepage = "https://sci2audio.com"` dropped from [project.urls], because Colin retired the domain (plan s.5 step 6). Repository and Issues URLs stay; uv.lock does not hold the URLs.
- 1e4ed6e: the sheet's date, listener and device. Colin's acceptance is quoted word for word from his 16:23 message. There are no made-up scores, and the sheet says why. The issues it names exist: #280, #285, #286 and #295 (v1.0.1, closed), #296 (v1.2), #314 (v1.0.1, screen reader).

F1 (fix needed): the M4B-check note says "The release workflow's smoke test checks that the M4B is written". That is false: `scripts/release_smoke.sh` runs `sci2audio script` offline (no voice, no audio, no M4B). What does write an M4B is the nightly `tests/integration/test_cli_end_to_end.py`: `sci2audio convert` with the real voice on all three systems, which also checks the EPUB's cover in its M4B with ffmpeg. Fix the sentence to say that, or just "not checked by hand for 1.0.0".

Round 2 F1 fixed in 7fd4aa3 (only that sentence changed; the dated heading is unchanged). **Approved.**

**Merged** into release/1.0 by squash pinned to 7fd4aa3 (all CI green, draft flag cleared first): b787309 (~16:32 UTC). Not yet forwarded to main (main red, D-568).
