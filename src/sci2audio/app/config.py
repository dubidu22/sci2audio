"""The settings file: the person's choices kept between runs (playbook 3.4).

A JSON file in the user's configuration folder (`default_config_file`, from platformdirs).
Only the command line and the server read and write it; a job gets its settings passed in
and never touches the file. The chosen chapters are not kept: they belong to one document.
A missing, unreadable or broken file never stops the program: what can't be read falls
back to the default, with a warning the caller shows.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import platformdirs

from sci2audio.app.files import write_text_atomically
from sci2audio.app.settings import JobSettings
from sci2audio.textprep import Category

CONFIG_NAME = "settings.json"
CONFIG_VERSION = 1
KEPT = (  # every JobSettings field but the chosen chapters
    "language",
    "switched_off",
    "voice",
    "speed",
    "output_folder",
)


def default_config_file() -> Path:
    """Where the settings file lives: the user's configuration folder for sci2audio.

    Windows `%APPDATA%\\sci2audio`, macOS `~/Library/Application Support/sci2audio`,
    Linux `$XDG_CONFIG_HOME/sci2audio` (usually `~/.config/sci2audio`).
    """
    folder = platformdirs.user_config_path("sci2audio", appauthor=False, roaming=True)
    return folder / CONFIG_NAME


def settings_to_data(settings: JobSettings) -> dict[str, Any]:
    """The settings as the file keeps them (without the chosen chapters)."""
    return {
        "version": CONFIG_VERSION,
        "language": settings.language,
        "switched_off": sorted(str(category) for category in settings.switched_off),
        "voice": settings.voice,
        "speed": settings.speed,
        "output_folder": None if settings.output_folder is None else str(settings.output_folder),
    }


def settings_from_data(data: object) -> tuple[JobSettings, list[str]]:
    """Settings from the file's data, and a warning for everything that was left out."""
    if not isinstance(data, dict):
        return JobSettings(), ["the settings file does not hold settings; using the defaults"]
    warnings = []
    version = data.get("version")
    if type(version) is not int or version != CONFIG_VERSION:  # true is not version 1
        warnings.append(f"the settings file has version {version!r}; reading what fits")
    values: dict[str, Any] = {}
    for key, value in data.items():
        if key == "version":
            continue
        if key not in KEPT:
            warnings.append(f"unknown setting {key!r} ignored")
            continue
        try:
            converted = _convert(key, value)
            JobSettings(**{key: converted})  # check it on its own
        except (TypeError, ValueError) as error:
            warnings.append(f"setting {key!r} ignored: {error}")
        else:
            values[key] = converted
    return JobSettings(**values), warnings


def load_settings(file: Path) -> tuple[JobSettings, list[str]]:
    """The settings kept in `file`, and warnings; the defaults if there is no file."""
    try:
        text = file.read_text(encoding="utf-8")
    except FileNotFoundError:
        return JobSettings(), []
    except (OSError, UnicodeDecodeError) as error:
        return JobSettings(), [f"the settings file can't be read ({error}); using the defaults"]
    try:
        data = json.loads(text)
    except (ValueError, RecursionError) as error:  # JSONDecodeError; nesting too deep
        detail = error if isinstance(error, ValueError) else "nested too deeply"
        return JobSettings(), [f"the settings file is damaged ({detail}); using the defaults"]
    return settings_from_data(data)


def save_settings(settings: JobSettings, file: Path) -> None:
    """Keep the settings in `file`, all or nothing (OSError if it can't be written)."""
    file.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(settings_to_data(settings), ensure_ascii=False, indent=2) + "\n"
    write_text_atomically(file, text, overwrite=True)


def _convert(key: str, value: object) -> object:
    if key == "switched_off":
        if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
            raise ValueError(f"expected a list of category names, got {value!r}")
        return frozenset(Category(name) for name in value)
    if key == "output_folder":
        if value is None:
            return None
        if not isinstance(value, str) or not value:
            raise ValueError(f"expected a folder, got {value!r}")
        return Path(value)
    if key in ("language", "voice") and not isinstance(value, str):
        raise ValueError(f"expected text, got {value!r}")
    return value
