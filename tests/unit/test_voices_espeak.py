"""espeak-ng's data folder: refused with an error where espeak-ng would exit the process (#663)."""

from __future__ import annotations

import codecs
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from sci2audio.voices import ModelLoadError, espeak
from sci2audio.voices.espeak import (
    ESPEAK_PATH_LIMIT,
    check_espeak_data,
    wheel_data_path,
    windows_ansi_encoding,
)

SPEAK = (
    "import sys, misaki.espeak\n"
    "sys.stdout.reconfigure(encoding='utf-8')\n"  # Windows' console code page lacks IPA
    "from phonemizer.backend.espeak.wrapper import EspeakWrapper\n"
    "EspeakWrapper.set_data_path(sys.argv[1])\n"
    "g2p = misaki.espeak.EspeakG2P(language='de')\n"
    "print(g2p('Brücke')[0])\n"
    "print(g2p.backend._espeak._espeak.info()[1].decode())\n"  # the folder espeak-ng uses
)


def linked_data(base: Path, length: int) -> Path:
    """A folder `length` bytes long holding the wheel's espeak-ng data."""
    folder = base.resolve() / ("x" * (length - len(str(base.resolve()).encode()) - 1))
    if sys.platform == "win32":
        # Windows' stat gives a file symlink's own size, 0, and espeak-ng reads that many
        # bytes of phondata: a real copy, which fits MAX_PATH at the limit
        shutil.copytree(wheel_data_path(), folder)
    else:
        folder.mkdir()
        for entry in Path(wheel_data_path()).iterdir():
            (folder / entry.name).symlink_to(entry, target_is_directory=entry.is_dir())
    assert len(str(folder).encode()) == length
    return folder


def speak(data: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-I", "-c", SPEAK, str(data)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        check=False,
    )


def test_espeak_exits_on_a_data_path_past_its_buffer(tmp_path: Path) -> None:
    """Pins espeak-ng's own behaviour, which `ESPEAK_PATH_LIMIT` mirrors.

    One byte past the limit, POSIX espeak-ng falls back to the wheel's build-time folder
    and exits. On Windows a copy that does not fit loses its terminating zero byte (MSVC's
    `_snprintf`), so past the limit espeak-ng reads past its buffer: undefined, nothing to
    pin.
    """
    (tmp_path / "at").mkdir()
    (tmp_path / "over").mkdir()
    at = linked_data(tmp_path / "at", ESPEAK_PATH_LIMIT)
    at_limit = speak(at)
    assert at_limit.returncode == 0, at_limit.stderr
    sounds, used = at_limit.stdout.splitlines()
    assert sounds == "bɾˈʏkə"  # noqa: RUF001 - IPA for "Brücke"
    assert Path(used) == at
    if sys.platform != "win32":
        past = speak(linked_data(tmp_path / "over", ESPEAK_PATH_LIMIT + 1))
        assert past.returncode == 1
        assert "phontab" in past.stderr
        assert past.stdout == ""  # the process ended before it could speak


def test_a_data_path_past_the_limit_is_refused_before_espeak_loads(tmp_path: Path) -> None:
    (tmp_path / "at").mkdir()
    (tmp_path / "over").mkdir()
    check_espeak_data(linked_data(tmp_path / "at", ESPEAK_PATH_LIMIT))
    over = linked_data(tmp_path / "over", ESPEAK_PATH_LIMIT + 1)
    with pytest.raises(ModelLoadError, match=rf"{ESPEAK_PATH_LIMIT + 1} bytes.*#663") as error:
        check_espeak_data(over)
    assert str(over) in str(error.value)


def test_a_non_ascii_path_is_measured_in_bytes(tmp_path: Path) -> None:
    base = tmp_path.resolve()
    # each "ü" is one character but two bytes: one more than half the room left goes past
    # the limit in bytes, whatever the parity of the base path's length
    folder = base / ("ü" * ((ESPEAK_PATH_LIMIT - len(str(base).encode())) // 2 + 1))
    folder.mkdir()
    (folder / "phontab").write_bytes(b"")
    assert len(str(folder)) <= ESPEAK_PATH_LIMIT < len(str(folder).encode())
    with pytest.raises(ModelLoadError, match="#663"):
        check_espeak_data(folder)


def test_a_data_folder_without_phontab_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ModelLoadError, match=r"phontab.*#663"):
        check_espeak_data(tmp_path)


def test_the_wheels_data_folder_passes_the_check() -> None:
    assert (Path(wheel_data_path()) / "phontab").is_file()
    check_espeak_data()


def non_ascii_data(base: Path) -> Path:
    """The wheel's espeak-ng data in a folder below one named with a non-ASCII character."""
    folder = base.resolve() / "Jürgen" / "data"
    if sys.platform == "win32":
        shutil.copytree(wheel_data_path(), folder)  # file symlinks read as empty there
    else:
        folder.mkdir(parents=True)
        for entry in Path(wheel_data_path()).iterdir():
            (folder / entry.name).symlink_to(entry, target_is_directory=entry.is_dir())
    return folder


def test_espeak_on_a_non_ascii_data_folder(tmp_path: Path) -> None:
    """Pins espeak-ng's own behaviour, which the code page check mirrors (#744).

    phonemizer hands espeak-ng the folder as UTF-8 bytes. POSIX opens them as they are;
    Windows reads them in the ANSI code page, where they name another folder unless that
    code page is UTF-8: espeak-ng falls back to its build-time folder and exits.
    """
    folder = non_ascii_data(tmp_path)
    result = speak(folder)
    encoding = windows_ansi_encoding()
    if encoding is None or codecs.lookup(encoding).name == "utf-8":
        assert result.returncode == 0, result.stderr
        sounds, used = result.stdout.splitlines()
        assert sounds == "bɾˈʏkə"  # noqa: RUF001 - IPA for "Brücke"
        assert Path(used) == folder
    else:
        assert result.returncode == 1, (encoding, result.stdout, result.stderr)
        assert "phontab" in result.stderr
        assert result.stdout == ""  # the process ended before it could speak


def test_a_non_ascii_data_folder_is_refused_under_an_ansi_code_page(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder = tmp_path.resolve() / "Jürgen"
    folder.mkdir()
    (folder / "phontab").write_bytes(b"")
    monkeypatch.setattr(espeak, "windows_ansi_encoding", lambda: "cp1252")
    with pytest.raises(ModelLoadError, match=r"cp1252.*#744") as error:
        check_espeak_data(folder)
    assert str(folder) in str(error.value)


def test_a_non_ascii_data_folder_passes_where_espeak_reads_utf8(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder = tmp_path.resolve() / "Jürgen"
    folder.mkdir()
    (folder / "phontab").write_bytes(b"")
    for encoding in (None, "utf-8", "cp65001"):
        monkeypatch.setattr(espeak, "windows_ansi_encoding", lambda e=encoding: e)
        check_espeak_data(folder)
    ascii_folder = tmp_path.resolve() / "Juergen"
    ascii_folder.mkdir()
    (ascii_folder / "phontab").write_bytes(b"")
    monkeypatch.setattr(espeak, "windows_ansi_encoding", lambda: "cp1252")
    check_espeak_data(ascii_folder)


def test_windows_ansi_encoding_is_set_on_windows_only() -> None:
    encoding = windows_ansi_encoding()
    if sys.platform == "win32":
        assert encoding is not None
        codecs.lookup(encoding)
    else:
        assert encoding is None
