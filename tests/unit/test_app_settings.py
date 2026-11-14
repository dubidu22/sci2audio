"""Job settings and the settings file (#70, playbook 3.4)."""

import json
from dataclasses import fields
from pathlib import Path

import pytest

from sci2audio.app import JobSettings, default_config_file, load_settings, save_settings
from sci2audio.app import config as config_module
from sci2audio.app.files import partial_path
from sci2audio.textprep import DEFAULT_SWITCHED_OFF, Category


def test_the_defaults() -> None:
    settings = JobSettings()
    assert settings.language == ""
    assert settings.switched_off == DEFAULT_SWITCHED_OFF == {Category.FOOTNOTE_TEXTS}  # D-142
    assert settings.chapters is None
    assert (settings.voice, settings.speed, settings.output_folder) == ("", 1.0, None)
    assert (settings.letter_pace, settings.letter_speed) == ("normal", 1.0)  # as before #295


@pytest.mark.parametrize(
    ("pace", "letter_speed"), [("normal", 1.0), ("slower", 0.7), ("slowest", 0.5)]
)
def test_each_letter_pace_gives_its_letter_speed(pace: str, letter_speed: float) -> None:
    """#295 (D-554): the paces measured in the issue."""
    assert JobSettings(letter_pace=pace).letter_speed == letter_speed


def test_values_are_normalised() -> None:
    settings = JobSettings(
        switched_off=[Category.CITATIONS],  # type: ignore[arg-type]
        chapters=[2, 0, 2],  # type: ignore[arg-type]
        speed=2,
        output_folder="out",  # type: ignore[arg-type]
    )
    assert settings.switched_off == frozenset({Category.CITATIONS})
    assert settings.chapters == frozenset({0, 2})
    assert settings.speed == 2.0
    assert isinstance(settings.speed, float)
    assert settings.output_folder == Path("out")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("language", "English"),
        ("language", "en_GB"),
        ("switched_off", frozenset({"citations"})),
        ("chapters", frozenset({-1})),
        ("chapters", frozenset({True})),
        ("speed", 0.4),
        ("speed", 2.5),
        ("speed", float("nan")),
        ("speed", True),
        ("speed", "1"),
        ("voice", 3),
        ("letter_pace", "fast"),
        ("letter_pace", ""),
        ("letter_pace", 0.7),
        ("letter_pace", None),
    ],
)
def test_bad_values_are_refused(field: str, value: object) -> None:
    with pytest.raises(ValueError, match=field.split("_")[0]):
        JobSettings(**{field: value})  # type: ignore[arg-type]


@pytest.mark.parametrize("language", ["en", "en-GB", "de", "pt-BR", "zh-Hant-TW"])
def test_language_tags_are_accepted(language: str) -> None:
    assert JobSettings(language=language).language == language


def test_the_file_keeps_every_setting_but_the_chosen_chapters(tmp_path: Path) -> None:
    kept = {f.name for f in fields(JobSettings)} - {"chapters"}
    assert set(config_module.KEPT) == kept
    settings = JobSettings(
        language="en-GB",
        switched_off=frozenset({Category.CITATIONS, Category.LINKS}),
        chapters=frozenset({1}),
        voice="af_heart",
        speed=1.25,
        letter_pace="slowest",
        output_folder=tmp_path / "Hörbücher",
    )
    file = tmp_path / "config" / "settings.json"
    save_settings(settings, file)
    loaded, warnings = load_settings(file)
    assert warnings == []
    assert loaded == JobSettings(
        language="en-GB",
        switched_off=frozenset({Category.CITATIONS, Category.LINKS}),
        voice="af_heart",
        speed=1.25,
        letter_pace="slowest",
        output_folder=tmp_path / "Hörbücher",
    )
    data = json.loads(file.read_text(encoding="utf-8"))
    assert data["letter_pace"] == "slowest"
    assert data["version"] == 1
    assert "chapters" not in data
    assert data["switched_off"] == ["citations", "links"]


def test_a_missing_file_gives_the_defaults_without_a_warning(tmp_path: Path) -> None:
    assert load_settings(tmp_path / "none.json") == (JobSettings(), [])


def test_a_file_without_the_switches_starts_from_the_default_ones(tmp_path: Path) -> None:
    file = tmp_path / "settings.json"
    file.write_text('{"version": 1, "voice": "af_heart"}', encoding="utf-8")
    settings, warnings = load_settings(file)
    assert (settings.switched_off, warnings) == (DEFAULT_SWITCHED_OFF, [])  # D-142
    file.write_text('{"version": 1, "switched_off": []}', encoding="utf-8")
    assert load_settings(file)[0].switched_off == frozenset()  # every category on, as chosen


