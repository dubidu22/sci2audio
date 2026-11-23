"""Output: one MP3 per chapter, one M4B with chapter marks, and the read-along file (#69);
`BookWriter` writes them chapter by chapter as the voice finishes each (#723);
`write_book_file` builds the whole book as one M4B or MP3 on request (#725).

Pipeline stage; may import only ``sci2audio.core`` (and the standard library and
imageio-ffmpeg). The app builds the input: the `Spoken` chunks with their pauses, the
`Chapter`s, the `BookInfo` and the `OutputSettings`; `write_audiobook` writes the files.
"""

from sci2audio.output.chapters import (
    BookChapter,
    BookWriter,
    ChapterAudio,
    chapter_fingerprint,
    write_book_file,
)
from sci2audio.output.ffmpeg import (
    Ffmpeg,
    FfmpegError,
    FfmpegNotFoundError,
    find_ffmpeg,
)
from sci2audio.output.model import (
    BookInfo,
    BookKind,
    Chapter,
    OutputSettings,
    Pause,
    Spoken,
    Written,
)
from sci2audio.output.readalong import (
    ChapterTimes,
    ChunkTimes,
    ReadAlong,
    ReadAlongError,
    read_readalong,
)
from sci2audio.output.wav import ChunkAudioError
from sci2audio.output.write import (
    AI_LABEL,
    Vouch,
    audiobook_targets,
    book_file_name,
    book_subtitles,
    write_audiobook,
)

__all__ = [
    "AI_LABEL",
    "BookChapter",
    "BookInfo",
    "BookKind",
    "BookWriter",
    "Chapter",
    "ChapterAudio",
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
    "Vouch",
    "Written",
    "audiobook_targets",
    "book_file_name",
    "book_subtitles",
    "chapter_fingerprint",
    "find_ffmpeg",
    "read_readalong",
    "write_audiobook",
    "write_book_file",
]
