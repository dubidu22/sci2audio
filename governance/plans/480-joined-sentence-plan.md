# #480 plan: the pieces of a cut sentence sound and look like one sentence

Status: DRAFT for the coordinator, 17 Nov 2026. Written by the web lane thread after PR B (#490) was handed to review.
Issue: #480 (v1.2, lane:app + lane:web), with Colin's scope comment of 17 Nov 04:58Z.
Colin, 17 Nov: "how about the senteces being ripped apart at the comma? It's better now but not reliable" and "could we put these pieces together so they sound not so seperated?"
Base read: main 5812d2d. Files read: `app/audio.py` (`plan_audio`, `assemble`), `output/model.py` (`Pause`, `OutputSettings`, `Spoken`), `output/timeline.py`, `output/write.py`, `output/readalong.py`, `textprep/utterances.py` (the cut rules, `DEFAULT_MAX_CHARS`), `voices/kokoro_engine.py`, `web/player.py` (`_block_view`), `static/player.js` (sentence steps, highlight, markers).

Earlier PRs built on a model this PR changes: #481 (the cut rules; unchanged here), #489 (the reading mark and bar; it now spans a whole sentence instead of a piece), #490 (markers; its overlap rule decides which element a marker shows on, and a new marker on a joined sentence anchors the whole sentence).

## 1. What I measured (real voices, in this container)

I downloaded both voice packs into a scratch folder with `sci2audio voices download` and spoke four long sentences with the real models: two English ones (af_heart) and two German ones (Thorsten, including Colin's BNE sentence). Each sentence was spoken twice: whole, and cut at its comma the way textprep cuts it. The script is `plans/480-measure_cuts.py`.

| | voice's own silence at the cut today (`Pause.NONE`) | Kokoro's own pause at a comma, sentence spoken whole | phoneme tokens per character |
|---|---|---|---|
| English | 0.78 s and 0.80 s | 0.23 to 0.49 s | 0.97 |
| German | 0.56 s and 0.58 s | 0.10 to 0.20 s | 1.07 to 1.16 |

What this shows:
- **The silence is the problem, not the pause kind.** A cut already gets no pause today (`Pause.NONE`, 0 s). The gap still comes out at 0.56 to 0.80 s, because every piece is spoken alone and Kokoro puts about 0.25 to 0.5 s of silence before and after its own speech. That makes a cut longer than Kokoro's own comma pause, which is why it sounds "ripped apart".
- **We cut too early.** The voice takes about 510 phoneme tokens per call, which is roughly 500 English or 440 German characters. Textprep cuts at `DEFAULT_MAX_CHARS = 300`, so every sentence between 300 and about 400 characters is cut although the voice could speak it whole. This is the "not reliable" part: an uncut sentence has Kokoro's own prosody across the comma, which no join can match.
- **What a join cannot fix:** the pitch at the end of piece 1. It is spoken alone, so it closes like the end of an utterance. Only fewer cuts help with that.

## 2. Design

### A. Audio (lanes: output and app)

1. **A new pause kind, `Pause.CLAUSE`** (`output/model.py`), between NONE and SENTENCE in the strength order. `OutputSettings.clause_pause` defaults to 0.25 s, a measured comma pause that sits between the German and the English values. It is not a user setting (YAGNI), but `__post_init__` checks it like the other pauses. `plan_audio` gives `Pause.CLAUSE` to every utterance with `continues=True` instead of `Pause.NONE`. `Pause.NONE` stays in the enum for old plans and for `strongest()`.
2. **Trim the voice's edge silence at a clause join** (`output/wav.py`, `output/timeline.py`, `output/write.py`). When chunk k+1 has `Pause.CLAUSE`, output trims the trailing quiet run of chunk k and the leading quiet run of chunk k+1.
   - A frame is quiet when its peak is under −45 dB of the chunk's own peak; frames are 10 ms.
   - Each side keeps 30 ms and loses at most 0.8 s. No other chunk is trimmed.
   - The pure function `edge_trim(samples) -> (lead, tail)` lives in `wav.py`. `ChunkAudio` gets `skip_start` and `skip_end` frames, `frames_of` streams only the kept range, and the timeline places chunks by their kept frames. The read-along times therefore stay exact by construction, as they are today.
   - The speech cache is untouched: chunk WAVs are trimmed while they are assembled, never on disk, so nothing is spoken again.
3. **The read-along file says which chunk continues a sentence.**
   - `Spoken` gets `continues: bool = False`, which `assemble` takes from the utterance. A skipped piece passes it on like its pause does.
   - `readalong.to_json` writes `"joins": true` on such a chunk and leaves the key out otherwise. `from_json` reads it with a default of false.
   - The version stays 1. The key is additive, and the version-1 reader already ignores keys it does not know, so older sci2audio versions read new files and new versions read old files. `docs/readalong-format.md` gets the key.
   - **Open point for the coordinator:** I read this as a backward-compatible format addition, not a contract change. If you count the read-along format as a contract, the alternative is version 2 with a reader for version 1, which is larger.

### B. Fewer cuts (lane: textprep) — an open choice, see section 5

Raise `DEFAULT_MAX_CHARS` from 300 to the voice's measured limit with a safety margin. The proposal is 400 characters: German at 1.16 tokens per character gives about 464 tokens, under 510. This changes the script of every sentence between 300 and 400 characters: those sentences are spoken again on the next run, and the regression rows of the cut rules (#481) change. That makes it critical.

### C. The page (lane: web)

1. **One element per sentence.** In `_block_view`, a chunk with `joins` takes the element of the chunk before it: `element_of[n]` is the same id. The page draws one `Piece` from the first piece's start to the last piece's end, including the text between the pieces, and its `data-chunk` is the first piece. Chunks stay one per piece in the read-along, so times, `position.json` and saved positions keep their meaning unchanged.
2. **The player.**
   - The highlight, the fill and the 3 px margin bar already follow the element of the current chunk, so they span the whole sentence with no change to the mark itself (D-724, D-727).
   - The next and previous sentence controls (`#next-sentence`, `#previous-sentence`, the arrow keys) step by element, not by chunk. Today they step by chunk, which would land inside a sentence. Previous restarts the current sentence from its first piece.
   - Focus listening shows the element, so it shows the whole sentence. A click on a sentence plays it from its first piece.
3. **Markers (#474).**
   - `place()` already shows a marker on the chunk it overlaps most. That chunk's element is now the whole sentence, so an old marker set on one piece shows on the joined sentence, and M on that sentence removes it.
   - A new marker set on a joined sentence anchors the whole sentence: the span runs from the first piece's start to the last piece's end, all in one block.
   - `_Book.on_sentence` compares elements rather than single chunks.
4. **Old audiobooks** have no `joins` key, so they look exactly as they do today, one element per piece. Making the audiobook again brings the joined look.

## 3. Tests (written first)

- **Output**
  - `edge_trim` on built signals: silence, a tone with known lead and tail, the 30 ms floor, the 0.8 s cap, a chunk that is all silence (never trimmed to nothing), and a Hypothesis property: the kept range always holds every frame above the threshold.
  - A timeline over a cut sentence: the gap at the join equals `clause_pause` plus at most 60 ms, and the read-along start of chunk k+1 equals its first kept sample.
  - A WAV round trip: the M4B length equals the timeline length.
  - `joins` survives `to_json`/`from_json`, and an old file without it reads as false.
- **App**
  - `plan_audio` gives `Pause.CLAUSE` to `continues` utterances. A `pause` edit inside a cut sentence still wins (`strongest`).
  - A skipped piece carries `continues` on.
  - A regression check with a long sentence cut at a comma, using the fake voice with known edge silence: the gap at the cut equals the clause pause.
- **Web**
  - `_block_view` draws one element for a cut sentence, with the in-between text, and still one per piece without `joins`.
  - `position.json` saved on a piece still resolves.
  - A marker anchored to one piece shows on the joined sentence, and a new one anchors the whole sentence.
  - Browser test (Chromium): the mark and the bar cover the whole sentence through every piece, and the next/previous controls step whole sentences. Axe runs in light and dark.
- **Slow (nightly)**
  - With the real voices, the measured gap at a cut is at most `clause_pause` plus 0.1 s, in English and German.
  - The faster-whisper round trip of a cut sentence still reads every word.
- **Mutants to kill:** trim on both sides vs. one side, the floor, the cap, CLAUSE vs NONE in `plan_audio`, `joins` dropped in `to_json`, and the step by element.

## 4. Size and order

- **PR C1, output + app (non-critical):** `Pause.CLAUSE`, the trim and `joins`. About 120 lines of code and 250 lines of tests.
- **PR C2, web (non-critical):** one element per sentence, the sentence steps and the marker anchor. About 80 lines of code and 200 lines of tests. It needs C1's `joins`, so C1 merges first.
- Two lanes and two PRs, as the lane rule asks. If you prefer one app/output/web PR, it stays reviewable at about 450 lines in all, but it crosses three lanes.
- **B** would be its own textprep PR (critical), after C1 and C2 or before them as you decide.

## 5. Open choice for the coordinator

**B, fewer cuts:** (1) do it now as its own critical textprep PR after C1 and C2, (2) do it first, or (3) leave it as a v1.2.x issue. My recommendation is (1). C1 and C2 fix what you hear and see at every cut, and B then removes most cuts. B is the only thing that fixes the pitch at the end of piece 1, and Colin's "not reliable" points at it, but it changes regression rows and makes cached sentences be spoken again, so it should be reviewed on its own.

Not in scope: the sentence gap itself. It is 0.3 s plus the voice's own edges, about 1.1 s in English; tightening it would be a separate question for Colin.
