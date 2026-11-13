"""The wheel ships every file of the package, the data files too (#68, review of PR #116).

The word lists of the text steps are package data read with `importlib.resources`
(`textprep/data/en/*.toml`, D-229). Hatchling decides what goes in the wheel, offline, from
`pyproject.toml` and `.gitignore`; this asks it, so a list left out of the wheel fails here
and not in an installed app.
"""

from pathlib import Path

from hatchling.builders.wheel import WheelBuilder

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "src" / "sci2audio"


def shipped() -> set[str]:
    # hatchling gives the path with the system's separator ("\\" on Windows)
    files = WheelBuilder(str(ROOT)).recurse_included_files()
    return {f.distribution_path.replace("\\", "/") for f in files}


def test_every_package_file_is_in_the_wheel() -> None:
    files = {
        "sci2audio/" + path.relative_to(PACKAGE).as_posix()
        for path in PACKAGE.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
    }
    assert files - shipped() == set()


def test_the_word_lists_are_in_the_wheel() -> None:
    assert {
        "sci2audio/textprep/data/en/abbreviations.toml",
        "sci2audio/textprep/data/en/units.toml",
    } <= shipped()
