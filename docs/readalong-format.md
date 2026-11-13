# Read-along file format (version 1)

Written by the output stage (`sci2audio.output`, issue #69) next to the audio files as
`<Book>.readalong.json`. It tells a player when each chunk of the voice is spoken and which
original words it reads, so the player (#78) can highlight the document's own block text
(OU-02, decision Q9). Output owns this format; `sci2audio.output.read_readalong` reads it. The
browser's Listen page (`sci2audio.web.player`) uses it with the audio job's `document.json`.

The file is written last, after every audio file it names is complete. If it exists, the
audio is complete. A run that replaces earlier output removes the old file first.

## Example

Shown indented for reading. The file itself is compact JSON in UTF-8, with the keys in this
order.

```json
{
  "format": "sci2audio-readalong",
  "version": 1,
  "sample_rate": 24000,
  "duration": 6.6,
  "m4b": "A Study of Tones.m4b",
  "chapters": [
    {"title": "Introduction", "mp3": "A Study of Tones - 01 Introduction.mp3",
     "start": 0.0, "end": 2.45, "first_chunk": 0}
  ],
  "chunks": [
    {"chapter": 0, "start": 2.0, "end": 2.1, "block": 0, "start_char": 0, "end_char": 5}
  ]
}
```

## Fields

| Field | Meaning |
|---|---|
| `format` | Always `"sci2audio-readalong"`. |
| `version` | `1`. A reader refuses any version it does not know. |
| `sample_rate` | Sample rate of the audio in Hz. All times below were exact sample counts before rounding. |
| `duration` | Length of the whole book in seconds (the M4B). |
| `m4b` | File name of the M4B in the same folder, or `null` if no M4B was written. |
| `chapters[]` | One entry per chapter, in order. |
| `chapters[].title` | The chapter title, as given (not the cleaned file name). |
| `chapters[].mp3` | File name of the chapter's MP3 in the same folder, or `null` if no MP3s were written. |
| `chapters[].start`, `end` | Where the chapter starts and ends on the book's timeline, in seconds. A chapter starts with the chapter pause, so its first chunk starts a little later. |
| `chapters[].first_chunk` | Index into `chunks` of the chapter's first chunk. |
| `chunks[]` | One entry per chunk of the voice, in the order spoken. |
| `chunks[].chapter` | Index into `chapters`. |
| `chunks[].start`, `end` | When the chunk's speech starts and ends on the book's timeline, in seconds. The pause before a chunk belongs to no chunk. |
| `chunks[].block`, `start_char`, `end_char` | The original text the chunk reads: block index in the document, and the character offsets `[start_char, end_char)` in that block's text (a core `Span`). |

## Times

- Times are in seconds, rounded to 3 decimals (1 ms).
- They count on the M4B's timeline. Inside a chapter's MP3, the time of a chunk is `chunk.start - chapter.start`.
- They assume the player decodes without a gap at the start: the AAC edit list in the M4B and the LAME header in each MP3 are honoured. ffmpeg, browsers and most players do this. A player that ignores them is about 45 ms late.

## Changes

A change that adds a field a reader may ignore keeps version 1. A change that removes a field or changes its meaning gets version 2, and this file is updated in the same pull request.
