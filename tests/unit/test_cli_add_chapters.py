"""`sci2audio convert --chapters` on a project that has chapters made (#726, LW-04): only
the missing ones are made; other settings exit 7 and name both choices."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from cli_helpers import Cli, files_in

TITLES = ("Alpha", "Beta", "Gamma")
BOOK = "\n\n".join(f"# {t}\n\nThe chapter {t} starts here. It ends with {t}." for t in TITLES)


@pytest.fixture
def cli(tmp_path: Path) -> Cli:
    return Cli(tmp_path)


@pytest.fixture
def source(tmp_path: Path) -> Path:
    path = tmp_path / "in" / "book.md"
    path.parent.mkdir(parents=True)
    path.write_text(BOOK, encoding="utf-8", newline="\n")
    return path


def test_convert_with_more_chapters_adds_only_the_missing(
    cli: Cli, source: Path, tmp_path: Path
) -> None:
    out = tmp_path / "out"
    assert cli("convert", source, "-o", out, "-q", "--chapters", "1").code == 0
    first = (out / "book - 01 Alpha.mp3").read_bytes()
    spoken = len(cli.voice.spoken)
    result = cli("convert", source, "-o", out, "-q", "--chapters", "1,3")
    assert result.code == 0, result.err
    new = cli.voice.texts[spoken:]
    assert new
    assert all("Gamma" in text for text in new)
    assert (out / "book - 01 Alpha.mp3").read_bytes() == first
    assert [n for n in files_in(out) if n.endswith(".mp3")] == [
        "book - 01 Alpha.mp3",
        "book - 03 Gamma.mp3",
    ]
    assert "book.m4b" in files_in(out)  # the CLI still writes the whole book in the job


def test_convert_with_other_settings_exits_7_and_names_keep_settings(
    cli: Cli, source: Path, tmp_path: Path
) -> None:
    out = tmp_path / "out"
    assert cli("convert", source, "-o", out, "-q", "--chapters", "1").code == 0
    spoken = len(cli.voice.spoken)
    result = cli("convert", source, "-o", out, "-q", "--chapters", "2", "--speed", "1.2")
    assert result.code == 7
    assert "speed: 1.0, now 1.2" in result.err
    assert "add --keep-settings or --overwrite" in result.err
    assert len(cli.voice.spoken) == spoken  # refused before any speech


def test_convert_with_keep_settings_adds_with_the_old_settings(
    cli: Cli, source: Path, tmp_path: Path
) -> None:
    out = tmp_path / "out"
    assert cli("convert", source, "-o", out, "-q", "--chapters", "1", "--speed", "1.2").code == 0
    spoken = len(cli.voice.spoken)
    result = cli("convert", source, "-o", out, "-q", "--chapters", "2", "--keep-settings")
    assert result.code == 0, result.err
    new = cli.voice.spoken[spoken:]
    assert new
    assert {speed for _, _, speed in new} == {1.2}
    assert all("Beta" in text for text, _, _ in new)
    assert "book - 02 Beta.mp3" in files_in(out)


def test_convert_keep_settings_with_script_writes_the_script_with_the_kept_settings(
    cli: Cli, source: Path, tmp_path: Path
) -> None:
    """#766: the script and report match the audio, which was made with the kept settings:
    the same switches and plugins, not the ones given on this command line."""
    out = tmp_path / "out"
    first = cli("convert", source, "-o", out, "-q", "--chapters", "1", "--off", "links,code")
    assert first.code == 0, first.err
    result = cli(
        "convert", source, "-o", out, "-q", "--chapters", "2", "--keep-settings", "--with-script"
    )
    assert result.code == 0, result.err
    report = json.loads((out / "book.report.json").read_text(encoding="utf-8"))
    assert report["settings"]["switched_off"] == ["code", "footnote-texts", "links"]
    assert "book.script.txt" in files_in(out)


def test_convert_keep_settings_with_script_keeps_the_plugins_off(
    cli: Cli, source: Path, tmp_path: Path
) -> None:
    out = tmp_path / "out"
    first = cli("convert", source, "-o", out, "-q", "--chapters", "1", "--no-plugins")
    assert first.code == 0, first.err
    result = cli(
        "convert", source, "-o", out, "-q", "--chapters", "2", "--keep-settings", "--with-script"
    )
    assert result.code == 0, result.err
    report = json.loads((out / "book.report.json").read_text(encoding="utf-8"))
    assert report["settings"].get("plugins") is False


def test_convert_keep_settings_with_overwrite_writes_the_script_with_the_given_settings(
    cli: Cli, source: Path, tmp_path: Path
) -> None:
    """--overwrite wins over --keep-settings: every chapter is made anew, script included."""
    out = tmp_path / "out"
    assert cli("convert", source, "-o", out, "-q", "--chapters", "1", "--no-plugins").code == 0
    result = cli(
        "convert",
        source,
        "-o",
        out,
        "-q",
        "--chapters",
        "2",
        "--keep-settings",
        "--overwrite",
        "--with-script",
        "--off",
        "links",
    )
    assert result.code == 0, result.err
    report = json.loads((out / "book.report.json").read_text(encoding="utf-8"))
    assert "links" in report["settings"]["switched_off"]
    assert report["settings"].get("plugins") is not False


def test_convert_keep_settings_with_script_keeps_the_language(
    cli: Cli, source: Path, tmp_path: Path
) -> None:
    out = tmp_path / "out"
    first = cli("convert", source, "-o", out, "-q", "--chapters", "1", "--language", "en")
    assert first.code == 0, first.err
    result = cli(
        "convert", source, "-o", out, "-q", "--chapters", "2", "--keep-settings", "--with-script"
    )
    assert result.code == 0, result.err
    report = json.loads((out / "book.report.json").read_text(encoding="utf-8"))
    assert report["settings"]["language"] == "en"


def test_convert_keep_settings_with_script_covers_the_chapters_the_audio_holds(
    cli: Cli, source: Path, tmp_path: Path
) -> None:
    """#784: the audio holds the chapters made before and the new ones, so the script and
    report cover those, in book order, not only this run's choice."""
    out = tmp_path / "out"
    assert cli("convert", source, "-o", out, "-q", "--chapters", "1").code == 0
    result = cli(
        "convert", source, "-o", out, "-q", "--chapters", "2", "--keep-settings", "--with-script"
    )
    assert result.code == 0, result.err
    report = json.loads((out / "book.report.json").read_text(encoding="utf-8"))
    assert report["settings"]["chapters"] == [0, 1]
    script = (out / "book.script.txt").read_text(encoding="utf-8")
    assert "not spoken" not in script.split("# 3. Gamma")[0]  # Alpha and Beta are heard
    assert script.index("# 1. Alpha") < script.index("# 2. Beta")
    assert "# 3. Gamma (not spoken)" in script


