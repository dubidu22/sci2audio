# PR #601 round 1 answer (fix commit 309f516 on 7a87a97)

R1-1 fixed: `test_a_fresh_readalong_file_rewritten_in_place_is_read_again` (tests/unit/test_web_player.py) now asks for the stamp before the in-place rewrite (asserting the first bytes' sha256[:16], which primes `_stamp`), then after the same-size rewrite with the mtime restored asserts the new bytes' sha256[:16]. The reviewer's mutant (a fresh file keyed on its stat triple) fails it: 1 failed, 2 passed with -k readalong_file; the unmutated branch passes. Test-only change; no src change.
Local: test_web_player, test_web_library, test_web_outside 169 passed, 1 skipped; ruff clean.
