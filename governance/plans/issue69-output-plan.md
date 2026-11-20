# Plan: issue #69, output stage (MP3 per chapter, M4B, read-along JSON)

Thread "Write audio files with ffmpeg", 12 Nov 2026. Critical (risk:high dependency, new stage contract): waits for the coordinator's approval. Binding inputs: plan Q5, Q8, Q9 (`plans/v1-remaining-plan.md`), review notes (`plans/v1-remaining-plan-review.md`).

## 1. Facts checked today (imageio-ffmpeg 0.8.1, all 7 wheels downloaded and inspected)

| Wheel | Bundled binary | Build flags | Licence of the binary | libmp3lame | native aac | ipod (M4B) muxer, ffmetadata |
|---|---|---|---|---|---|---|
| manylinux x86_64 | ffmpeg n9.0.2 (173 MB unpacked) | `--enable-gpl --enable-version3`, `--disable-libfdk-aac`, no `--enable-nonfree` | GPL-3.0-or-later | yes | yes | yes |
| manylinux aarch64 | n9.0.2 | same | GPL-3.0-or-later | yes | yes | yes |
| macOS x86_64 | v9.0.2 | `--enable-gpl --enable-version3`, no nonfree | GPL-3.0-or-later | yes | yes | yes |
| macOS arm64 | v9.0 (52 MB) | `--enable-gpl` without `--enable-version3`, no nonfree | GPL-2.0-or-later | yes | yes | yes |
| Windows x86_64 | v9.0.2 | `--enable-gpl --enable-version3`, no nonfree | GPL-3.0-or-later | yes | yes | yes |
| Windows arm64 | v9.0.1 | same | GPL-3.0-or-later | yes | yes | yes |
| Windows 32-bit | **v4.2.2** (old) | `--enable-gpl --enable-version3`, no nonfree | GPL-3.0-or-later | yes | yes | yes |

- Wrapper licence: BSD-2-Clause. No ffprobe in any wheel (confirmed).
- `imageio_ffmpeg.get_ffmpeg_exe()` makes no network call: it tries `IMAGEIO_FFMPEG_EXE`, the bundled binary, a conda ffmpeg, then `ffmpeg` on PATH.
- No `--enable-nonfree` anywhere, so the binaries are redistributable. We do not redistribute them ourselves (they come from PyPI as a dependency); a later native installer that bundles them would need a source offer. Written into `THIRD_PARTY_LICENSES.md`.
- Prototype with the Linux binary: a PCM stream piped in, chapters from an `;FFMETADATA1` file (`TIMEBASE=1/sample_rate`), a JPEG cover as `attached_pic`, `-f ipod` gives a valid M4B; `ffmpeg -i x.m4b -f ffmetadata -` reads title, artist, comment and both chapters back with sample-exact START/END; decoding to raw PCM gives exactly the samples put in (AAC and also MP3, whose LAME gapless header ffmpeg honours).

## 2. Design

### Input types (defined in `output`, built by the app, #71)

```python
class Pause(StrEnum):          # the silence placed BEFORE a chunk
    NONE, SENTENCE, PARAGRAPH, HEADING, PAUSE_EDIT, CHAPTER

@dataclass(frozen=True)
class Spoken:                   # one chunk and the pause before it
    chunk: AudioChunk
    pause: Pause = Pause.SENTENCE

@dataclass(frozen=True)
class Chapter:
    title: str
    first: int                  # index of its first Spoken; first chapter starts at 0, strictly increasing

@dataclass(frozen=True)
class BookInfo:
    title: str
    authors: tuple[str, ...] = ()
    language: str = "en"        # BCP 47; mapped to ISO 639-2 for the audio stream
    cover: Path | None = None   # JPEG or PNG, checked by magic bytes

@dataclass(frozen=True)
class OutputSettings:
    chapter_pause: float = 2.0  # Q8
    heading_pause: float = 1.0  # Q8
    paragraph_pause: float = 0.6  # Q8
    pause_edit: float = 0.5     # Q8
    sentence_pause: float = 0.3 # NOT in Q8, see open point A
    mp3: bool = True
    m4b: bool = True
    mp3_bitrate: str = "64k"    # mono speech
    aac_bitrate: str = "64k"
```

The app decides which `Pause` each chunk gets (first chunk of a chapter: CHAPTER; after a heading: HEADING; first chunk of a new block: PARAGRAPH; after a `pause` edit: PAUSE_EDIT; a Q4 clause cut inside a sentence: NONE; otherwise SENTENCE). Output only maps kinds to seconds, so it never needs the `Document`. A helper `Pause.strongest(*kinds)` lets the app combine two reasons (e.g. a pause edit at a paragraph end).

### Entry point