def test_convert_with_script_covers_the_chapters_the_audio_holds_without_keep_settings(
    cli: Cli, source: Path, tmp_path: Path
) -> None:
    """#808: with the same settings the audio adds to the earlier chapters' book, so the
    script and report cover what the audio holds, in book order."""
    out = tmp_path / "out"
    assert cli("convert", source, "-o", out, "-q", "--chapters", "1").code == 0
    result = cli("convert", source, "-o", out, "-q", "--chapters", "2", "--with-script")
    assert result.code == 0, result.err
    report = json.loads((out / "book.report.json").read_text(encoding="utf-8"))
    assert report["settings"]["chapters"] == [0, 1]
    script = (out / "book.script.txt").read_text(encoding="utf-8")
    assert script.index("# 1. Alpha") < script.index("# 2. Beta")
    assert "# 1. Alpha (not spoken)" not in script
    assert "# 2. Beta (not spoken)" not in script
    assert "# 3. Gamma (not spoken)" in script


@pytest.mark.parametrize("flags", [("--overwrite",), ("--keep-settings", "--overwrite")])
def test_convert_with_script_without_keeping_covers_the_chosen_chapters_only(
    cli: Cli, source: Path, tmp_path: Path, flags: tuple[str, ...]
) -> None:
    out = tmp_path / "out"
    assert cli("convert", source, "-o", out, "-q", "--chapters", "1").code == 0
    result = cli("convert", source, "-o", out, "-q", "--chapters", "2", "--with-script", *flags)
    assert result.code == 0, result.err
    report = json.loads((out / "book.report.json").read_text(encoding="utf-8"))
    assert report["settings"]["chapters"] == [1]
    script = (out / "book.script.txt").read_text(encoding="utf-8")
    assert "# 1. Alpha (not spoken)" in script
    assert "# 2. Beta (not spoken)" not in script


