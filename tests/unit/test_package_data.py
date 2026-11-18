"""The wheel ships every file of the package, the data files too (#68, review of PR #116).

The word lists of the text steps are package data read with `importlib.resources`
(`textprep/data/en/*.toml`, D-229). Hatchling decides what goes in the wheel, offline, from
`pyproject.toml` and `.gitignore`; this asks it, so a list left out of the wheel fails here
and not in an installed app.
"""

import zipfile
from email.parser import Parser
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
        "sci2audio/textprep/data/en/sentence_openers.toml",  # #477, D-744 A4
        "sci2audio/textprep/data/de/sentence_openers.toml",
    } <= shipped()


def test_the_fonts_and_their_licences_are_in_the_wheel() -> None:
    # the interface's bundled fonts ship with their OFL texts (#385, D-670; OFL condition 2)
    fonts = PACKAGE / "web" / "static" / "fonts"
    wanted = {f"sci2audio/web/static/fonts/{path.name}" for path in fonts.iterdir()}
    assert len([name for name in wanted if name.endswith(".woff2")]) == 12
    assert {
        "sci2audio/web/static/fonts/OFL-atkinson.txt",
        "sci2audio/web/static/fonts/OFL-literata.txt",
        "sci2audio/web/templates/_icons.html",
        "sci2audio/web/templates/settings.html",
    } <= wanted | shipped()
    assert wanted <= shipped()


def test_the_wheel_names_the_font_licence_and_carries_its_texts(tmp_path: Path) -> None:
    # the wheel holds GPL code and OFL fonts: its metadata says both (PR #409 review S1)
    built = Path(
        next(WheelBuilder(str(ROOT)).build(directory=str(tmp_path), versions=["standard"]))
    )
    with zipfile.ZipFile(built) as wheel:
        names = wheel.namelist()
        info = next(name for name in names if name.endswith(".dist-info/METADATA"))
        metadata = Parser().parsestr(wheel.read(info).decode("utf-8"))
    assert metadata["License-Expression"] == "GPL-3.0-or-later AND OFL-1.1"
    assert set(metadata.get_all("License-File") or []) >= {
        "src/sci2audio/web/static/fonts/OFL-atkinson.txt",
        "src/sci2audio/web/static/fonts/OFL-literata.txt",
    }
    licences = {
        name.split(".dist-info/licenses/", 1)[1] for name in names if ".dist-info/licenses/" in name
    }
    assert {
        "src/sci2audio/web/static/fonts/OFL-atkinson.txt",
        "src/sci2audio/web/static/fonts/OFL-literata.txt",
    } <= licences