```python
def write_audiobook(job_folder: Path, out_folder: Path, chapters, spoken, book: BookInfo,
                    settings: OutputSettings = OutputSettings(), *, ffmpeg: Ffmpeg | None = None,
                    overwrite: bool = False) -> Written
```

Returns the written paths (M4B, MP3s, read-along JSON).

### How audio is joined (exact timing, no temp WAVs)

1. Chunk files are **WAV, 16-bit PCM, mono, one sample rate for the whole job** (open point B). Output reads each header with the stdlib `wave` module; a chunk in another format, a different rate or a missing file stops with an error naming the chunk.
2. A pure function `plan_timeline(...)` computes, in samples, where every pause and chunk starts and ends, and the chapter ranges. **Timing comes from the WAV frame counts, not from `AudioChunk.duration`** (the voice's own figure may be rounded).
3. Per chapter, output streams the chapter's PCM (silence as zero bytes, then each chunk's frames) into one `ffmpeg` process on stdin: `libmp3lame`, ID3v2.3 tags, cover as APIC. For the M4B, it streams the whole book once more into one process: native `aac` in the `ipod` muxer, chapters from a generated ffmetadata file (`TIMEBASE=1/rate`, so chapter marks are sample-exact), cover as `attached_pic`, `+faststart`. Reading the chunk WAVs twice is cheap; no multi-GB temporary WAV is ever written.
4. The chapter pause sits at the **start** of each chapter (also the first), so every chapter file begins the same way and a jump to a chapter mark lands just before the speech.

### Metadata (AQ-04, OU-03)

- Every file: `title`, `album` (book title), `artist` (authors joined with "; "), `genre=Audiobook`, `language`, `encoder` left to ffmpeg, and **`comment = "AI-generated audio: text-to-speech made with sci2audio <version>."`** (the AQ-04 label; in ID3 it is a COMM frame, in MP4 the ©cmt atom). MP3s also get `track=n/N`.
- File names from the title: `<Book>.m4b`, `<Book> - 01 <Chapter>.mp3` (number padded to the chapter count, at least 2 digits), `<Book>.readalong.json`. A name cleaner removes characters Windows forbids and control characters, trims trailing dots and spaces, avoids reserved names (CON, NUL, COM1 ...), caps the length at 120 characters, and falls back to "audiobook" / "chapter".

### Safe writing (no half-written file, #10)

