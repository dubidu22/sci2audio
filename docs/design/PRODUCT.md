# Product

<!-- impeccable:product-schema 1 -->

> Product truth for the whole sci2audio app after the pivot to a free, open-source, local-only desktop app (ADR-007, 9 Nov 2026). Sources: the public repo `dubidu22/sci2audio` (README, CLAUDE.md, CHANGELOG, `src/sci2audio/web`, open Issues, as of 15 Nov 2026) and the knowledge base in `dubidu22/sci2audio-design/docs/kb`. It **replaces** the earlier `PRODUCT.md` of `dubidu22/sci2audio-design` (in its git history), which described the retired hosted service (credit, Stripe, AI text levels, Azure voices, admin). Nothing here describes the current look; visual decisions belong to DESIGN.md.

## Platform

web

A desktop app whose interface is local web pages: today `sci2audio ui` serves them on 127.0.0.1 and opens the system browser; installers with their own app window are planned (v1.3, #215). Design for a desktop window from a 13″ laptop upward, on macOS, Windows and Linux. Phone layouts are out of scope: phones play the exported MP3/M4B in any audiobook or podcast app, and an Android app is a "maybe later" (no iOS, because GPL conflicts with App Store terms).

## Users

- **Primary: students, PhD candidates and researchers in any field, internationally.** English first, German second. They want to listen to papers, theses and textbooks (on the commute, while walking, to rest their eyes, or alongside reading) without citations, footnote marks, page furniture and formulas wrecking the listening.
- **Accessibility users are a named core group:** dyslexic, low-vision, ADHD and other print-disabled readers who use text-to-speech to follow and focus. Read-along, reliable playback, and control over what is spoken are core for them, not extras.
- **Colin** (the owner) uses it himself and runs the project as a reference for AI-assisted development. That shapes the process, not the audience.
- **Contributors and plugin authors** (open source, GPL): text-step and voice plugins are planned (v1.3, #216).

Not served by design: fiction listeners who want multi-voice drama or emotional performance.

## Product Purpose

sci2audio turns a scientific or long-form text (PDF, EPUB, Markdown, plain text, or pasted text) into a **faithful** audiobook on the user's own computer. It works in three steps:

1. Read the file's structure (reading order, columns, headings, footnotes, captions, tables, figures, formulas).
2. Prepare a listening script with transparent, switchable rules.
3. Speak it with a local Kokoro voice, writing an M4B with chapters, one MP3 per chapter, a read-along file and optional SRT/WebVTT subtitles.

It also plays the result in a read-along view that highlights the original text sentence by sentence.

**Planned direction (confirmed by Colin, 15 Nov 2026):** sci2audio grows from "convert, then listen" into a place to **study while listening**. The user captures notes, verbatim quotes, bookmarks and flashcards at the sentence being read, and exports them to Zotero, Obsidian and Anki. Gemini's v2.0 player proposal (`docs/proposals/2026-11-gemini-player-v2/`) first described this; its feature ideas count as input, not as specification.

Success means the listener can follow a dense academic text by ear, trusts that nothing was silently rewritten, and can find their way back to and keep what mattered.

## Positioning

- **Faithful, not rewritten.** Every change to the text is a marked edit (remove, replace, pause, ask) with a reason. Changes appear in a report, are counted on the document page, and can be switched off by category. Nothing is summarised and nothing is changed silently (D-57).
- **The text preparation is the differentiator, not the voice.** sci2audio understands academic text: two-column layout, running heads, line-end hyphens, author-year and numeric citations, URLs and DOIs, statistics (t, p, CI, χ²), units, abbreviations, footnotes read right after their mark, and spoken notices for tables, figures and formulas in the text's language. Neighbouring tools (Abogen, Audiblez, commercial TTS readers) either read the raw text or rewrite it with AI.
- **Entirely local.** No account, no upload, no telemetry. The update check is off until the user turns it on in Settings; then sci2audio asks GitHub once a day for the number of its newest version, one request with no version number, no identifier and no cookie, and downloads and installs nothing. Otherwise the only network access is a voice download the user starts, shown file by file with size and licence first.
- **Free and open source** (GPL-3.0-or-later).

## Operating Context

- **Main flow today**, all local:
  1. **Open a document**: file or pasted text. The start page also lists documents opened before, and audiobooks made on the command line.
  2. **Document page**, in three numbered steps:
     - *Check what will be read:* chapters to read, with choose, deselect and reorder (the reference list and an EPUB's publisher pages are off by default); the categories of change, each switchable; every proposed change as "printed → read as → why → what became of it"; the text's language.
     - *Choose a voice:* speed, and a pace for spelled-out abbreviations.
     - *Make the audiobook:* output folder, and subtitles.
  3. **Job page**: progress with pages, sentences and time left; cancel. A run can be interrupted and resumed, because already spoken sentences are kept in a speech cache. When done: the files, their folder, and freeing the cache.
  4. **Listen page (read-along player)**: the text as printed with the sentence being read highlighted, and play from any sentence. Previous/next sentence and chapter, speed 0.75×–2×, scroll with the reading, and "continue from 3:12". It also lists what is not in the audiobook, and names the synthetic voice.
- **Other surfaces:** voice setup and download (packs per language, files, sizes, licences, hosts, explicit consent); the privacy page (every statement checked against the code); removing a document (what goes, what stays); error pages; a language switch (EN/DE).
- **Command line** with the same options (`script`, `convert`, `listen`, `voices download`, `clean`). It reads the interface's saved settings and never changes them.
- **Planned study layer:** capture at the current sentence while listening, review the captured material, export to Zotero (citations, quotes), Obsidian (notes, Markdown) and Anki (cards). The first version (v1.5) is decided in ADR-008 (`governance/kb/01-audit-and-roadmap/adr-008-study-layer.md`, D-850): marks, notes and quotes, a Captures page, and exports as files (Markdown, RIS, CSV); cards, card review and local connections to Zotero or Anki come later.
- **Documents range** from a few pages to books of 1,000+ pages with many nested chapters. Jobs take minutes to hours; the user may leave and come back.
- **Typical usage scenes:** at a desk next to Word, Overleaf, Zotero or a PDF viewer; listening with headphones, eyes on or off the screen; returning later to continue.

## Capabilities and Constraints

- **Input:** PDF (with a text layer; no OCR yet), EPUB, Markdown, TXT, pasted text. Size limits are refused with a clear message.
- **Languages:** text rules, spoken notices and voices for English (28 Kokoro voices) and German (Kokoro Thorsten). The text's language is detected when the file doesn't state it. The interface is in English and German (`strings/en.toml`, `de.toml`); every user-facing string exists in both, and layouts must survive longer German text.
- **Output:** M4B with chapters and cover, MP3 per chapter, a read-along file, an optional listening script and report (Markdown and JSON), optional SRT/WebVTT. The metadata labels the audio as AI-generated.
- **Hard technical rules:**
  - The interface binds to 127.0.0.1 only.
  - Pages load nothing from the internet, so fonts, icons and scripts must be bundled.
  - There are no network calls except the voice download the user starts and the update check the user turned on.
  - There is one interface, never a second UI (D-45).
  - The pipeline never stops mid-run to ask.
- **Built with:** FastAPI with server-rendered Jinja templates, plain CSS and JS (`src/sci2audio/web`). The browser tests include keyboard and axe-core checks.
- **Roadmap signals from open Issues:**
  - VoiceOver and screen-reader navigation (v1.0.1).
  - A subtitle track in the player; showing the figure, table or formula where its notice is spoken (v1.2).
  - Explaining a paper's own abbreviations (v1.2.x).
  - Installers with an app window, an opt-in update check, and public plugin interfaces (v1.3).
  - Word-level highlighting, and a personal abbreviation and pronunciation list (Later).
- **Undecided:**
  - The study layer after v1.5 (ADR-008): a local connection to Zotero or Anki, headphone and media-key capture, voice notes.
  - Whether phones ever get more than exported files.
  - A logo.

## Brand Commitments

- Name: **sci2audio**, lowercase; the "2" is part of the word. Domain: sci2audio.com, a static project site. There is no logo yet.
- **Voice:** plain, exact, explanatory English and German with no jargon. Say what a choice does and what stays where ("Your audiobook stays in …"). Name things by what the user knows ("left out", "read as"), not by pipeline stages.
- **Honest about AI:** the audio is labelled AI-generated, and the player names the synthetic voice.
- Users convert only texts they may use; sci2audio does not remove copy protection.

## Evidence on Hand

- The README specimen, a paragraph as printed vs. as read, with three report lines. This is the product's clearest demonstration.
- The test corpus `tests/corpus/` contains only openly licensed texts. Examples are the German "PrivacyScore" paper (arXiv 1705.08889, CC BY 4.0) and an EPUB of *The Time Machine* (public domain).
- The real interface strings in `src/sci2audio/web/strings/*.toml` are the source for copy.
- **Absent, so never fabricate:** users, testimonials, reviews, download or star counts, press, and quality benchmarks. Third-party texts never appear in the repo, screenshots or mockups.

## Product Principles

1. **Faithful and visible.** Every change to what is heard can be seen, explained and switched off. The user can always check "printed vs. read" for themselves.
2. **The text is the product.** The paper and the sentence being read come first on every reading surface; tools appear when needed and recede afterwards.
3. **Local means trustworthy.** State plainly what stays on this computer, what is written where, and what any network access does, before it happens.
4. **Leaving is normal.** Long jobs, interrupted runs and returning listeners are the usual case: every page makes sense on return, and failures say what happened and what was kept.
5. **Listening and studying work together.** Capturing a thought must not cost the thread of the argument: the audio's state (paused or playing) follows what the user is doing, and every capture is confirmed and can be undone.

## Accessibility & Inclusion

- The whole interface works with the keyboard alone and with screen readers (a README promise; there are browser tests with axe-core). VoiceOver navigation is an open v1.0.1 Issue.
- Read-along must serve sighted dyslexic and ADHD readers (a clear highlight, a calm page, control over pace) without flooding screen-reader users with announcements. Treat these as separate needs.
- Every visible element gets a text label in both languages. State is shown by form, not by colour alone. Light and dark appearances.
- Synchronized highlighting must stay fast on books of 1,000+ pages.
- Shortcuts must not collide with operating-system or browser shortcuts.
