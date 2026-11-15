# Subtitles (SRT and WebVTT)

Written by the output stage (`sci2audio.output.subtitles`, issue #214, decision D-606) when
subtitles are switched on: "Also write subtitles (SRT and WebVTT)" on the document page, or
`--subtitles` on the command line. The choice is off by default and is saved with the other
settings; `--no-subtitles` switches a saved choice off for one run.

## Files

| File | Written when | Times count from |
|---|---|---|
| `<book> - 01 <chapter>.srt` and `.vtt` | MP3s are written | the start of that chapter's MP3 |
| `<book>.srt` and `<book>.vtt` | the M4B is written | the start of the M4B |

Each name is the MP3's or the M4B's name with another suffix. The files are UTF-8 with `\n`
line ends. They are written after the audio and before the read-along file. Like the audio
files, existing subtitle files are replaced only when you choose to replace them. A run with
subtitles off leaves subtitle files of an earlier run alone.

## Cues

- The text is what the voice speaks: notices ("Figure 2 is skipped."), spoken replacements and
  expanded abbreviations as heard, with no removed text. A sentence the voice failed on is not
  in the audio and has no cue. Runs of white space are shown as one space.
- A cue belongs to one chunk of the voice (about a sentence, or a part of a long sentence cut at a
  clause mark), so cues end at sentence ends. Pauses have no cue.
- A cue has at most 2 lines of at most 42 characters, the two lines as even as they can be. A
  word longer than a line (a URL or a DOI) gets a line of its own and is never cut.
- A chunk that fits one cue is shown from its start to its end. These are exactly the
  `start` and `end` of the chunk in the [read-along file](readalong-format.md), to the
  millisecond. Inside a chapter file a time is `start - chapter start`, the read-along's rule
  for MP3s.
- A longer chunk is split into the fewest cues that fit. The split comes after the last ";" or
  ":" that fits, else the last ",", else the last space. A clause mark counts only when the cue
  before it is at least half full. The chunk's time is shared out by characters. The first cue
  starts on the chunk's start, the last ends on its end, and the cues meet in between. Those
  inner times are estimates, because the voice gives no times for single words (#352).

## Formats

- SRT: cues numbered from 1, `HH:MM:SS,mmm --> HH:MM:SS,mmm`, a blank line between cues. SRT
  has no escapes, so a `-->` in the text is shown as `->`.
- WebVTT: the `WEBVTT` header, `HH:MM:SS.mmm --> HH:MM:SS.mmm`, with `&`, `<` and `>`
  escaped.

The tests check both files against the read-along times. They also read them back with the
bundled ffmpeg and read the WebVTT file with Chromium's own parser as a `<track>`.
