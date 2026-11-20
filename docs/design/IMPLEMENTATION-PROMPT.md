# Prompt for the project coordinator: implement "The Working Reader" design

A new design for the whole sci2audio app was made on 15 November 2026. It replaces the design this repository held before, which was made for the retired hosted service (Quick Start, text levels, credit, account, admin). Your job is to plan its implementation in the product repository **github.com/dubidu22/sci2audio** as Issues, and to coordinate them under that repository's `CLAUDE.md`. Every rule there still applies: Issues with acceptance criteria, one PR per Issue, plan first, tests first, a review in a separate thread, and no network calls.

Paths without a folder, and paths starting with `prototype/` or `proposals/`, are in this folder (`docs/design/`). Paths starting with `src/` or `tests/` are the product code in the same repository.

## What to read first, in this order

1. `PRODUCT.md`: the product after the pivot (ADR-007) — who it is for, what it promises, the hard technical rules, and what must never be invented. It replaces the earlier `PRODUCT.md`.
2. `DESIGN.md`: the design system. Tokens with light and dark values are in its frontmatter, followed by named rules, components, and do's and don'ts. `design.json` holds the same tokens in machine-readable form. Treat both as binding.
3. `prototype-app-brief.md`: the brief and the direction contract (thesis, first viewport, signature interaction). Read it once before the first Issue.
4. `prototype/`: the clickable reference of every page. Run `python3 -m http.server 8813` in `docs/design` and open `http://127.0.0.1:8813/prototype/index.html` at 1280 px or wider. The review switches `?theme=dark`, `?lang=de`, `?state=firstrun`, `?state=empty` and `?state=offline` show the other states; the rail item "Prototype states" does the same.
5. `prototype/screens/`: thirteen reference screenshots at 1440 × 900 (`listen-1280.png` at 1280 × 800), in light, dark and German. They are the quickest way to see what is meant.

`proposals/2026-11-gemini-player-v2/` holds the player proposal that started this redesign. It is input, not specification; `critique-academic-player-prototype-2026-11-15.md` explains what was kept and what was rejected.

## The design in five sentences

The app is the student's own marked-up copy of the paper: a white sheet on a cool grey desk, with a binder-cobalt rail as the shell. The voice sweeps the sentence it reads in highlighter yellow; every capture (note green, quote blue, card pink, mark orange) sticks out of the page edge as a small flag at its sentence, and the same flags run along the top of the player's timeline. Text that will not be read is struck through in pencil, never hidden, and every change shows "printed → read as → why". Atkinson Hyperlegible speaks for the app, Literata for the paper, and every number uses tabular figures. Fluorescents mean exactly one thing each and never appear on buttons, chips or navigation; primary actions are ink.

## Which page becomes which

| Prototype view (hash route) | Today in the product | What changes |
|---|---|---|
| Shell: cobalt rail, docked player | `templates/base.html` (header, language buttons, running-job line, footer) | The rail replaces the header and footer: wordmark, Library, Captures, Open a document, Voices; "Reading and recent" with progress and flag strips; Settings, Privacy, Keyboard shortcuts at the foot. The running job appears as a shelf item with its progress. The language switch moves to Settings. |
| Library `#/library` | `/` `templates/index.html` | The document list becomes a table: title and authors, a state chip with icon and word, listened, captures, last opened. Open a file or paste text inline at the top. Command-line audiobooks are rows labelled "Made on the command line". A missing voice becomes one notice with a link to Voices. Covers first run and an empty library. |
| Prepare `#/paper/<id>/prepare` | `/documents/{id}` `templates/document.html` | The same three steps, restyled: changes by category with a switch, a count and "printed → read as → why" examples; chapters; language; voice; make. The paper header with Prepare and Listen tabs is shared with Listen. |
| Making and failed (inside Prepare) | `/jobs/{id}` `templates/job.html` | Progress sits at the top of the document page: chapter, sentences, time left, with pause, resume and cancel. A failure names the chapter and the reason, and says how many chapters were kept. Keep `/jobs/{id}` as a route if the API needs it, but render it in this layout. |
| Listen `#/paper/<id>/listen` | `/documents/{id}/listen` `templates/listen.html`, `static/player.js` | The sheet in Literata with the yellow sweep that advances with the audio. Cut citations and statistics are struck in pencil; "said as" words carry their reading as a tooltip; footnotes are read after their mark; tables and figures appear as spoken-notice lines; page breaks are marked. Resume bar, one context panel (Captures, Changes, Outline) and the docked player. |
| Focus `#/paper/<id>/focus` | — | New. A mode of the Listen page: no rail, no panel, the current sentence at display size. F toggles it, Esc leaves it. |
| Captures `#/captures` | — | New, part of the study layer (see below). |
| Voices `#/voices` | `/voice` `templates/voice.html` | Packs per language with files, sizes, licences and hosts, explicit consent, and download progress. |
| Privacy `#/privacy` | `/privacy` `templates/privacy.html` | Restyled only. Every statement stays checked against the code. |
| Settings `#/settings` | — (settings are saved by the app, `app/settings.py`) | New page: appearance (system, light, dark), language, default output folder and speed, announcing sentences to screen readers, sounds. |
| Keyboard shortcuts (dialog, `?`) | — | New. Space, ← →, ⇧← ⇧→, − +, N Q C M, F, P, ?, Esc. Letter keys are ignored while typing and while ⌘, Ctrl or Alt is held. |
| — | `templates/missing.html`, `_remove.html` | Restyle in the same world; no prototype page exists for them. |

