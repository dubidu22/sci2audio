# Plan: SRT and WebVTT subtitles (#214, OU-04)

Lane: app/release (the change is mostly in `output`, wired through `app`, `cli` and `web`).
Branch `output/subtitles-214`, one PR. **Critical** (`risk:high`): it changes golden files
(the CLI help snapshot and the audio job record snapshot), so it waits for approval.

## What the person gets

With subtitles switched on, the output folder gets, next to the audio:

- one `.srt` and one `.vtt` per chapter MP3, named like the MP3 (`<book> - 01 <chapter>.srt`),
  times counted from the start of that MP3;
- one `<book>.srt` and one `<book>.vtt` for the M4B, on the M4B's timeline.

Per-chapter files exist only when MP3s are written, book files only when the M4B is written
(`--format` decides, as today). Subtitles are **off by default** and the choice is remembered
with the other settings.

## Design

### Where the text comes from

The read-along file has times and spans into the *printed* text, but no spoken text. The
issue asks for notices and replacements as they are spoken, so the spoken text has to travel
with each chunk. `app.audio.assemble` already holds it (`PlannedChunk.utterance.text`, the
exact text the voice got, plain text with no voice markup).

- `output.model.Spoken` gains `text: str = ""`, the spoken text of the chunk. This is output's
  own model, not a `core` dataclass and not a layer contract. `assemble` fills it in.
- Text the voice failed on (skipped utterances, D-162) has no chunk, so it has no cue.
  Removed text was never spoken, so it has no cue either. Pauses get no cue.

### Cue times equal the read-along times

`output/subtitles.py` is a new pure module. It builds cues from the same `Timeline` that
`readalong.build` uses, inside the same `write_audiobook` call. So the times match by
construction, not by re-reading a file.

- A cue never spans two chunks. A chunk is one sentence, or one piece of a long sentence cut
  at a clause mark (`utterances.py`). That means cues end at sentence ends.
- A chunk whose text fits one cue (at most 2 lines of 42 characters) is one cue, from the
  chunk's `start` to its `end`, exactly the read-along's two numbers.
- A longer chunk is cut into the fewest cues that fit. The cut goes at the last `;`, `:` or
  `,` that fits, otherwise at the last space. Its time is shared out in proportion to the
  characters of each cue. The first cue starts at the chunk's start and the last ends at its
  end, so the outer times still equal the read-along. The times inside are estimates; the
  voice gives no word times.
- Each cue's text is wrapped into at most two lines at the space nearest the middle. A single
  word longer than 42 characters (a URL or DOI) gets a line of its own and is never cut.
- Times are whole milliseconds, rounded from samples the way `readalong._seconds` rounds
  (3 decimals). Chapter files use `cue - chapter.start`, the rule `docs/readalong-format.md`
  already gives for MP3s.

### Formats

- **SRT**: numbered from 1 per file, `HH:MM:SS,mmm --> HH:MM:SS,mmm`, a blank line between
  cues, UTF-8 without BOM, `\n` line ends.
- **WebVTT**: `WEBVTT` header, `HH:MM:SS.mmm --> HH:MM:SS.mmm`. `&`, `<` and `>` are
  escaped. A cue's text never contains `-->` (it becomes `->`) and never holds an empty line.
- Both: a cue's text is the spoken text with runs of white space read as one space.

### Writing

`write_audiobook` writes the subtitle files with the existing `_atomic` helper (a `.partial`
name, then a rename). The existence check before any work covers them, and so does the
`overwrite` rule. They are written after the audio and **before** the read-along file, which
stays last because it vouches for the files around it. `Written` gains
`subtitles: tuple[Path, ...] = ()`. `app.audio.audiobook_files` lists them, so the app refuses
existing subtitle files before any speech, as it does for the MP3s (D-163). A run with
subtitles off never deletes subtitle files an earlier run left; this matches how MP3s of an
earlier run with more chapters are left alone today.

### Settings and interfaces

