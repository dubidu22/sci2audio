"""The README's "What the rules do" example is what sci2audio reads (#80): the paragraph
as printed, run through `sci2audio script`, gives the spoken text and the report lines the
README quotes, so the README cannot drift from the rules."""

from __future__ import annotations

import re
from pathlib import Path

from cli_helpers import Cli

README = Path(__file__).resolve().parents[2] / "README.md"


def quotes(section: str) -> list[str]:
    """The block quotes and the text block of one README section, in order."""
    text = README.read_text(encoding="utf-8").split(f"## {section}\n", 1)[1].split("\n## ", 1)[0]
    quoted = [line[2:] for line in text.splitlines() if line.startswith("> ")]
    block = re.search(r"```text\n(.*?)```", text, re.DOTALL)
    assert block, "the section shows report lines in a text block"
    return [*quoted, block.group(1)]


def test_the_readme_example_is_what_sci2audio_reads(tmp_path: Path) -> None:
    printed, spoken, report_lines = quotes("What the rules do")
    source = tmp_path / "example.txt"
    source.write_text(f"Results\n\n{printed}\n", encoding="utf-8")
    result = Cli(tmp_path)("script", source, "-o", tmp_path / "out", "--ignore-settings")
    assert result.code == 0, result.err

    script = (tmp_path / "out" / "example.script.txt").read_text(encoding="utf-8")
    after_heading = script.split("\nResults\n", 1)[1]
    assert " ".join(after_heading.split()) == spoken

    report = (tmp_path / "out" / "example.report.md").read_text(encoding="utf-8")
    edits = [line for line in report.splitlines() if line.startswith("- page ")]
    count = re.search(r"lists all (\d+) changes", README.read_text(encoding="utf-8"))
    assert count, "the section says how many changes the report lists"
    assert int(count.group(1)) == len(edits)
    shown = [
        re.sub(r"^- page \d+, chapter \d+, applied: (.*?) Step: [\w-]+\.$", r"\1", line)
        .replace("\\[", "[")
        .replace("\\]", "]")
        .replace("\\<", "<")
        for line in edits
    ]
    for line in report_lines.strip().splitlines():
        assert line in shown, f"README report line not in the report: {line}"