## Suggested Issues, in this order

Finish each one before starting the next. Write acceptance criteria from the prototype page and its screenshot.

1. **Foundation.** Port the tokens from `prototype/app.css` (light; dark under `prefers-color-scheme` and under an explicit setting) into `src/sci2audio/web/static/app.css`. Bundle the five font files from `prototype/fonts/`; both families are under the SIL Open Font License 1.1, so add them to `THIRD_PARTY_LICENSES.md` and ship the licence texts. Add the inline SVG icon sprite from `prototype/index.html`. No CDN, no icon font.
2. **Shell.** The rail and the new `base.html`, without the dock. Language moves to Settings, so add the Settings page here too.
3. **Library** on `/`, including first run, an empty library and command-line audiobooks.
4. **Prepare and making** on `/documents/{id}`, with the job inline and failures that keep finished chapters.
5. **Listen**: the sheet, the sweep, cancels in pencil, the resume bar, the context panel (Changes and Outline first; Captures waits for the study layer), and the dock on this page.
6. **Focus listening and the keyboard sheet.**
7. **Voices, Privacy, the not-found page and the removal dialog.**
8. **Study layer**: captures while listening, the Captures page, review, and export. Treat it as its own milestone (see below).

Every Issue adds its strings to `strings/en.toml` and `strings/de.toml` with the same keys; the German wording is in `prototype/i18n.js`, where "Captures" is "Fundstücke". Interface changes also run `uv run pytest -m browser` (keyboard and axe-core).

## Choices to make before or during planning

- **The player across pages.** In the prototype the dock stays at the bottom on every view, and playback continues while the user moves between pages. Server-rendered pages stop the audio when they navigate. My recommendation: the dock on Listen and Focus only, at first, and a "Continue listening" shelf item elsewhere. Navigating without a page load is a larger later step. Decide this, and record it as a decision.
- **The study layer is designed but not decided.** Its storage (captures need a data model, and changing `sci2audio.core` is critical), its export to Zotero, Obsidian and Anki, and the scope of the first version are open (PRODUCT.md, "Undecided"). The prototype shows the intended interaction: N, Q, C, M at the current sentence. A quote or mark is saved at once without pausing, with a short sound and a toast offering Undo; pressed in the first 1.2 s of a sentence, it belongs to the sentence that just ended. A note or card pauses playback and opens a box in the panel (⌘/Ctrl+Enter saves, Esc cancels). Write an ADR before its first Issue.
- **The wordmark** ("sci" "2" "audio" with the 2 in reading yellow) is a proposal, not a logo decision.

## Leave out of the product

- `prototype/data.js`: every paper, author and number in it is synthetic.
- The review switches (`?state=`, `?theme=`, `?lang=`) and the rail item "Prototype states".
- The simulated audio and the simulated job progress. The real timings come from the read-along file and the job API.
- The hash router. Pages stay server-rendered Jinja templates with plain JS, as now (D-45: one interface).

## How to check a page is done

- It matches its screenshot in `prototype/screens/` at 1440 px and 1280 px, in light and dark, and in German. Below 1280 px the context panel becomes an overlay and the reading column stays intact.
- Under reduced motion, the whole sentence is highlighted at once instead of swept, and nothing animates.
- No fluorescent colour appears on a chip, a button or the navigation; every state shows an icon and a word.
- Keyboard-only use works, axe-core reports nothing, and screen readers get no announcement for every sentence unless the setting is on.