@pytest.mark.parametrize(
    ("text", "warning"),
    [
        ("{not json", "damaged"),
        ("[1, 2]", "does not hold settings"),
        (b"\xff\xfe".decode("latin-1"), "damaged"),
    ],
)
def test_a_broken_file_gives_the_defaults_and_a_warning(
    tmp_path: Path, text: str, warning: str
) -> None:
    file = tmp_path / "settings.json"
    file.write_text(text, encoding="utf-8")
    settings, warnings = load_settings(file)
    assert settings == JobSettings()
    assert len(warnings) == 1
    assert warning in warnings[0]


def test_a_deeply_nested_file_gives_the_defaults_and_a_warning(tmp_path: Path) -> None:
    file = tmp_path / "settings.json"
    file.write_text("[" * 100_000 + "]" * 100_000, encoding="utf-8")
    settings, warnings = load_settings(file)
    assert settings == JobSettings()
    assert warnings == ["the settings file is damaged (nested too deeply); using the defaults"]


@pytest.mark.parametrize("version", [True, 1.0, "1", None])
def test_only_the_number_1_is_version_1(tmp_path: Path, version: object) -> None:
    file = tmp_path / "settings.json"
    file.write_text(json.dumps({"version": version, "speed": 1.5}), encoding="utf-8")
    settings, warnings = load_settings(file)
    assert settings == JobSettings(speed=1.5)
    assert warnings == [f"the settings file has version {version!r}; reading what fits"]


def test_an_unreadable_file_gives_the_defaults_and_a_warning(tmp_path: Path) -> None:
    file = tmp_path / "settings.json"
    file.write_bytes(b"\xff\xfe\x00bad")
    settings, warnings = load_settings(file)
    assert settings == JobSettings()
    assert "can't be read" in warnings[0]


def test_bad_fields_fall_back_one_by_one(tmp_path: Path) -> None:
    file = tmp_path / "settings.json"
    data = {
        "version": 1,
        "language": "en-GB",
        "switched_off": ["citations", "no-such-category"],
        "voice": 7,
        "speed": 9,
        "letter_pace": "fast",
        "output_folder": "",
        "chapters": [1, 2],
        "colour": "blue",
    }
    file.write_text(json.dumps(data), encoding="utf-8")
    settings, warnings = load_settings(file)
    assert settings == JobSettings(language="en-GB")
    assert len(warnings) == 7
    assert any("'letter_pace'" in w for w in warnings)
    assert any("'colour'" in w for w in warnings)
    assert any("'chapters'" in w for w in warnings)


def test_another_version_is_read_as_far_as_it_fits(tmp_path: Path) -> None:
    file = tmp_path / "settings.json"
    file.write_text(json.dumps({"version": 2, "speed": 1.5}), encoding="utf-8")
    settings, warnings = load_settings(file)
    assert settings == JobSettings(speed=1.5)
    assert warnings == ["the settings file has version 2; reading what fits"]


def test_saving_is_all_or_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    file = tmp_path / "settings.json"
    save_settings(JobSettings(speed=1.5), file)
    before = file.read_bytes()

    def full(*args: object) -> None:
        raise OSError(28, "No space left on device")

    monkeypatch.setattr("sci2audio.app.files.os.fsync", full)
    with pytest.raises(OSError, match="No space"):
        save_settings(JobSettings(speed=0.75), file)
    assert file.read_bytes() == before
    assert not partial_path(file).exists()


def test_the_settings_file_lives_in_the_users_config_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = []

    def config_path(appname: str, appauthor: object, roaming: bool) -> Path:
        calls.append((appname, appauthor, roaming))
        return tmp_path / appname

    monkeypatch.setattr(config_module.platformdirs, "user_config_path", config_path)
    assert default_config_file() == tmp_path / "sci2audio" / "settings.json"
    assert calls == [("sci2audio", False, True)]


def test_the_real_config_folder_is_named_for_sci2audio() -> None:
    file = default_config_file()
    assert file.name == "settings.json"
    assert file.parent.name == "sci2audio"


def test_a_file_from_before_the_letter_pace_reads_normal(tmp_path: Path) -> None:
    """Settings saved by v1.0 have no letter_pace (#295)."""
    file = tmp_path / "settings.json"
    file.write_text(json.dumps({"version": 1, "speed": 1.5}), encoding="utf-8")
    assert load_settings(file) == (JobSettings(speed=1.5), [])