- Each file is written to `.<name>.partial` in the target folder, then `os.replace`d into place. Any exception (ffmpeg exit code, `OSError` such as disk full, a vanished folder, `KeyboardInterrupt`) removes the partial file. The partial names are fixed, so a later run also clears leftovers from a process that was killed outright.
- **Existing files are never overwritten unless `overwrite=True`** (the app's resume, #71, passes it for its own job folder). Deleting or overwriting user files is risk:high, so the default refuses with a clear error.
- The read-along JSON is written last, so its presence means the audio files it names are complete.

### ffmpeg behind one small interface (Q5)

- `find_ffmpeg()`: `imageio_ffmpeg.get_ffmpeg_exe()` first, then `shutil.which("ffmpeg")`; if both fail, `FfmpegNotFoundError` with a clear message (reinstall sci2audio, or install ffmpeg and put it on PATH, or set `IMAGEIO_FFMPEG_EXE`).
- `Ffmpeg.run(args, feed)` runs the binary with `-nostdin`-style safety: `-hide_banner -loglevel error`, **`-protocol_whitelist file,pipe` on every input**, so ffmpeg cannot open a network URL even if a path looks like one (CLAUDE.md: no network). A non-zero exit raises `FfmpegError` with the last lines of stderr.
- Tests inject a fake `Ffmpeg` to simulate failures.

### Read-along file, version 1 (Q9), owned by output

```json
{
  "format": "sci2audio-readalong",
  "version": 1,
  "sample_rate": 24000,
  "duration": 812.345,
  "m4b": "My Book.m4b",
  "chapters": [
    {"title": "Introduction", "mp3": "My Book - 01 Introduction.mp3", "start": 0.0, "end": 95.2, "first_chunk": 0}
  ],
  "chunks": [
    {"chapter": 0, "start": 2.0, "end": 4.512, "block": 3, "start_char": 0, "end_char": 42}
  ]
}
```

- Times in seconds (3 decimals) on the M4B timeline; inside a chapter MP3 the time is `start - chapter.start`. A chunk's `end` is the end of its speech; pauses belong to no chunk.
- `block`, `start_char`, `end_char` are the chunk's `Span` into the document's block text (the original words, Q9).
- Written down in `docs/readalong-format.md`; `read_readalong(path)` checks `format` and `version` and raises on an unknown version, for #78.
- Gapless note in the doc: times assume the player honours the encoder delay (AAC edit list, LAME header); a player that does not is off by about 45 ms.

### Modules

`output/ffmpeg.py`, `output/model.py` (types), `output/timeline.py` (pure), `output/wav.py` (header check, PCM stream), `output/names.py`, `output/readalong.py`, `output/write.py`; `output/__init__.py` exports the public names. Imports only `core`, the standard library and `imageio_ffmpeg` (lint-imports unchanged).

## 3. Tests (fast suite unless marked)

- **Unit:** types reject bad input (chapters not increasing, empty title, negative pause); name cleaner; pause mapping; ffmetadata escaping (`=`, `;`, `#`, `\`, newline in titles).
- **Hypothesis:** timeline (chunks never overlap, in order, chapter ranges tile the book, total = sum of frames and pauses, chapter boundaries fall on chapter pauses); name cleaner (never empty, no forbidden character, ≤ 120, idempotent); read-along round trip.
- **Real ffmpeg, small generated audio (no voice, no network), about 2–4 s in total:** a 3-chapter book of generated tones and silence; read back with `ffmpeg -i ... -f ffmetadata -` (chapters, title, AI label present in M4B and every MP3) and by decoding to raw PCM (exact sample counts per MP3 and for the M4B); cover present as an attached picture; `ffmpeg -i` stream line parsed for codec (mp3, aac) and sample rate. These run on all three systems in CI, because they are the proof the bundled binary works there (open point C).
- **Golden file (syrupy):** the read-along JSON of a small fixed job.
- **Fault injection:** ffmpeg exits non-zero mid-stream (fake); `OSError(ENOSPC)` while streaming and while writing the JSON; output folder removed between two chapters; a chunk file deleted during the run; a stale `.partial` from a killed run is cleared; existing file without `overwrite` refused. Each checks that no partial file and no half-written target remains.
- **ffmpeg missing:** both sources fail → `FfmpegNotFoundError` with the message; PATH fallback used when imageio-ffmpeg has no binary.
- **No network:** every ffmpeg command carries the protocol whitelist (checked on the argument list); a URL-like input path is refused by ffmpeg.
- **`benchmark`:** encode 10 minutes of generated audio to MP3s and M4B; row in `docs/baseline.md`.
- **`slow`:** a 2-hour book of silence and tones, checking chapter marks and the last chunk's time have no drift.

## 4. Dependency, licences, files touched

- `pyproject.toml`: `imageio-ffmpeg>=0.8.1,<0.9` (and `uv.lock`). Install size grows by 20–70 MB per platform (wheel), 50–175 MB unpacked.
- `THIRD_PARTY_LICENSES.md`: imageio-ffmpeg (BSD-2-Clause) and the bundled FFmpeg build per platform as in the table above, with libmp3lame (LGPL-2.0-or-later) named.
- PR body: the per-platform licence table, libmp3lame and aac confirmed (from the build flags and the encoder list), risk:high.
- Files: `src/sci2audio/output/**`, `tests/output/**`, `docs/readalong-format.md`, `docs/baseline.md`, `pyproject.toml`, `uv.lock`, `THIRD_PARTY_LICENSES.md`. Rough size: 700–900 lines of code, 700–900 lines of tests.

## 5. Open points for the coordinator (my recommendation first)

- **A. A pause between sentences.** Q8 decides chapter 2.0, heading 1.0, paragraph 0.6 and `pause` edit 0.5 s, but no value between two sentences of one paragraph (Kokoro's clips have almost no trailing silence, so 0 s runs sentences together). Recommend a fifth setting, `sentence_pause = 0.3 s`, and NONE (0 s) for a Q4 clause cut inside a sentence. (Note: the coordinator's message labelled the four values "chapter / paragraph / sentence / short pause"; I follow the plan's Q8 table, which wins.)
- **B. Chunk audio format.** Recommend: chunk files are WAV, 16-bit PCM, mono, one rate per job; output reads them with the stdlib and times from frame counts. This binds #18/#71 (the voice or the app writes the WAV). Alternative: accept any format and decode each chunk with ffmpeg (one process per chunk, about 10 minutes extra on a 10,000-sentence book, and timing only as exact as the decoder). This is a contract between stages, so I'd record it in the KB with the other #69 choices.
- **C. Real ffmpeg in the fast suite.** `.claude/rules/tests.md` says tests that need audio are `slow`. Recommend keeping 4–6 small real-ffmpeg tests (a few seconds of audio, about 3 s in total) in the fast suite, because they prove the bundled binary works on all three systems on every PR; the long and benchmark tests stay nightly.
- **D. Overwrite.** Recommend refusing to overwrite by default, `overwrite=True` for the app's own job folder (#71).

Out of scope (later issues or other PRs): Opus (OU-05, Could), per-chapter ZIP, SRT/VTT (OU-04, v1.1), cover extraction (#73), choosing pause kinds (#71), resume logic (#71).
