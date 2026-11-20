# Plan: Issue #63, the text-step interface (textprep layer)

Thread "Build the text-step interface", 12 Nov 2026. Critical (layer contract, golden files). **APPROVED as written** by the coordinator, 12 Nov 2026 22:45Z (D-80; Colin informed 2026-11-12T22:45:11Z); the nine points of section 5 are decided and go into the KB as D-107 onward. Binding inputs: D-57, D-61, issue #63 as amended 22:41Z (Q4, Q11, Q15), `.claude/rules/tests.md`, issues #4 and #6.

## 0. Split: two PRs, both lane:textprep

- **PR A** (this issue's "first half", unblocks #64 to #68): interface, categories, registry, runner with the overlap rule, furniture step, `sci2audio.testing` with the text-step conformance suite, Hypothesis properties, English regression harness with the 14 audit cases, import-linter and lanes change. Does **not** close #63.
- **PR B** (unblocks #70/#71): the utterance cutter with its tests. Closes #63 (and the text part of #6, and #4's harness criteria).
- Why split: the wave-2 rule threads need only PR A; the cutter is a separate algorithm with its own review questions. The regression harness renders the script per block (not per utterance), so PR B changes no golden file of PR A.

## 1. PR A: modules and types

All in `src/sci2audio/textprep/`, importing only `core` and the standard library.

**`steps.py`: the interface**
- `TEXT_STEP_API = 1`.
- `Category` (StrEnum, fixed, each with a user-facing label for the report and switches, UC-02): `page-furniture` "Page furniture" (TP-01), `characters` "Characters and hyphenation" (IN-04, TP-02), `footnotes` "Footnotes" (TP-05), `citations` "Citations" (TP-03, TP-04), `links` "URLs, DOIs and e-mail addresses" (TP-07), `formulas` "Formulas" (FX-01), `tables-and-figures` "Tables and figures" (FX-02, TP-12), `references` "Reference list" (TP-06), `abbreviations` "Abbreviations" (TP-08), `numbers-and-units` "Numbers, symbols, units and statistics" (TP-09, TP-10, TP-11). Every step has exactly one.
- `Stage` (StrEnum): `block` (each edit covers a whole block: furniture, reference list, placeholder notices) or `inline` (edits inside a block). **This is the authoring thread's reading of D-57's "stage" field, which the KB never defined; the KB entry (D-107 onward) defines it.** it makes "coarse to fine" a checked rule instead of a convention.
- `StepContext` (frozen dataclass): `language` (the job's language, BCP 47). Only that in v1.0; new fields get defaults, so adding one later breaks no step. The app fills it from its settings (`textprep` cannot import `app`). No global state.
- `TextStep` (abstract base class): class attributes `id` (kebab-case), `languages` (tuple of primary tags, or `("*",)` for any language), `category`, `stage`, `api_version`; abstract `find(document, context) -> list[Edit]`. A step proposes; it never changes the document (D-57).

**`registry.py`: the built-in steps**
- `BUILT_IN_STEPS: tuple[TextStep, ...]` in run order. v1.0 has only `FurnitureStep` now; the docstring holds the planned order the wave-2 PRs fill in: block steps furniture, references, placeholder notices, footnote texts; then inline steps links, citations, footnote marks, characters and hyphens, numbers and units, abbreviations.
- `check_registry(steps)`: ids unique; every `block` step before every `inline` step; `api_version` current; languages non-empty and well-formed. Called by a test and by the runner on its input.
- No entry-point loading (`sci2audio.text_steps` stays v1.1).

**`runner.py`: collect and settle**
- `run_steps(document, context, steps=BUILT_IN_STEPS, switched_off=frozenset()) -> StepRun`.
- Every step whose languages match runs (primary-subtag match: `en` matches `en-GB`), **including steps in switched-off categories**, so the report can show what a switch would change without a second run; their edits are marked `switched-off`.
- Overlap rule (Q15): in registry order, then document order, each switched-on edit is `accepted` unless it overlaps an already accepted edit (same definition as `core.check_edits`: a shared character, a position strictly inside, or two marks at one position); then it is `set-aside` and records the edit that won. Switched-off edits never block others.
- `ask` edits are accepted like any other and read the original through `apply_edits` (D-61 (3)). No answers in v1.0 (UC-04 is Should).
- A step that raises or returns invalid edits (span outside its block, its own edits overlapping, wrong `step` id) gets all its edits dropped and a `StepProblem(step, message)` in the result; the run never stops (D-61 (3)). `strict=True` re-raises instead; all tests run strict, so built-in bugs cannot hide.
- `StepRun` (frozen): `document`, `outcomes` (each `Outcome(edit, category, status, won_by)`), `problems`; properties `accepted`, `set_aside`, `switched_off`; `script()` returns `apply_edits(document, accepted)`. The report format itself is #70; this is its data (set-aside edits with reason and winner included).
- Speed: per block, a sorted list of accepted intervals with `bisect`, so n log n, not pairwise (lesson of #60/#62).

**`spoken.py`**
- `spoken_text(pieces) -> str` for one block: piece texts joined, every run of whitespace (line breaks included) read as one space, trimmed; a pause is `[pause]` in the rendering only. Used by the harness now and by the cutter in PR B, so "line breaks are spaces" lives in one function, not in an edit (Q4).

**`furniture.py`: the first step (TP-01)**
- `FurnitureStep`: id `page-furniture`, languages `("*",)`, category `page-furniture`, stage `block`. One `remove` per FURNITURE block with non-empty text, span the whole block, reason naming the role ("page furniture (running head) is not read"; "page furniture" when the role is unknown). A furniture block without text (a repeated logo, D-91) gets no edit: there is nothing to remove, and `remove` needs a non-empty span.

## 2. PR A: `sci2audio.testing` (Q11)

New package `src/sci2audio/testing/`, standard library and `sci2audio` only, **no pytest or hypothesis imports** (plain callables the tests wrap):
- `documents.py`: `make_document(blocks, language="en")` builds a valid `Document` from `(kind, text)` pairs (or with role/label), one page, one `TextLine` per printed line, no boxes. Used by the conformance suite, the harness and the wave-2 rule tests.
- `text_steps.py`: `check_text_step(step, documents=None, *, allow_ask=True) -> None` raises `ConformanceError` listing every problem found. Checks (#6): `api_version` present and current; id kebab-case; category and stage valid; languages declared and well-formed; `find` returns a list of `Edit`; every span lies inside its block; every edit names this step; its own edits do not overlap (`check_edits`); a block step's edits each cover a whole block; same input gives the same edits twice (determinism); no network: `find` runs inside `no_network()`, which makes `socket.connect`, `create_connection` and `getaddrinfo` raise; idempotent: rebuilding the document from the step's script (same blocks and kinds, text = spoken text) and running again gives the same spoken text and pauses; `allow_ask=False` refuses `ask` edits. `SAMPLE_DOCUMENTS` covers every block kind, empty blocks, a furniture block with every role, and the regression case texts.
- `regression.py`: `load_cases(path)` (tomllib) and `render(run)` (one line per block, `spoken_text`, empty blocks left out), `diff(expected, got)` (difflib, readable before/after) for #4.
- Layers in `pyproject.toml` (infra file, named in the PR): `"sci2audio.app | sci2audio.testing"` (independent of each other) plus a `forbidden` contract that `sci2audio.cli` and `sci2audio.web` do not import `sci2audio.testing`, so nothing in the shipped program uses it. `.github/lanes.yml`: `src/sci2audio/testing/**` joins lane textprep for now (the voice part of #18 will need it too; a separate lane is an option if both run at once).

## 3. PR A: tests

- Unit (`tests/unit/test_textprep_*.py`): categories (all ten, labels set, unique); `check_registry` on good and bad registries (block after inline, doubled id, old api_version); runner with small fake steps: earlier wins, the set-aside edit records its winner, a mark inside a removed block is set aside, two marks at one position, switched-off edits do not block, language matching (`en-GB`, `*`, `de` skipped), a raising step and an invalid-edit step become problems (strict re-raises); furniture step on every role and on an empty furniture block; `spoken_text` on line breaks, tabs, pauses.
- Hypothesis (existing `documents()` and `edits_on` strategies from `tests/unit/core_strategies.py`; random fake steps proposing random edits): no crash on any document; accepted edits always pass `check_edits`; every proposed edit has exactly one status; every set-aside edit overlaps its winner, which comes earlier; switching a category off never changes a switched-on category's accepted edits except to accept edits it had set aside; the whole run is idempotent (rebuild from script, run again, same script). Runs in the nightly profile too.
- Conformance: `test_textprep_conformance.py` runs `check_text_step(step, allow_ask=False)` for every step in `BUILT_IN_STEPS`, so every wave-2 step is checked when it is registered, and "no built-in v1.0 step emits ask" is enforced. Plus tests that `check_text_step` catches each kind of bad step (one fake per check), and a subprocess test that `import sci2audio.testing` loads neither pytest nor hypothesis.
- Corpus: on all 7 papers, the furniture step removes exactly the furniture blocks with text and nothing else, and every other block reads as printed; a syrupy snapshot of the run summary per paper (edits per category and status) so later rule PRs show their effect as a small diff.
- **English regression harness (#4, golden):** `tests/regression/english.toml`, one `[[case]]` per row of the English audit (14), taken from `sample_en.md` (written for the audit in the KB repo, project-owned, no third-party text). Each case: `id`, `audit` row, `issue` that owns the rule (#64 to #68), `blocks` (kind and text), `expected` (the script the built-in steps produce **today**), `goal` (one line: what the owning issue must reach, as a note, not exact wording, so this PR decides no rule wording). One parametrised test compares `render(run)` with `expected` and prints the diff. Today 13 cases read unchanged and case 14 (running footer as a FURNITURE block) reads nothing. Each rule PR then changes its cases' `expected` first (test-first), and the diff shows the before/after (tests.md).

## 4. PR B: the utterance cutter (Q4)

- `textprep/utterances.py`: `Utterance(text, span, pause=False)` (frozen, textprep-owned, no core change); `cut_utterances(pieces, language="en", max_chars=300) -> tuple[Utterance, ...]`. The voice gets `utterance.text` (a string, never a Document); the app makes one `AudioChunk(utterance.span, …)` per utterance.
- Rules: pieces of different blocks never share an utterance; a pause piece is its own pause utterance; text is `spoken_text`; a sentence ends after `.`, `?` or `!` (with closing quotes or brackets) followed by whitespace and an upper-case letter, digit or opening quote/bracket, except after an English abbreviation (Fig., Eq., Sec., Tab., et al., e.g., i.e., cf., vs., Dr., Mr., Ms., Prof., No., approx., resp., ca., incl.) or a single initial ("J. Smith"). Other languages use the same punctuation rule without the abbreviation list until a language table is added.
- Fallback cut (Kokoro takes at most about 510 phoneme tokens per call): a sentence over `max_chars` is cut at the last `;` or `:`, else `,`, else a dash, else the last space before the limit; a single token longer than the limit (a long sequence) is cut hard. Default 300 characters, a parameter, so #18 can lower or raise it to the voice's real limit.
- Spans: an utterance's span runs from the original offset of its first spoken character to the end of its last, inside one block; kept text maps one to one, so cuts inside kept text are exact; a cut is never placed inside a replacement unless the replacement alone is over the limit (then the later parts get an empty span at the replacement's end, so spans never overlap). Removed text between pieces lies inside the span (the audio stands for that stretch of the original).
- Tests: unit cases (each abbreviation, initials, decimals "p < .05", "et al. (2019)", quotes and brackets, headings without a full stop, a pause, a 1,000-character sentence with and without clause marks, a 400-character token); Hypothesis: no crash, every utterance non-empty and at most `max_chars`, spans inside one block, in order and never overlapping, and the utterance texts joined by spaces equal the blocks' spoken text (nothing lost or added); corpus: every paper cuts with all utterances under the limit; a `benchmark` test on the largest paper plus a row in `docs/baseline.md` (tests.md: a step that can take long). Regression cases get an optional `utterances` list for cases where sentence ends matter ("Approx.", "Fig. 1").

## 5. Decisions this plan asks the coordinator to make (for the KB)

1. Split into PR A and PR B as above.
2. The ten categories and their labels.
3. D-57's "stage" means `block` or `inline`, and the registry check enforces block steps first (Q15's coarse-to-fine rule made checkable).
4. Steps in switched-off categories still run; their edits are reported as switched off and never block others.
5. A failing or invalid step is dropped with a problem in the result; the run never stops; tests run strict.
6. `StepContext` holds only the language in v1.0.
7. Regression cases pin today's output (`expected`) and carry a `goal` note and owning issue; no rule wording decided here.
8. `sci2audio.testing`: layer line `app | testing`, plus a forbidden contract for cli and web; its path joins lane textprep.
9. Cutter: textprep-owned `Utterance`, default `max_chars` 300, fallback order `; :` then `,` then dash then space.

## 6. Size

PR A about 600 lines of source and 700 of tests and data; PR B about 250 and 350. No new dependency (tomllib, difflib, bisect, socket are standard library), so no licence row.
