# Sentence-boundary programme: plan (D-715)

Thread: textprep lane, "Plan sentence-boundary fixes" (started 16 Nov 2026 18:47Z). Base: main 7cd84bd.
Status: **waiting for the coordinator's approval** (critical: text-step behaviour, regression cases,
golden files, a new truth kind). No code or tests before approval.

Colin's ask (16 Nov 16:28Z / 16:35Z): "Sentence boundaries are a problem in general. How could we
tackle that issue?" then "I agree. This is a priority issue. start once the current threads are done."
Agreed approach: (1) a hand-checked sentence test set with a precision/recall metric; (2) a layout
join rule (#454); (3) evaluate pySBD against our rules on that set and adopt it only if it wins.
Folded in: #460, #455; coordinator additions #463, #464.

## 1. What exists today (read on 7cd84bd)

- **One sentence rule, in one place.** `textprep/utterances.py::_sentences` cuts a block's script
  text (after the text steps) at `.?!` + closing quotes/brackets + white space + (capital, digit or
  opening quote/bracket). Exceptions: per-language abbreviation sets (`ABBREVIATIONS["en"]`
  hand-listed, `["de"]` built from the German abbreviation and unit lists), `_BEFORE_NUMBERS`
  ("No.", "p.", "vol." only before a digit), single initials, never inside a replacement.
- **German (#227, #229, D-530, D-577)** already has: German closing quotes „…“ »…« «…» ›…‹, short
  ordinals ("3. Sieger") cut only before a word of `data/de/sentence_openers.toml`, labels
  ("Abbildung 1. PrivacyScore") cut, units with a full stop through the openers list. Known
  accepted limit: "Es waren 3. Studien zeigen das." stays one utterance.
- **Other users of the rule:** `sentence_end()` places footnotes after the sentence holding the mark
  (#213); `app/audio.py` turns `continues` into `Pause.NONE`, a new utterance in the same block
  into `Pause.SENTENCE`, a new block into `PARAGRAPH`/`HEADING`; the web player draws one sentence
  element per utterance.
- **Utterances never cross blocks** (module docstring, span contract). So every layout block
  boundary is a sentence boundary for the listener. That is why #454 (layout split a motto at an
  indent) sounds like a sentence break.
- **Long sentences (#460):** `_cut_point` takes the last `;:` that fits in 300 spoken characters,
  else the last comma, else a dash, else a space. It never looks for a better boundary earlier.
- **No measurement exists.** The truth files hold 3 to 7 `verbatim` sentences per paper; nothing
  counts boundary errors.

Corpus size as the pipeline reads it today (utterances that start a sentence, my run on 7cd84bd):

| file | lang | sentence starts | cut by length |
|---|---|---|---|
| acl2023-chi-plue | en | 345 | 5 |
| acl2023-hardt-ellipsis | en | 245 | 0 |
| acl2023-nowak-prefix-probabilities | en | 282 | 4 |
| arxiv2024-arsiwalla-qualia-meaning | en | 473 | 16 |
| arxiv2024-liu-orbital-hall | en | 164 | 4 |
| joss2021-waskom-seaborn / joss2022-biggs-pymedphys | en | 75 / 31 | 3 / 4 |
| arxiv2017-maass-privacyscore | de | 297 | 11 |
| own samples (en: note, plain / de: notiz, text) | en / de | 51 / 38 | 0 |

German is thin: one paper of one genre (CS and law). Colin's papers are humanities (Kehren).

Open sentence issues found besides the ones named: #406 (German "Az." before a file number ends
the sentence), #141 (a single capital after a maths symbol is no initial), #268 (cutter quadratic on
a block with many sentences: `_LAST_WORD.search(text, 0, end)` rescans from 0 at every match).

## 2. PRs in batch order

All PRs are critical (`risk:high`). One implementation thread (this one) authors all of them in
order (D-705); PR 2 is a layout-lane PR by file scope (`.github/lanes.yml`), authored by this
thread unless the coordinator wants a layout thread for it (open question Q1).

### PR 1: sentence test set and metric (tests only, no behaviour change)

**What.**
- `tests/sentences/<corpus name>.txt`: hand-checked sentences, one per line, as printed (the truth
  README's normalisation: line breaks become a space, a line-end hyphen that only splits a word is
  dropped, marks and inline maths written in line). Format:
  - `# …` comment; `@page N` marks where a page starts (for the reviewer, not scored);
  - a plain line is one sentence; a heading is its own line;
  - a line starting `~ ` continues the sentence above across something that is not read in place
    (a display formula, a float, a footnote): the boundary there is **optional**, counted neither
    way;
  - a line `---` marks a gap: the text between is not annotated (tables, reference list, code,
    author block), and alignment restarts after it.
- **Natural set** (scored against targets): English hardt (~245) + chi (~345) + the own en samples
  (~51) ≈ 640 sentences; German maass (~297) + the own de samples (~38) ≈ 335 sentences. Body text,
  headings, captions; footnotes and the reference list are gaps (footnotes move, references are
  removed or read differently).
- **Stress set** (`tests/sentences/stress-de.txt`, `stress-en.txt`, about 100 sentences each),
  written for sci2audio, CC0, no third-party text: German citation shapes of #455, ordinals, dates
  "3. 4. 2019", units with a full stop, legal references ("Art. 6 Abs. 1 lit. f", "i. V. m.",
  "Az. 13 W 17/12"), "S. Müller", quotes „…“ closing a sentence, long sentences with colons;
  English "approx. 5", "vs.", "U.S.", "Fig. 3", "et al.", "p < .05", initials, "e.g."/"i.e." in
  brackets. Run as text files through the same pipeline. Scored separately: it tells rule coverage,
  not real-world quality.
- **How the truth is made (D-60 spirit).** Drafted from the PDF (and the arXiv LaTeX source for
  maass as a check), never from the cutter's output. Then every disagreement with the cutter is
  checked against the page and resolved in the truth's favour or corrected; each correction gets a
  `#` comment. The review thread independently checks every disagreement plus a random sample of
  100 boundaries per language (seed in the review report). See Q2 on Colin's check.
- **Metric** (`tests/sentences/metric.py`, test-side, no `src` change):
  - System side: run `read_document` + `prepare_script` (all chapters) and take every non-pause
    utterance with `continues=False`; its boundary is the start of its original span. Footnote
    blocks are dropped on both sides.
  - Alignment: normalised word sequences (NFKC, white space folded, hyphen joins as in the truth
    README) of the truth and of the document's printed text in reading order, aligned with
    `difflib.SequenceMatcher(autojunk=False)` on word lists (deterministic). A boundary is a gap
    between two aligned words.
  - TP / FP / FN counted only inside aligned stretches; optional boundaries count neither way.
    FP split into **block** (the boundary is a layout block edge: a layout error) and **in-block**
    (a textprep rule error). Report precision, recall, F1 per language and per file.
- **Gate: a known-errors list, not a threshold.** `tests/sentences/known-errors.toml` lists every
  error of the baseline: file, the words around it, FP/FN, class (`layout-split`, `abbreviation`,
  `ordinal`, `initial`, `citation`, `quote`, `formula`, `other`), and an issue number. The test
  fails on **any unlisted error** and on **any listed error that no longer occurs** (so a fix must
  shrink the list: a ratchet). Precision/recall are printed and written to the test report, and a
  floor per language (baseline rounded down to 3 decimals) is asserted as a second line of defence.
- Runs in the fast suite (≈2 s per paper on my run, about 10 s in all with the existing corpus
  caches); if it is over 15 s on CI it moves to `slow` + nightly, and review runs it.
- Out-of-repo evaluation script `plans/sentence-boundary-eval/eval.py` (mount) that plugs other
  splitters into the same harness (section 3). Not shipped; no new dependency in PR 1.

**Licence.** Sentence files quote corpus papers: hardt and chi are CC BY 4.0 (ACL Anthology),
maass CC BY 4.0 (arXiv), own samples CC0; the stress sets are written for sci2audio (CC0). Each file
starts with title, authors, source and licence; `tests/sentences/README.md` has the attribution
table. **No personal-use paper** (Kehren stays out; its shapes go into the stress set as our own
sentences). The files sit outside `tests/corpus/` so `test_corpus.py`'s file rules are untouched.

**Critical because:** new golden/truth files and a gate on the text-step output.
**Acceptance:** the test passes on 7cd84bd with the baseline list; the review's sample check finds
no truth error, or each one found is corrected in the fix commit; the README states the format.
**Earlier PRs in this batch that built on a model this PR changes:** none.

### PR 2 (layout lane): flush-right and centred blocks; a block that ends mid-sentence goes on (#454)

**What.** In `layout/paragraphs.py`:
1. **#454 as specified:** rows that share a right edge (within `align * size`) and have ragged left
   edges are a flush-right (or centred: both edges symmetric about one axis) block; there the
   first-line-indent and outdent rules do not split (in centred rows the short-line rule neither).
   Size, weight, a change between italic and upright (review of #476, S1) and extra white still do.
2. **Join rule (the general part):** a short-line break is not taken when the last row ends
   inside a sentence (it ends in a letter, a comma, a semicolon, an open bracket or a slash; not a
   digit) **and** the row right under it starts with a lower-case letter that is no "i." / "a."
   list mark, and the paragraph is no caption. An indent or an outdent still ends the paragraph
   (amended in review of #476, round 1, S2; coordinator's ruling 16 Nov 20:25Z: a real first-line
   indent or hanging-indent outdent is a stronger sign than a lower-case start). Size, weight and white-space
   breaks still end the paragraph, so headings, captions and list entries are not joined.
   The lower-case guard is deliberate: a reference entry ending in a DOI without a full stop is
   followed by an upper-case author, so hanging-indent lists stay apart; German nouns start
   upper-case, so "…Gefährdung,\nZiel…" is not joined by this rule (rule 1 covers the motto).

**Tests first:** a synthetic flush-right motto (no third-party text) failing before the fix; a
synthetic justified paragraph with a real first-line indent still splitting; a hanging-indent
reference list ending in a DOI still splitting; corpus truth tests and layout golden files
unchanged, or each change explained in the PR; Hypothesis properties of D-76 still hold. The
sentence metric: every `layout-split` known error that disappears is removed from the list.

**Critical because:** layout golden files may change.
**Acceptance:** #454's four criteria; no new metric error; block-class FPs on the natural set ≤ the
baseline minus those fixed.
**Earlier PRs in this batch that built on a model this PR changes:** none (PR 1's metric reads
blocks but assumes nothing about where layout splits).

### PR 3: sentence rules, measured; pySBD decision (#406, #141, #268)

**What.**
1. Run the evaluation (section 3) and record the result in `plans/sentence-boundary-eval.md`.
2. **If our rules win** (expected, see the smoke test below): fix the rule-class errors that PR 1
   listed, each with a regression case first: #406 ("Az." before a file number), #141 (a capital
   after a maths symbol), and every other class with two or more occurrences in the natural set.
   Single occurrences that need a new rule shape are fixed only if the rule is general; else they
   stay listed with an issue.
3. **If pySBD wins for a language:** adopt it for that language only, as the candidate generator
   inside `_sentences`, keeping our guards (never inside a replacement, German ordinal/opener rule
   if it beats pySBD there); dependency through the licence gate (MIT, pure Python, no network,
   `THIRD_PARTY_LICENSES.md` row, `deptry`), and an infra-lane `pyproject.toml`/`uv.lock` change
   (Q3).
4. **#268:** `_LAST_WORD.search(text, 0, end)` scans from the start at every candidate; search from
   a bounded window instead, with a `benchmark` test on a block of 2,000 sentences (linear time).

**Tests first:** English regression cases before any English rule change (golden), German cases,
unit tests in `test_textprep_utterances.py`, the Hypothesis properties (no crash, spans valid, in
order), second-run idempotency (D-710 conformance on every built-in step), `sentence_end` tests
(footnote placement uses the same rule: the footnote corpus tests must stay unchanged or be
explained).

**Critical because:** text-step behaviour, regression cases; with pySBD also a dependency.
**Acceptance:** natural set EN precision ≥ 0.990 and recall ≥ 0.990, DE precision ≥ 0.985 and
recall ≥ 0.985 (if the PR 1 baseline is already above, the target is the baseline plus every
fixed known error); stress set: every shape the module docstring claims is right; known-errors list
only shrinks; no `abbreviation`, `ordinal` or `initial` error left without an issue.
**Earlier PRs in this batch that built on a model this PR changes:** PR 1 (the metric reads
`continues=False` utterances: unchanged meaning). Outside the batch: footnote placement
(`sentence_end`, #213) and the German rules of #227/#229 call `_sentences`.

### PR 4: long sentences cut at the best clause boundary (#460, textprep part); German citation shapes (#455)

**What (#460).** `_cut_point` ranks every candidate in the window, not the last one that fits:
`;` / `:` first, then a comma before a conjunction or clause opener (de: und, oder, aber, denn,
doch, sondern, dass, weil, wenn, ob, als, da, wie, die/der/das/welche… as relative pronouns after a
comma; en: and, but, or, nor, yet, so, which, who, whom, whose, because, although, while, whereas,
where, when, that), then any comma, then a dash, then a space. Within a rank the cut nearest the
middle of what is left wins, so pieces stay balanced; a piece may be shorter than the limit to
reach a better rank; never under a minimum piece of 40 spoken characters unless no other cut
exists. Lists in `data/{de,en}/clause_openers.toml`, written for sci2audio.
Kehren's sentence (block 130) is cut after "reagiert:" and nowhere else.

**What (#455).** `citations.py`: years joined by `/` ("1974/2004"), authors joined by `/`
("Heydorn/Koneffke"), Roman page locators after `S.`/`p.`/`pp.` ("S. XV", "pp. iv–vi"), and the
all-capitals author ("WBGU 2011", cause to be pinned first). Guards for slash: both sides are
capitalised name words, or both are four-digit years; `(und/oder 3 Mal)` stays. "(BLK-Heft 72
1999)" (series title before a year): out of scope, stays read, a comment in the regression row.

**Tests first:** English regression cases for the English shapes ("(Smith 1890/1990, p. 5)",
"(Smith 2001, pp. iv–vi)", a long sentence with a late colon) before the change; German cases for
each row of #455's table and #460's two Kehren shapes rewritten as our own sentences; properties:
no piece over the limit, cut rank never worse than the old cut's; D-710 second run.

**Not in this PR (Q4):** #460's short pause at a cut (`app/audio.py`, app lane) and the whole-
sentence highlight across pieces (`web/player.py`, `player.js`, web lane). I file them as one
app/web issue linked to #460 and they follow after this batch (D-705: one thread at a time).
**Critical because:** regression cases.
**Acceptance:** #460's criteria 1, 2 and 5; #455's criteria; known-errors list only shrinks.
**Earlier PRs in this batch that built on a model this PR changes:** PR 3 if it touches the
candidate loop that `_fitted` reuses (it does not change `_fitted`/`_cut_point`); else none.

### PR 5 (optional, coordinator's call Q5): audit follow-ups #463, #464

Not sentence work, but specified, small and textprep-only. #463: `HiddenRunStep.find` skips a
placeholder only while its notice category is on. #464: alt text read through `_read_in_place` as a
paragraph block. Each with its regression rows (EN + DE) and a SAMPLE_DOCUMENTS entry for the D-710
own-output check. If not taken here they wait for the next textprep batch, which starts only after
this one (D-705).
**Earlier PRs in this batch that built on a model this PR changes:** none.

## 3. pySBD evaluation (step 3)

- **Status (16 Nov, review of #467 N2):** `plans/sentence-boundary-eval/eval.py` does not exist yet; PR 3 writes it first, as a script that imports `tests/unit/sentence_metric.py` (`read_truth`, `system_words`, `compare`) and swaps the splitter, before any rule change.

- Out-of-repo harness on the mount, scratch venv, never a repo dependency until adopted.
- Four candidates on the same natural and stress sets: (a) today's pipeline end to end; (b) our
  `_sentences` on the step output; (c) pySBD 0.3.4 (`clean=False, char_span=True`) on the same
  step output, with our "never inside a replacement" guard; (d) pySBD on the printed block text
  mapped back. (b) vs (c) is the fair comparison. syntok 1.4.4 (MIT, needs `regex`) runs as a
  second comparator at no extra cost.
- **pySBD wins for a language only if all hold:** fewer FP + FN on that language's natural set than
  (b) after PR 3's rule fixes are counted the same way; no more errors on the stress set; second
  run idempotent; ≤ 5 ms per block median on the corpus; no regression case changed without a
  reason. A tie keeps our rules (no dependency for nothing).
- Excluded up front: NLTK Punkt and neural splitters (spaCy models, wtpsplit): they need a model
  download or trained data, against "nothing from the internet".

**Smoke test on 16 Nov (my scratch venv, not the set):** pySBD 0.3.4 (MIT, last release Feb 2021,
pure Python) splits "Am | 3. | 4. 2019 begann", "Siehe Abb. | 3 und", "Gemäß Art. 6 Abs. | 1 lit. |
f DSGVO", "It costs approx. | 5 USD"; our rules keep all four. It gets "Er wurde 3. Sieger" and
"2 Std. Danach" (no cut) the way #229 decided against. It takes 15 s on one 113,000-character
string (superlinear), about 3 ms per 840-character block. syntok cuts "Er wurde 3. | Sieger" and
misses "0.05. U.S. law". So I expect our rules to win, but the measured set decides.

## 4. What is critical, per PR

| PR | lane | critical by | golden/regression | three-system + mutation on final round |
|---|---|---|---|---|
| 1 | textprep (tests only) | new truth kind, test gate | new sentence truth | yes |
| 2 | layout | layout golden files | layout goldens if changed | yes |
| 3 | textprep (+ infra if pySBD) | text-step behaviour | EN/DE regression | yes |
| 4 | textprep | regression cases | EN/DE regression | yes |
| 5 | textprep | regression cases | EN/DE regression | yes |

Workflow per PR: Linux CI green and my own `ci:full` green before review; one fix commit per round;
I never merge; ledger line per PR in `ledger/implementation.md`.

## 5. Open questions for the coordinator

- **Q1.** PR 2 is layout-lane by files. Recommend: this thread authors it (one thread at a time
  anyway, and it shares PR 1's metric); else a layout thread after PR 1.
- **Q2.** D-60 has Colin check truth files. ~1,000 sentence lines is a lot for him. Recommend: the
  review thread checks every disagreement plus 100 random boundaries per language, Colin is not
  asked. If D-60 must hold literally, Colin checks only the German file.
- **Q3.** A second German paper of another genre (humanities, author-year with "S.", long
  sentences), CC BY 4.0 and under 1 MB, would make the German natural set fairer (corpus 8 → 9 of
  10 papers; needs its own truth file). Recommend: yes, as a follow-up issue after PR 1, not
  blocking it; the stress set covers Kehren's shapes meanwhile.
- **Q4.** #460's pause and highlight parts: recommend one app/web issue after this batch (above).
- **Q5.** #463 and #464: recommend taking them as PR 5 here, since the next textprep batch is days
  away under D-705.
- **Q6.** Targets of PR 3 (EN ≥ 0.990 / DE ≥ 0.985) are set before the baseline exists. If PR 1's
  baseline is far below, I post the numbers and a revised target before PR 3 starts.

## 6. Size

PR 1: about 1,000 truth lines, metric ~250 lines, tests ~150. PR 2: ~60 lines + tests. PR 3:
depends on the error list; ~150 lines + regression rows. PR 4: ~200 lines + two data files + rows.
PR 5: ~60 lines + rows.
