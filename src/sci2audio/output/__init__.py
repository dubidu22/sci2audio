"""Output: one MP3 per chapter, one M4B with chapter marks, and the read-along file (#69).

Pipeline stage; may import only ``sci2audio.core`` (and the standard library and
imageio-ffmpeg). The app builds the input: the `Spoken` chunks with their pauses, the
`Chapter`s, the `BookInfo` and the `OutputSettings`; `write_audiobook` writes the files.
"""

from sci2audio.output.ffmpeg import (
    Ffmpeg,
    FfmpegError,
    FfmpegNotFoundError,
    find_ffmpeg,
)
from sci2audio.output.model import BookInfo, Chapter, OutputSettings, Pause, Spoken, Written
from sci2audio.output.readalong import (
    ChapterTimes,
    ChunkTimes,
    ReadAlong,
    ReadAlongError,
    read_readalong,
)
from sci2audio.output.wav import ChunkAudioError
from sci2audio.output.write import AI_LABEL, write_audiobook

__all__ = [
    "AI_LABEL",
    "BookInfo",
    "Chapter",
    "ChapterTimes",
    "ChunkAudioError",
    "ChunkTimes",
    "Ffmpeg",
    "FfmpegError",
    "FfmpegNotFoundError",
    "OutputSettings",
    "Pause",
    "ReadAlong",
    "ReadAlongError",
    "Spoken",
    "Written",
    "find_ffmpeg",
    "read_readalong",
    "write_audiobook",
]
