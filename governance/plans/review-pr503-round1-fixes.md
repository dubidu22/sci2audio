# PR #503 round 1: what was fixed

Fix commit deb732f (tests only, no source change), on 763595d.

- **S1, item 5 of plans/480-c2-tests.md.** Two new unit tests.
  - `test_web_listen.py::test_a_mark_across_the_cut_of_a_cut_sentence_is_drawn_in_the_joined_sentence`. The voice's cut falls inside the citation " (Okafor, 2021)", so the cut mark lies across the join. The joined sentence has the full parts: plain, said "milliseconds", the cut citation, plain. The parts join up to `shown(TEXT, *FIRST)`. It sits in `test_web_listen.py`, not `test_web_player.py`, because the edit-making steps (`_Edits`, `steps_with`) live there. Your mutant C1 fails it.
  - `test_web_player.py::test_a_word_joined_at_the_cut_of_a_cut_sentence_shows_joined`. The cut falls right after the hyphen of "con-\ntributing", which the hyphen step joined. The one joined piece reads "asking questions, and contributing code during COVID-19.". Your mutant C2 fails it.
- **S2.** Your probe case is added to `test_a_join_follows_only_the_chunk_the_page_draws_just_before_it`: "One two three, four five six.", spans (0,0,13), (0,4,9), (0,14,29), and chunk 2 joins. It expects elements `s0 s0 s2` and `sentence_starts == view.sentences == [0, 1, 2]`. Your mutant C4 fails it.
- **Mutants checked here, one at a time** against the web unit files. C1, C2 and C4 are each killed, by exactly the test named above.
- **Not done: the optional overlapping spans in the property test's generator.** The overlap rule is pinned by the case above. Drawing overlapping spans would also change what the property test's model has to reproduce for every other check. If you want it, it can be a follow-up issue.
- **Runs:** `tests/unit/test_web_*.py` 710 passed, 3 skipped; ruff check and format are clean.
