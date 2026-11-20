# Review PR #503, round 1 (#480 C2: a cut sentence is one sentence on the page and for markers)

Head reviewed: 763595d, one commit on main 3c7482f (#495). Non-critical per D-730, lane:web, 7 files, +564 −23. Plans: plans/480-joined-sentence-plan.md section C2 and plans/480-c2-tests.md. Linux CI is green on the head, including browser (Chromium), ZAP and CodeQL.

**Verdict: not approvable yet.** There are no functional defects in normal use. There are two should-fixes, both missing tests for rules the PR states.
- **S1.** The merged piece's marks and joined hyphens are not pinned. This is test-list item 5.
- **S2.** The overlap part of `sentence_starts`' skip rule is not pinned. This is the rule the body says keeps the page, the markers and the player in agreement.

## What I checked

### Against the plan, the C2 test list and the coordinator's points
- **One grouping rule.**
  - `sentence_starts` uses the same order (`(start, n)`) and the same skip rule as `_block_view`: empty spans, and spans that start before the drawn end.
  - It joins a chunk only when the chunk before it is the one the page draws just before it in the same block.
  - The page (`firsts` into `_block_view`), the markers (`_Book.firsts`) and the script (`"sentences"`) all take this one list.
  - Placeholder blocks return early in `_block_view`. Their chunks share `b{n}` either way, so a join there changes nothing on the page.
- **The page.** A later piece deletes the pieces from the sentence's first piece onwards and redraws one piece from the first piece's start to its own end, so the text between the pieces is included. `data-chunk` stays the first piece. Without `joins`, `sentences` is the identity, and the old pieces, ids and steps are unchanged.
- **Next, Previous and click to play.**
  - Next skips to the next chunk that starts a sentence. At the last sentence it restarts that sentence, as before.
  - Previous measures `RESTART_AFTER` from the first piece and lands on the first piece of the sentence before.
  - A click plays from `data-chunk`, which is the first piece.
- **One highlight and one margin bar** in Listen and Focus. The browser test covers both views, with axe in light and dark.
- **The marker** anchors the whole sentence from any piece: block, the first piece's start, the last piece's end.
  - `check_span` runs on the whole span. The empty-piece refusal stays: mutant C12 is killed by #490's `[empty]` case.
  - `on_sentence` compares sentences. M toggles from every piece, and an old one-piece marker is found and not doubled.
  - The anchor quote has no length cap in `markers.py`, so a long joined sentence is never refused for its length.
- **An old `markers.json`** (one chunk per element, as #490 wrote it) still loads, places on its piece and is the sentence's marker: `test_a_marker_set_on_one_piece_before_480_is_the_sentences_marker`. Restore's clash check goes through `on_sentence`, so it now also compares sentences.
- **Grace and toggle lessons.** M's 1.2 s grace is counted from the first piece. M early in piece 1 still marks the sentence before (#397). The tick, the list's time and Go to all use the first piece.
- **Harness changes** (D-718): `readalong(joins=)`, the `book` fixture in `test_web_joined.py`, and the new browser file with its `at()` helper. Each has its reason in the body. No existing fixture or helper changed. The plan expected the helper in `web_helpers.py`; it sits in `test_web_player.py` instead, which is fine.
- **Closing keywords.** Only `Closes #480`, in the body. The commit message has none.

### Runs (on 763595d)
- **Unit:** `test_web_joined.py`, `test_web_player.py`, `test_web_markers.py`, `test_web_markers_survive.py`, `test_web_schemathesis.py`, `test_web_position.py` and `test_web_listen.py`: 179 passed, 1 skipped (read-only as root).
- **Browser** (Chromium): `test_joined.py`, `test_markers.py`, `test_player.py`, `test_focus.py` and `test_listen.py`: 64 passed.

### Mutation (21 hand mutants, one at a time, from a clean worktree; `scratchpad m503/mut.py`, `run.sh`)
- **Python, against the seven unit files above (`-x -n 4`): 7 killed, 2 equivalent, 3 survive.**

  | mutant | result |
  |---|---|
  | C3: no `kept_before[n] == n - 1` | killed: `test_a_join_never_crosses_a_block_or_follows_an_empty_span` |
  | C5: an undrawn chunk counts as following | killed: the property test |
  | C6: `sentences` not sent | killed: `test_the_pieces_of_a_cut_sentence_are_one_element` |
  | C8: anchor only the first piece; C9: anchor the named piece; C10: the toggle compares chunks | killed: `test_a_new_marker_anchors_the_whole_sentence_from_any_piece` |
  | C12: an empty piece not refused | killed: #490's `[empty]` case |
  | C7: no `last_element is not None` in the join branch | equivalent. `sentence_starts` joins n only when n − 1 is the chunk drawn just before it in the same block, so `last_element` is already set. |
  | C11: an extra `p.chunk >= first` in `on_sentence` | equivalent: `firsts[p] == first` implies `p >= first` |
  | **C1:** the merged piece drawn without `marks` | **survives: S1** |
  | **C2:** the merged piece drawn without `joined` hyphens | **survives: S1** |
  | **C4:** `sentence_starts` skips empty spans but not overlapping ones | **survives: S2** |

- **Player script, against `test_joined.py`, `test_markers.py` and `test_player.py` in Chromium: all 9 killed.** They are J1 to J9:
  - next by chunk;
  - previous to a piece, not the sentence's first;
  - `RESTART_AFTER` from the piece;
  - the grace from the piece;
  - the tick, the list's time and Go to from the marker's own chunk;
  - `firstOf` as the identity;
  - previous restarting while paused.

## Findings

### S1. Marks and joined hyphens over a merged piece are not pinned (test list item 5; C1, C2)
The join branch of `_block_view` redraws the sentence with `_piece(text, start, span.end, joined, marks, …)`. Dropping `marks` or `joined` there leaves every test green. The property test draws no edits and probably no line-end hyphen across a join. Add one unit test to `test_web_player.py`:
1. **A mark across the join.** An edit (a cut or a replaced stretch, as the existing mark tests build them) that starts in piece 1 and ends in piece 2 is drawn in the merged piece. The parts' texts join up to `shown(text, start, end, joined)` over the whole range, and the mark's part is there. This must fail with C1.
2. **A line-end hyphen joined between two pieces.** For example "… inter-\nnational …", with the cut such that the hyphenated word lies inside the merged range. The merged piece shows the word joined. This must fail with C2.

### S2. The overlap part of the shared skip rule is not pinned (C4)
The body says `sentence_starts` uses "the same order and skip rule as `_block_view`", so that the page, the markers and the player can't disagree. Without the `span.start < position` part, nothing fails, but they do disagree. Probe on 763595d with mutant C4, paragraph "One two three, four five six.":
- Spans (0, 0, 13), (0, 4, 9) and (0, 14, 29); chunk 2 says it `joins`.
- Head: elements `s0 s0 s2`, sentences `[0, 1, 2]`.
- Mutant: elements `s0 s0 s0`, but sentences `[0, 1, 1]`. The page draws chunk 2 into chunk 0's sentence while the player and the markers group it with chunk 1.

Add this case, or one like it, to `test_a_join_follows_only_the_chunk_the_page_draws_just_before_it`. Assert the elements and `sentence_starts(data) == view.sentences == [0, 1, 2]`. It must fail with C4. Optionally, let the property test's generator draw overlapping spans too, so the model covers the whole skip rule.

## Process
- **One fix commit**, tests only. No source change is expected; if one turns out to be needed, say why.
- **Linux CI green**, then round 2. This is round 1 of at most 2 (non-critical). In round 2 I re-run C1, C2 and C4.