def test_convert_keep_settings_with_script_still_warns_of_a_chapter_the_book_lacks(
    cli: Cli, source: Path, tmp_path: Path
) -> None:
    """#784: the script keeps the chosen numbers the document lacks, so the report
    still warns of them."""
    out = tmp_path / "out"
    result = cli(
        "convert", source, "-o", out, "-q", "--chapters", "2,9", "--keep-settings", "--with-script"
    )
    assert result.code == 0, result.err
    report = json.loads((out / "book.report.json").read_text(encoding="utf-8"))
    assert report["settings"]["chapters"] == [1, 8]
    assert any("chapter 9 was chosen" in warning for warning in report["warnings"])


def test_convert_keep_settings_with_script_without_chapters_on_a_new_project(
    cli: Cli, source: Path, tmp_path: Path
) -> None:
    out = tmp_path / "out"
    result = cli("convert", source, "-o", out, "-q", "--keep-settings", "--with-script")
    assert result.code == 0, result.err
    script = (out / "book.script.txt").read_text(encoding="utf-8")
    assert "# 1. Alpha" in script
    assert "not spoken" not in script


def test_convert_keep_settings_with_script_without_chapters_adds_to_the_project(
    cli: Cli, source: Path, tmp_path: Path
) -> None:
    out = tmp_path / "out"
    assert cli("convert", source, "-o", out, "-q", "--chapters", "1").code == 0
    result = cli("convert", source, "-o", out, "-q", "--keep-settings", "--with-script")
    assert result.code == 0, result.err
    report = json.loads((out / "book.report.json").read_text(encoding="utf-8"))
    assert report["settings"]["chapters"] == [0, 1, 2]
    script = (out / "book.script.txt").read_text(encoding="utf-8")
    assert "not spoken" not in script


def test_convert_keep_settings_with_script_keeps_the_chosen_order(
    cli: Cli, source: Path, tmp_path: Path
) -> None:
    out = tmp_path / "out"
    result = cli(
        "convert", source, "-o", out, "-q", "--chapters", "3,1", "--keep-settings", "--with-script"
    )
    assert result.code == 0, result.err
    report = json.loads((out / "book.report.json").read_text(encoding="utf-8"))
    assert report["settings"]["chapters"] == [2, 0]
    script = (out / "book.script.txt").read_text(encoding="utf-8")
    assert script.index("# 3. Gamma") < script.index("# 1. Alpha")


def test_convert_with_script_on_a_new_project_keeps_the_chosen_order(
    cli: Cli, source: Path, tmp_path: Path
) -> None:
    out = tmp_path / "out"
    result = cli("convert", source, "-o", out, "-q", "--chapters", "3,1", "--with-script")
    assert result.code == 0, result.err
    report = json.loads((out / "book.report.json").read_text(encoding="utf-8"))
    assert report["settings"]["chapters"] == [2, 0]
    script = (out / "book.script.txt").read_text(encoding="utf-8")
    assert script.index("# 3. Gamma") < script.index("# 1. Alpha")


def test_convert_warns_of_a_chapter_the_book_lacks_fresh_and_when_adding(
    cli: Cli, source: Path, tmp_path: Path
) -> None:
    """#830: `--chapters 2,9` on a book of three chapters names 9 as ignored on stderr, in
    the document's own numbers, on a fresh run and when adding to an earlier one. The
    language is given, so its own warning stays out."""
    warning = (
        "sci2audio: warning: there is no chapter 9 (the document has chapters 1 to 3); ignored\n"
    )
    fresh = cli(
        "convert", source, "-o", tmp_path / "fresh", "-q", "--language", "en", "--chapters", "2,9"
    )
    assert fresh.code == 0, fresh.err
    assert fresh.err == warning
    out = tmp_path / "out"
    assert cli("convert", source, "-o", out, "-q", "--language", "en", "--chapters", "1").code == 0
    added = cli("convert", source, "-o", out, "-q", "--language", "en", "--chapters", "1,2,9")
    assert added.code == 0, added.err
    assert added.err == warning
    assert [n for n in files_in(out) if n.endswith(".mp3")] == [
        "book - 01 Alpha.mp3",
        "book - 02 Beta.mp3",
    ]
