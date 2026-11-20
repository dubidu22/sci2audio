# Flate-bomb test, D-682 isolation run on Windows (D-725)

Test: `tests/unit/test_extraction_pdf_process.py::test_a_flate_bomb_is_stopped_at_the_memory_limit_and_this_process_stays_small`

**Failures without a code cause:**
1. #481, 16 Nov 23:20Z, Windows (the three-system run);
2. #484, 17 Nov ~02:50Z, dispatch run 44005330346 on head 64adb70, Windows. The child process exited with status 1 and no stderr was captured. The pull_request run 44005281522 on the same head was green on Windows.

**Isolation run:** Actions run 44006516928 (17 Nov), workflow ci.yml dispatched from a scratch branch `ci/isolate-flate-bomb-d725`, which was main cfeb084 plus one edit to the tests job:
- windows-latest only;
- the test alone, 40 times: `uv run pytest -p no:cacheprovider -q <test>` in a loop.

The scratch branch could not be deleted from this session, because the proxy refuses ref deletes. It holds only that one workflow edit. Delete it on GitHub (Branches page) when convenient.



**Result: 0 of 40 failed** (1.6 to 2.3 s each).

**Reading.** The test does not fail on its own. It failed only inside the full fast suite, which runs with `-n auto` on the 4-core Windows runner, where other workers compete for memory and CPU. The likely cause is the memory limit or timing under load, not the code under test. Put this in the quarantine issue as its evidence (D-374, D-725).
