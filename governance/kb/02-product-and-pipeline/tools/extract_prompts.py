"""Regenerate the verbatim prompt appendices of doc-prompts-and-detector-rules.md from the code.

Usage (from the audiobook-generator repository root, with sci2audio installed):
    python -I path/to/extract_prompts.py path/to/doc-prompts-and-detector-rules.md

It cuts the file at the first line "## Appendix A" (if present) and appends Appendices A–F freshly
extracted from sci2audio/prompts.py and sci2audio/sprechfassung.py, so the KB never drifts from the code.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))

from sci2audio import prompts as p  # noqa: E402
from sci2audio import sprechfassung as s  # noqa: E402


def block(title: str, note: str, text: str, lang: str = "text") -> str:
    return f"\n## {title}\n\n{note}\n\n````{lang}\n{text.strip()}\n````\n"


def appendices() -> str:
    notes = "\n\n".join([
        "### PRENORMALIZED_NOTE\n" + p.PRENORMALIZED_NOTE,
        "### ENGLISH_NOTE\n" + p.ENGLISH_NOTE,
        "### SHORT_SOURCES_NOTE\n" + p.SHORT_SOURCES_NOTE,
        "### SENTENCE_LIMIT_NOTE\n" + p.SENTENCE_LIMIT_NOTE,
        "### USER_INSTRUCTION\n" + p.USER_INSTRUCTION,
        "### GLOSSARY_INSTRUCTION\n" + p.GLOSSARY_INSTRUCTION,
        "### FOREIGN_INSTRUCTION\n" + p.FOREIGN_INSTRUCTION,
        "### NO_CONTEXT_MARKER\n" + p.NO_CONTEXT_MARKER,
        "### VERIFY_SYSTEM_PROMPT\n" + p.VERIFY_SYSTEM_PROMPT,
    ])
    return "\n".join([
        block("Appendix A: classic rewrite system prompt (`prompts.SYSTEM_PROMPT_TEMPLATE`)",
              "Placeholders filled per run; identical for every chunk so providers can cache it.",
              p.SYSTEM_PROMPT_TEMPLATE),
        block("Appendix B: notes, user instructions and verify prompt (`prompts.py`)",
              "Appended depending on settings.", notes),
        block("Appendix C: Sprechfassung, Klar & Direkt, German (`klar-de.md`)",
              "Claude Haiku, effort high, whole subchapters.",
              s.SYSTEM_PROMPT + "\n\n### NUMBERED_NOTE\n" + s.NUMBERED_NOTE + "\n\n### CONTEXT_NOTE\n"
              + s.CONTEXT_NOTE + "\n\n### GLOSSARY_NOTE\n" + s.GLOSSARY_NOTE),
        block("Appendix D: Sprechfassung, Akademisch & Flüssig, German (`akademisch-de.md`)",
              "Claude Sonnet, effort medium, ≈ 900-word groups.", s.SYSTEM_PROMPT_AKADEMISCH),
        block("Appendix E: English variants (`klar-en.md`, `akademisch-en.md`)", "Same rules in English.",
              "### SYSTEM_PROMPT_EN\n" + s.SYSTEM_PROMPT_EN + "\n\n### SYSTEM_PROMPT_AKADEMISCH_EN\n"
              + s.SYSTEM_PROMPT_AKADEMISCH_EN),
        block("Appendix F: retry hints after failed checks (`sprechfassung._HINTS`)",
              "Inserted into the targeted second try.", json.dumps(s._HINTS, ensure_ascii=False, indent=2), "json"),
    ])


def main(target: str) -> None:
    path = Path(target)
    text = path.read_text(encoding="utf-8")
    cut = text.find("\n## Appendix A")
    if cut != -1:
        text = text[:cut] + "\n"
    path.write_text(text + appendices(), encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1])