- `OutputSettings.subtitles: bool = False`.
- `JobSettings.subtitles: bool = False`, saved in `settings.json` like the voice and speed.
  `run_audio_job` passes it on into `OutputSettings`. A file without the key reads as
  `False`; `CONFIG_VERSION` stays 1.
- CLI: `--subtitles` ("also write SRT and WebVTT subtitles: one pair per chapter MP3 and one
  for the M4B").
- Web: a checkbox "Also write subtitles (SRT and WebVTT)" with a hint, in the audiobook
  settings on the document page, saved like the voice choice. The API settings models gain
  `subtitles`. `MEDIA_TYPES` gains `.srt` (`application/x-subrip; charset=utf-8`) and `.vtt`
  (`text/vtt; charset=utf-8`), and the job's file list includes the subtitle files.
- The audio record lists the subtitle file names (`"subtitles": [...]`).
- English and German strings; `docs/subtitles.md` (a short page next to
  `readalong-format.md`); a CHANGELOG entry.

## Tests

- **Unit, `output.subtitles`**:
  - SRT numbering from 1 with no gaps, and the time format (hours past 99 minutes, the
    millisecond comma, rounding at .0005);
  - VTT escaping and the `-->` rule;
  - wrap at 42 characters with at most 2 lines, and an over-long word on its own line;
  - cuts prefer clause marks;
  - a cue never crosses a chunk;
  - chapter times are relative to the chapter's start.
- **Hypothesis**: for any chunk texts and durations:
  - cues are in order and never overlap;
  - the first and last cue of each chunk sit on the chunk's read-along times;
  - no cue line is empty or over 42 characters unless it is one word;
  - the joined cue text equals the chunk text with white space collapsed (nothing lost,
    nothing added).
- **Against the read-along**: write a book with the fake voice. For every chunk, check that
  its cue boundaries equal the `start`/`end` in the written `.readalong.json`, in the book
  files and in every chapter file.
- **Validators, no new dependency**:
  - the bundled ffmpeg parses each written `.srt` and `.vtt` (`ffmpeg -i x.vtt -f srt -`), and
    the cue count and times survive the round trip; a few seconds, allowed in the fast suite
    (#69);
  - a browser test loads the book's `.vtt` as a `<track>` in Chromium and checks that the
    browser's own WebVTT parser reads every cue with the same times and text.
- **As spoken**: a document with a figure notice, a replaced abbreviation and a removed
  citation gives cues with the notice text, the spoken replacement and no citation. A
  skipped utterance (the fake voice fails on one) has no cue.
- **Faults** (tests.md, file writing): a subtitle write that fails (disk full injected) leaves
  no `.partial`, no read-along file and no half-written subtitle file; existing subtitle files
  are refused without `overwrite` before any speech; a run with `overwrite` replaces them.
- **CLI, web, config**:
  - `--subtitles` in the CLI writes the files;
  - the API's settings round trip keeps `subtitles`;
  - the checkbox is reachable by keyboard and labelled (axe);
  - `settings.json` without the key loads.
  - Schemathesis covers the changed schema.
- **Golden files that change, explained in the PR**: the CLI `audiobook --help` snapshot
  gains the `--subtitles` line, and the audio record snapshot gains `"subtitles": []`. The
  read-along snapshot does not change.

## Open choices (recommendation first)

1. **Default off, remembered** (recommended), or always on. Always on adds two files per
   chapter plus two for the book (26 more files for a 12-chapter book), which most listeners
   don't use.
2. **The choice in `JobSettings`** (recommended, so the web remembers it and the CLI and web
   share it), or only in `OutputSettings` next to `--format`, which the web would then have
   to pass on by itself.
3. **Validators: ffmpeg plus Chromium's parser** (recommended, no new dependency), or a
   Python validator package. The ones I know of (for example `webvtt-py`) only parse loosely,
   so they would check less than the browser does.

## Out of scope (follow-up issues)

- Subtitles in the web player (a `<track>` on its audio element).
- Word-level times. These need timestamps from the voice, which Kokoro does not give us
  today.

## Size

About 250 lines of code (`subtitles.py` about 150, plus the wiring), about 450 lines of
tests, and two strings files. It is one PR.
