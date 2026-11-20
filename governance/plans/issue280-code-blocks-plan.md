# Plan: code blocks are referenced, not read (#280)

Issue: https://github.com/dubidu22/sci2audio/issues/280 (milestone v1.0.1, labels bug, risk:high, lane:layout, lane:textprep).
Thread: "Skip code blocks like figures". Critical (core `BlockKind`, layout contract, golden files, KB): waits for the coordinator's approval. No code yet.

## 1. What happens today (measured on main d91a074)

| Input | What layout makes of the code | Read? |
|---|---|---|
| PDF, `joss2021-waskom-seaborn.pdf` p.2 (Colin's case) | 10 PARAGRAPH blocks, one per line (blocks 32-41). Every run `LMMono10-Regular`, no shaded box, no drawing behind it | Yes, line by line; `=` is even read "equals" ("g equals sns.relplot(", `test_app_corpus.ambr`) |
| Markdown, fenced and indented code | one PARAGRAPH per block, runs tagged `pre code` (`sci2audio-sample-note.md` block 15 and the indented block) | Yes |
| EPUB `<pre><code>` | same tagged layout as Markdown: PARAGRAPH (D-410 chose this on purpose; placeholder was the alternative not chosen) | Yes |
| Plain text | no fonts, no markup | nothing to detect |

Whole-monospace lines elsewhere in the corpus (scan of all 8 papers, every run in a typewriter font):
- `acl2023-nowak` blocks 5-6: `https://github.com/rycolab/` + `prefix-parsing` (a URL in the author block, two lines). **Must stay read** (links step handles it).
- Everything else is a monospace word, e-mail or URL inside a proportional paragraph (seaborn prose, hardt, chi, arsiwalla references): not touched by the rule below, because it only looks at blocks made wholly of monospace lines.

## 2. Design

### 2.1 Core (one line of contract)
- `BlockKind.CODE = "code"`, added to `PLACEHOLDER_KINDS` (so `is_placeholder` is true, the player's notice box and the steps that already skip placeholders treat it like a figure). No label (not in `LABELLED_KINDS`). `document.json` just gains the value "code"; no export version exists to bump.

### 2.2 Layout, PDF: new `layout/code.py`, `find_code(blocks, content)`
- A line is **monospace** when every run with visible text uses a typewriter font, by font name (subset prefix already stripped): `mono` (not `monotype`), `courier`, `typewriter`, `consol`, `menlo`, `monaco`, `inconsolata`, `code` (SourceCodePro, FiraCode), and the TeX `tt` families (`cmtt`, `sftt`, `txtt`, `lmtt`, `ectt`). Font name only, so extraction and its golden files do not change.
- A run of PARAGRAPH blocks next to each other in reading order, each made only of monospace lines, becomes **one CODE block** (parts kept in order, lines joined by line breaks as found). Headings, captions, footnotes, list items and furniture are never taken.
- Not code: a run whose text, line breaks removed, is one URL, e-mail address or DOI (the nowak case). A single monospace line on its own ("pip install seaborn") is code.
- Runs in `build_document` after `find_lists`, before reading order and headings, so section indices stay right.
- A listing broken by a page break becomes two CODE blocks (two notices). Accepted for now.
- Indentation is not rebuilt (PDF lines carry no leading spaces; layout must not add text). Follow-up issue.

### 2.3 Layout, EPUB/Markdown (`layout/tagged.py`): replaces D-410
- An element whose context holds both `pre` and `code` is CODE (Markdown renders every fenced and indented block that way; most EPUB listings too). A `pre` without `code` stays a PARAGRAPH that keeps its lines (poems, addresses, ASCII art in Gutenberg EPUBs). Inline `code` in a paragraph changes nothing (the context is what all runs share).

### 2.4 Textprep
- New category `Category.CODE = "code"`, label "Code blocks", on by default; switched off, code is read as today. A separate category because "tables and figures" is about something else and some listeners want code read.
- New `CodeNoticeStep` (`code-notices`) in `placeholders.py`, the same `_NoticeStep` as figures: the whole block is replaced by one notice, reason "this code block is not read; a short notice is read instead".
- Wording (`wording.py`, `unnamed[BlockKind.CODE]`): **"A code block is skipped."** / **"Ein Codeblock wird übersprungen."** House style of "A figure is skipped." rather than Colin's shorter "Code block skipped"; espeak-ng German reads "Codeblock" as `kˈoːtblɔk`, which is right.
- Steps that list placeholder kinds by hand also skip CODE: `notation.py`, `links.py`, `hyphens.SKIPPED_KINDS` (a "-" at a line end in code is not a hyphenation).

### 2.5 Player, script, report
- Player (`web/player.py`, `listen.html`): a CODE block read as its notice is the notice box, like a figure, but the code is shown **open** below the notice in a `<pre>` keeping its line breaks (a figure's found text stays folded in "Text found"). `translate="no"`.
- Script (`.script.txt`): only the notice, since it is what the voice says. Report (`.report.md/.json`): the edit with the original code, as for figures.
- Settings page: new switch text "Code blocks: skipped with a short notice" / "Codeblöcke: mit einem kurzen Hinweis übersprungen" (`web/strings/en.toml`, `de.toml`).

## 3. PRs (two, by lane)
1. **core + layout** (`lane:core`, `lane:layout`): `BlockKind.CODE`, `layout/code.py`, tagged rule, truth field, layout golden files. Between PR 1 and PR 2 code is still read (no step replaces it yet), only steps that skip placeholders stop editing inside it.
2. **textprep + web** (`lane:textprep`, `lane:web`): category, step, wording, player view, strings, app golden files.

Both target main (the v1.0.1 path from main to release/1.0 is the coordinator's call).

## 4. Golden files that change
- `tests/corpus/truth/README.md`: new field `code_blocks`, list of `{ page, count }` (as `unnumbered_formulas`); every truth file gets it: seaborn `[{ page = 2, count = 1 }]`, `sci2audio-sample-note` 2, every other file `[]` (nowak's URL is not one).
- `test_layout_corpus.ambr`: seaborn blocks 32-41 become one `code` block, later block numbers shift by 9. No other paper changes.
- `test_layout_tagged_corpus.ambr`: sample note, the fenced and the indented block become `code`.
- `test_app_corpus.ambr` (PR 2): seaborn's 10 code lines become "A code block is skipped."; sample note the same twice.
- Possibly `test_textprep_rules_corpus.ambr` and the tagged footnotes snapshot if they print kinds; each diff explained in the PR.
- Extraction golden files: unchanged.

## 5. Tests (written first)
- Layout unit: a run of monospace paragraphs is one CODE block holding all items in order; a monospace URL split over two lines stays a paragraph; a paragraph with one monospace word stays; a monospace heading stays a heading; a single monospace line is code; two listings separated by prose are two blocks; `Monotype Corsiva` is not monospace.
- Tagged unit: `pre code` is CODE, `pre` alone is a PARAGRAPH, inline `code` stays in its paragraph.
- Corpus truth test: CODE blocks per page equal `code_blocks` (PDF and own-format truths).
- Hypothesis: the existing "never fails, every item in exactly one block" properties cover the new pass; add "every line of a CODE block from a PDF is monospace".
- Textprep: notice step unit tests; English and German regression cases (input code, spoken notice); conformance fixture in `sci2audio.testing.text_steps` gets a CODE block; switched-off category reads the code.
- Player: unit test for the view (notice + code with line breaks); browser test that the code is visible and not a read-along element; axe check stays clean.

## 6. KB (numbers by the coordinator)
- Code blocks are placeholders: CODE kind, replaces D-410 and extends D-55's list.
- PDF detection by typewriter font name; URL-only runs stay read.
- Tagged detection: `pre` with `code`; `pre` alone stays a paragraph.
- Own category "Code blocks", on by default; wording en/de.
- Player shows the code open, the notice spoken.

## 7. Out of scope (follow-up issues)
- "Listing 3: ..." captions naming a code block ("Listing 3 is skipped.").
- Rebuilding indentation of PDF code from line positions.
- One notice for a listing broken across a page.
- Code in plain-text input.

## 8. Open choices (recommendation first)
1. Wording: "A code block is skipped." (house style) vs Colin's "Code block skipped." Recommend house style.
2. Category: own "Code blocks" vs folding into "Tables and figures". Recommend own.
3. Tagged: `pre`+`code` only vs every `pre`. Recommend `pre`+`code`.
4. Player: code shown open vs folded like figures. Recommend open.
5. Two PRs (core+layout, textprep+web) vs one. Recommend two, by lane.

Rough size: PR 1 about 150 lines of code and 250 of tests plus golden files; PR 2 about 80 lines of code and 150 of tests.
