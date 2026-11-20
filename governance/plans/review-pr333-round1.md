# Review PR #333, round 1 (footnote marks and German closing quotes, #315 #316)

Reviewed head: 436b16c, and the merge with main fbc6de8 (my local merge 5609abb has the same tree as the author's merge 05b0800). Verdict: **changes needed** (5 required fixes, 1 optional).

## What I checked

- Fast suite on the merge with main, ci profile: 4802 passed, 1 skipped, 76 snapshots unchanged.
- Corpus: all 13 documents through `run_script_job`, main vs PR: script, report JSON, report Markdown and every utterance byte-identical (52 files).
- Timing: every `assert_linear`/`assert_near` ratio in the units/abbreviations, statistics, numbers, utterances, citations and links tests, main vs PR: all between 5 and 9.3, limit 32, no change beyond noise. Whole chain on 800 paragraphs with 800 marks and notes: 0.58 s on main, 0.78 s on the PR (+36%, from `found_marks` running `FootnoteStep.marked` four more times). It stays linear (50/200/800 notes). Accepted, no fix.
- Nightly profile, my seeds 555, 8080 and 31337, on the utterances, footnotes, footnote-places, units/abbreviations, statistics, numbers and both regression files (1316 tests each): 555 and 31337 green. 8080 found a numbers-step idempotence break (`3 × 10−410^2`) that is also on main, so not this PR: filed #340.
- Shape probes (sup-tagged mark plus a footnote, whole chain, run 1 vs the same text without the mark vs run 2), 90 shapes in en and de, PR vs main. With Footnotes on, the PR fixes every glued-after shape it names and more (`u. a.¹`, `usw.¹`, `Dr.¹`, `Std.¹`, `i. d. R.¹`, `Vgl.¹ S. 12`, `ca.¹ 12.345`, `bzw.¹ (Müller, 2019)`, `z. B.¹ [12]`, `cf.¹ [12]`, `5 kg¹ today`, `Am 3.¹ Mai 2020`). It breaks nothing that main reads stably.
- Hand mutations, 14 one-line changes, all textprep unit and regression tests: 10 killed, 4 survived (R1-2, R1-3 and two equivalent ones, below).

## Required fixes

**R1-1 (blocker): with the Footnotes category switched off, the steps still skip marks, though the marks stay in the text.** `found_marks` cannot know whether the footnotes step's edits will be applied: `StepContext` has no switched-off categories, and the runner still calls `find` for switched-off steps. When a user switches Footnotes off (the web API and settings accept any category), the marks are read, but the abbreviation, number, unit and statistics steps act as if the marks were gone. Probes with `switched_off = DEFAULT_SWITCHED_OFF | {Category.FOOTNOTES}`:

| Text (¹ = sup "1") | main, both runs | PR run 1 | PR run 2 |
|---|---|---|---|
| `Siehe Abschnitt 2.¹ Dann weiter.` | "2 Punkt 1" | "2.1" | "2 Punkt 1" |
| `Siehe Tab. 2.¹ Dann mehr.` | "2 Punkt 1" | "2.1" | "2 Punkt 1" |
| `Er sagte „ja“.¹ Dann ging er.` | "„ja“0 Komma 1" | "„ja“.1" | "„ja“0 Komma 1" |
| `Das ist z.¹ B. so.` | "z.1 B." | "zum Beispiel" (the mark is gone) | "zum Beispiel" |

So the PR adds three second-run breaks that main does not have. In the fourth row an abbreviation edit spans the mark and drops it without any footnotes edit, though the user asked for marks to stay. Required: with Footnotes switched off, the four shapes read on both runs exactly as on main; add them as tests that run twice. A likely route is a defaulted `StepContext` field that `run_steps` fills from `switched_off`, read by `found_marks`. That changes the text-step interface (critical), so post the design to the coordinator before you write code, whatever route you pick.

**R1-2: the unit and statistics changes are untested.** Mutants `units.py` `marks.get(index, ())` → `()` and `statistics.py` `unread = marks.get(index, ())` → `unread = ()` both pass every textprep test. (The "5 kg.¹ Dann" and "approx.¹ 5 kg" rows of `test_a_mark_hides_no_abbreviation_or_number_from_the_first_run` pass without the units change.) Shapes that need each change; each one is stable on the PR and breaks on run 2 with the change removed:
- units: en `It weighs 5 kg¹ today.`, de `Es waren 5 kg¹ heute.`, de `Es dauerte 2 Std.¹ Dann kam er.`
- statistics: en `It was 95% CI¹ 1.2–3.4 here.`

Add these to that test, or as regression cases, and check that each mutant now fails.

**R1-3: the German `rstrip(closing)` change is untested.** Mutant `closing = _CLOSING_DE if german else _CLOSING` → `closing = _CLOSING` survives. These shapes kill it (PR: one utterance; mutant: cut after the quote): `Er nannte „Dr.“ Müller dann.`, `Er sagte „A.“ Dann ging er.` Add them to `test_german_sentences_end_where_german_ends_them`.

**R1-4: German single guillemets are missing.** German typesetting quotes inside »…« with ›…‹, and Swiss inside «…» with ‹…›. On the PR, `Er sagte ›ja.‹ Dann ging er.` is not cut (»ja.« is). And a mark after it, `Er sagte ›ja.‹¹ Dann ging er.`, is not found as a mark at all: it is read "›ja.‹1" on both runs, because `footnotes._CLOSING` has « » but not ‹ ›. Required: add ‹ (U+2039) and › (U+203A) to the German closing set in `utterances.py`, and to the closing characters a mark may follow in `footnotes.py`. Also add › and ‹ to what may open the next sentence in German, so that `Er sagte »ja.« ›Nein.‹ Dann ging er.` cuts after »ja.«. Add cutter tests, a footnote-places test, and an English test showing that English is unchanged.

**R1-5: the PR body and CHANGELOG claim too much.** "A footnote mark hides no abbreviation or number" is not true for a mark *inside* a multi-part abbreviation (`z.¹ B.`, `d.¹ h.`, `i.¹ e.`): the abbreviation edit spans the mark and is set aside, so run 1 reads "z. B." and run 2 "zum Beispiel" (also on main). Filed as #341. Write "glued after" in the PR body and the CHANGELOG line, and list #341 (and #342, below) under Out of scope.

## Optional

**N1:** `found_marks`' language gate is dead. Every caller handles only en and de, which are exactly `FootnoteStep.languages`, so the mutant that removes the gate is equivalent. `if not FootnoteStep().handles(context.language)` says the same thing and stays right if the languages change. Also equivalent and needing no test: mutant `closing = _CLOSING_DE` for English, because the English regex never lets a German closing quote come before the gap.

## Filed (deferred, all also on main)

- #340: numbers step not idempotent on `3 × 10−410^2` (nightly seed 8080).
- #341: a mark inside a multi-part abbreviation, or between "CI" and its bracket, still hides the shape on run 1.
- #342: a German abbreviation ending a sentence inside a closing quote loses its full stop (`Er schrieb „usw.“ Dann ging er.` is one utterance; without the quote it is cut).

## Probe scripts (container-local)

/home/user/probe: marks.py (shape | mark → run 1 / plain / run 2, footnotes on or off), cuts.py (utterance cuts), mutate.py, timelog.py + ratios.py (timing ratios main vs PR), corpus.py (13 documents plus utterances).
