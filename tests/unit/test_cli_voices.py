"""`sci2audio voices` and `voices download` (#72, VA-03): the list without network, the
download shown in full before consent, and nothing fetched without it (D-221, D-222).
No test touches the network: the download's `fetch` is a fake that serves bytes."""

from __future__ import annotations

from pathlib import Path

import pytest
from cli_helpers import Cli
from syrupy.assertion import SnapshotAssertion
from test_voices_download import FILES, SERVED, FakeServer, leftovers

from sci2audio.cli import describe_download
from sci2audio.testing import no_network
from sci2audio.voices import (
    DEFAULT_VOICE,
    ENGLISH_VOICES,
    DownloadPlan,
    NetworkError,
    download_plan,
    missing_files,
)
from sci2audio.voices import download as download_module

PLAN = DownloadPlan(FILES, sum(f.size for f in FILES), ("MIT",))


@pytest.fixture
def small_plan(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(download_module, "download_plan", lambda: PLAN)
    monkeypatch.setattr("sci2audio.cli.download_plan", lambda: PLAN)


def downloading(tmp_path: Path, server: FakeServer, **kwargs: object) -> Cli:
    """A cli whose download runs against the fake server and the real missing-file check."""
    return Cli(tmp_path, fetch=server, missing=missing_files, **kwargs)  # type: ignore[arg-type]


def test_lists_every_voice_without_network(tmp_path: Path) -> None:
    cli = Cli(tmp_path, voice_installed=False)
    with no_network() as attempts:
        result = cli("voices")
    assert attempts == []
    assert result.code == 0
    for voice in ENGLISH_VOICES:
        assert voice.id in result.out
        assert voice.name in result.out
    assert f"{DEFAULT_VOICE}  " in result.out
    assert [line for line in result.out.splitlines() if "(default)" in line] == [
        line for line in result.out.splitlines() if line.lstrip().startswith(DEFAULT_VOICE)
    ]
    assert f"The voice files are not installed in {cli.models}" in result.out
    assert "sci2audio voices download" in result.out


def test_says_when_the_voice_files_are_installed(tmp_path: Path) -> None:
    cli = Cli(tmp_path)
    result = cli("voices")
    assert result.out.endswith(f"The voice files are installed in {cli.models}.\n")


def test_the_real_download_is_described_in_full(snapshot: SnapshotAssertion) -> None:
    plan = download_plan()
    text = describe_download(plan, plan.files, Path("models"))
    assert text == snapshot
    assert "355 MB" in text


@pytest.mark.usefixtures("small_plan")
def test_yes_on_the_terminal_downloads(tmp_path: Path) -> None:
    server = FakeServer()
    cli = downloading(tmp_path, server, interactive=True, answers=["y"])
    with no_network():
        result = cli("voices", "download")
    assert result.code == 0, result.err
    assert cli.asked == ["Download about 0.0 MB now? [y/N] "]
    assert server.fetched == [f.url for f in FILES]
    assert missing_files(cli.models) == []
    assert leftovers(cli.models) == []
    assert result.out.startswith(f"The voice download puts these files into {cli.models}:\n")
    assert result.out.endswith(f"The voice files are installed in {cli.models}.\n")
    assert "Downloading: " in result.err


@pytest.mark.parametrize("answer", ["n", "", "no", "maybe"])
@pytest.mark.usefixtures("small_plan")
def test_anything_but_yes_downloads_nothing(tmp_path: Path, answer: str) -> None:
    server = FakeServer()
    cli = downloading(tmp_path, server, interactive=True, answers=[answer])
    result = cli("voices", "download")
    assert result.code == 1
    assert result.out.endswith("Nothing was downloaded.\n")
    assert server.fetched == []
    assert not cli.models.exists()


@pytest.mark.usefixtures("small_plan")
def test_end_of_input_downloads_nothing(tmp_path: Path) -> None:
    server = FakeServer()
    cli = downloading(tmp_path, server, interactive=True, answers=[])
    assert cli("voices", "download").code == 1
    assert server.fetched == []


@pytest.mark.usefixtures("small_plan")
def test_without_a_terminal_it_needs_yes(tmp_path: Path) -> None:
    server = FakeServer()
    cli = downloading(tmp_path, server, interactive=False)
    result = cli("voices", "download")
    assert result.code == 2
    assert "add --yes to agree on the command line" in result.err
    assert cli.asked == []
    assert server.fetched == []


@pytest.mark.usefixtures("small_plan")
def test_yes_on_the_command_line_is_consent(tmp_path: Path) -> None:
    server = FakeServer()
    cli = downloading(tmp_path, server, interactive=False)
    result = cli("voices", "download", "--yes")
    assert result.code == 0, result.err
    assert cli.asked == []
    assert missing_files(cli.models) == []
    assert result.err.splitlines()[-1].startswith("Downloading: ")  # one line per step


@pytest.mark.usefixtures("small_plan")
def test_nothing_to_download_when_installed(tmp_path: Path) -> None:
    cli = downloading(tmp_path, FakeServer(), interactive=False)
    assert cli("voices", "download", "--yes").code == 0
    again = FakeServer()
    cli = downloading(tmp_path, again, interactive=False)
    result = cli("voices", "download")  # no --yes needed: nothing is fetched
    assert result.code == 0
    assert result.out == f"The voice files are installed in {cli.models}; nothing to download.\n"
    assert again.fetched == []


@pytest.mark.usefixtures("small_plan")
def test_a_network_failure_keeps_what_finished(tmp_path: Path) -> None:
    server = FakeServer()

    def drop(url: str, start: int) -> None:
        if url == FILES[1].url and start == 2000:
            raise NetworkError("the connection was reset")

    server.on_block = drop
    cli = downloading(tmp_path, server)
    result = cli("voices", "download", "--yes")
    assert result.code == 1
    assert "the connection was reset" in result.err
    assert "running the download again continues" in result.err
    assert (cli.models / FILES[0].target).read_bytes() == SERVED[FILES[0].url]
    assert leftovers(cli.models) == []


@pytest.mark.usefixtures("small_plan")
def test_ctrl_c_during_the_download_leaves_no_part_file(tmp_path: Path) -> None:
    server = FakeServer()

    def interrupt(url: str, start: int) -> None:
        if url == FILES[1].url and start == 2000:
            raise KeyboardInterrupt

    server.on_block = interrupt
    cli = downloading(tmp_path, server)
    result = cli("voices", "download", "--yes")
    assert result.code == 130
    assert result.err.endswith("sci2audio: stopped; run the same command again to continue\n")
    assert leftovers(cli.models) == []


def test_the_models_folder_option(tmp_path: Path) -> None:
    seen: list[Path] = []
    cli = Cli(tmp_path, missing=lambda models: seen.append(models) or [])
    assert cli("voices", "--models-folder", tmp_path / "m").code == 0
    assert cli("voices", "download", "--models-folder", tmp_path / "n").code == 0
    assert cli("voices", "--models-folder", tmp_path / "o", "download").code == 0
    assert seen == [tmp_path / "m", tmp_path / "n", tmp_path / "o"]
