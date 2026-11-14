"""The user-started voice download: what it fetches, and fault injection (D-47, VA-03).

No test touches the network: `fetch` is replaced by a fake that serves bytes from memory,
and the real requests-based fetch is tested against a fake `requests.get`.
"""

from __future__ import annotations

import errno
import hashlib
import io
import re
import shutil
import zipfile
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path, PurePosixPath
from typing import BinaryIO

import pytest
import requests

from sci2audio.testing import no_network
from sci2audio.voices import (
    DownloadError,
    DownloadPlan,
    NetworkError,
    RemoteFile,
    download_plan,
    download_voice_files,
    installed_languages,
    missing_files,
)
from sci2audio.voices import download as download_module

REVISION = "f3ff3571791e39611d31c381e3a41a3af07b4987"
GERMAN_REVISION = "734e593d320a3d876bede7020f773dfd481a0cc7"


def test_plan_names_every_file_with_size_checksum_and_licence() -> None:
    plan = download_plan(["en"])
    assert {f.pack for f in plan.files} == {"en"}
    hf = f"https://huggingface.co/hexgrad/Kokoro-82M/resolve/{REVISION}/"
    spacy = "https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/"
    assert all(f.url.startswith((hf, spacy)) for f in plan.files)
    assert all(re.fullmatch(r"[0-9a-f]{64}", f.sha256) for f in plan.files)
    assert all(f.size > 0 and f.licence for f in plan.files)
    targets = [f.target for f in plan.files]
    assert len(set(targets)) == len(targets)
    assert all(not PurePosixPath(t).is_absolute() and ".." not in t for t in targets)
    assert len(plan.files) == 2 + 28 + 1
    assert [f.unpack for f in plan.files].count(True) == 1
    assert plan.total_bytes == sum(f.size for f in plan.files)
    assert 350_000_000 < plan.total_bytes < 360_000_000
    assert any("Apache" in text for text in plan.licences)
    assert any("MIT" in text for text in plan.licences)


def test_the_german_pack_is_the_pinned_thorsten_model_with_its_licence() -> None:
    plan = download_plan(["de"])
    base = f"https://huggingface.co/Thorsten-Voice/Kokoro/resolve/{GERMAN_REVISION}/"
    folder = f"kokoro-82m-de-thorsten/{GERMAN_REVISION}/"
    assert [(f.url, f.target, f.size, f.sha256[:12]) for f in plan.files] == [
        (base + "config.json", folder + "config.json", 2_351, "5abb01e2403b"),
        (base + "model.pth", folder + "model.pth", 327_231_582, "36dde15c4a80"),
        (base + "voices/thorsten.pt", folder + "voices/thorsten.pt", 523_450, "9d98b775ebce"),
    ]
    assert all(f.pack == "de" and not f.unpack for f in plan.files)
    assert len(plan.licences) == 1
    assert "Apache License 2.0" in plan.licences[0]
    assert "Thorsten-Voice dataset (CC0)" in plan.licences[0]
    # the German config is the English one, byte for byte (Kokoro-82M's architecture)
    english_config = next(f for f in download_plan(["en"]).files if f.target.endswith(".json"))
    assert plan.files[0].sha256 == english_config.sha256


def test_the_whole_plan_is_every_pack_in_order() -> None:
    plan = download_plan()
    assert plan == download_plan(["en", "de"])
    assert [f.pack for f in plan.files] == ["en"] * 31 + ["de"] * 3
    assert plan.total_bytes == download_plan(["en"]).total_bytes + download_plan(["de"]).total_bytes
    assert len(plan.licences) == 3
    targets = [f.target for f in plan.files]
    assert len(set(targets)) == len(targets)


def test_an_unknown_language_has_no_pack(tmp_path: Path) -> None:
    for call in (
        lambda: download_plan(["fr"]),
        lambda: missing_files(tmp_path, ["fr"]),
        lambda: download_voice_files(tmp_path, languages=["fr"], fetch=FakeServer()),
    ):
        with pytest.raises(ValueError, match="no voice pack for fr"):
            call()


def test_missing_files_and_installed_languages_by_pack(tmp_path: Path) -> None:
    assert installed_languages(tmp_path) == ()
    assert missing_files(tmp_path, ["de"]) == list(download_plan(["de"]).files)
    for file in download_plan(["de"]).files:  # right sizes count as in place
        path = tmp_path / file.target
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as out:
            out.truncate(file.size)
    assert missing_files(tmp_path, ["de"]) == []
    assert installed_languages(tmp_path) == ("de",)
    assert missing_files(tmp_path) == missing_files(tmp_path, ["en"])
    assert len(missing_files(tmp_path)) == 31


# --- a small fake plan: two files and a wheel -------------------------------------------


def wheel_bytes(members: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, data in members.items():
            archive.writestr(name, data)
    return buffer.getvalue()


WHEEL = wheel_bytes(
    {
        "en_core_web_sm/__init__.py": b"",
        "en_core_web_sm-3.8.0.dist-info/METADATA": b"Name: en_core_web_sm\n",
        "en_core_web_sm-3.8.0.dist-info/RECORD": b"",
    }
)
SERVED = {
    "https://example.test/config.json": b'{"vocab": {}}',
    "https://example.test/weights.pth": b"w" * 5000,
    "https://example.test/model.whl": WHEEL,
}


def remote(url: str, target: str, unpack: bool = False) -> RemoteFile:
    data = SERVED[url]
    return RemoteFile(url, target, len(data), hashlib.sha256(data).hexdigest(), "MIT", unpack)


FILES = (
    remote("https://example.test/config.json", "kokoro/config.json"),
    remote("https://example.test/weights.pth", "kokoro/weights.pth"),
    remote("https://example.test/model.whl", "spacy/en_core_web_sm-3.8.0", unpack=True),
)


class FakeServer:
    """Serves SERVED in blocks of 1000 bytes; hooks can break things mid-stream."""

    def __init__(self, served: dict[str, bytes] | None = None) -> None:
        self.served = served or SERVED
        self.fetched: list[str] = []
        self.on_block: Callable[[str, int], None] | None = None

    def __call__(self, url: str, out: BinaryIO, on_bytes: Callable[[int], None]) -> None:
        self.fetched.append(url)
        data = self.served[url]
        for start in range(0, len(data), 1000):
            if self.on_block:
                self.on_block(url, start)
            block = data[start : start + 1000]
            out.write(block)
            on_bytes(len(block))


@pytest.fixture
def small_plan(monkeypatch: pytest.MonkeyPatch) -> None:
    plan = DownloadPlan(FILES, sum(f.size for f in FILES), ("MIT",))
    monkeypatch.setattr(download_module, "download_plan", lambda: plan)


def leftovers(folder: Path) -> list[Path]:
    return [p for p in folder.rglob("*") if p.name.endswith(".part") or p.name.startswith(".")]


@pytest.mark.usefixtures("small_plan")
def test_download_puts_every_file_in_place(tmp_path: Path) -> None:
    server = FakeServer()
    seen: list[tuple[int, int, str]] = []
    with no_network():
        download_voice_files(tmp_path, fetch=server, progress=lambda *a: seen.append(a))
    assert (tmp_path / "kokoro/weights.pth").read_bytes() == SERVED[FILES[1].url]
    assert (tmp_path / "spacy/en_core_web_sm-3.8.0/en_core_web_sm/__init__.py").is_file()
    assert not (tmp_path / "spacy" / "en_core_web_sm-3.8.0-py3-none-any.whl").exists()
    assert missing_files(tmp_path) == []
    assert leftovers(tmp_path) == []
    done = [d for d, _, _ in seen]
    assert done == sorted(done)
    assert done[-1] == seen[-1][1] == sum(len(d) for d in SERVED.values())


@pytest.fixture
def two_packs(monkeypatch: pytest.MonkeyPatch) -> tuple[RemoteFile, ...]:
    """The small plan with its weights file in the German pack."""
    files = (FILES[0], replace(FILES[1], pack="de"), FILES[2])
    plan = DownloadPlan(files, sum(f.size for f in files), ("MIT",))
    monkeypatch.setattr(download_module, "download_plan", lambda languages=None: plan)
    return files


def test_one_language_downloads_only_its_pack(
    tmp_path: Path, two_packs: tuple[RemoteFile, ...]
) -> None:
    server = FakeServer()
    seen: list[tuple[int, int, str]] = []
    with no_network():
        download_voice_files(
            tmp_path, fetch=server, languages=["de"], progress=lambda *a: seen.append(a)
        )
    assert server.fetched == [two_packs[1].url]
    assert seen[-1][:2] == (two_packs[1].size, two_packs[1].size)
    assert missing_files(tmp_path, ["de"]) == []
    assert [f.target for f in missing_files(tmp_path, ["en"])] == [
        two_packs[0].target,
        two_packs[2].target,
    ]
    assert installed_languages(tmp_path) == ("de",)
    download_voice_files(tmp_path, fetch=server)  # the rest, English
    assert server.fetched == [two_packs[1].url, two_packs[0].url, two_packs[2].url]
    assert installed_languages(tmp_path) == ("en", "de")


def test_an_interrupted_pack_download_resumes(
    tmp_path: Path, two_packs: tuple[RemoteFile, ...]
) -> None:
    server = FakeServer()

    def cut(url: str, start: int) -> None:
        if start == 3000:
            raise NetworkError("connection reset")

    server.on_block = cut
    with pytest.raises(NetworkError):
        download_voice_files(tmp_path, fetch=server, languages=["de"])
    assert leftovers(tmp_path) == []
    assert missing_files(tmp_path, ["de"]) == [two_packs[1]]
    download_voice_files(tmp_path, fetch=FakeServer(), languages=["de"])
    assert missing_files(tmp_path, ["de"]) == []


@pytest.mark.usefixtures("small_plan")
def test_second_run_fetches_nothing(tmp_path: Path) -> None:
    download_voice_files(tmp_path, fetch=FakeServer())
    again = FakeServer()
    download_voice_files(tmp_path, fetch=again)
    assert again.fetched == []


@pytest.mark.usefixtures("small_plan")
def test_network_failure_keeps_finished_files_and_resumes(tmp_path: Path) -> None:
    server = FakeServer()

    def drop(url: str, start: int) -> None:
        if url == FILES[1].url and start == 3000:
            raise NetworkError("connection reset")

    server.on_block = drop
    with pytest.raises(NetworkError):
        download_voice_files(tmp_path, fetch=server)
    assert (tmp_path / "kokoro/config.json").is_file()
    assert not (tmp_path / "kokoro/weights.pth").exists()
    assert leftovers(tmp_path) == []

    resumed = FakeServer()
    download_voice_files(tmp_path, fetch=resumed)
    assert resumed.fetched == [FILES[1].url, FILES[2].url]
    assert missing_files(tmp_path) == []


@pytest.mark.usefixtures("small_plan")
def test_damaged_file_of_the_right_size_is_fetched_again(tmp_path: Path) -> None:
    download_voice_files(tmp_path, fetch=FakeServer())
    (tmp_path / "kokoro/weights.pth").write_bytes(b"x" * 5000)
    again = FakeServer()
    download_voice_files(tmp_path, fetch=again)
    assert again.fetched == [FILES[1].url]
    assert (tmp_path / "kokoro/weights.pth").read_bytes() == SERVED[FILES[1].url]


@pytest.mark.usefixtures("small_plan")
def test_a_file_of_the_wrong_size_counts_as_missing(tmp_path: Path) -> None:
    download_voice_files(tmp_path, fetch=FakeServer())
    weights = tmp_path / "kokoro/weights.pth"
    weights.write_bytes(weights.read_bytes()[:-1])  # truncated by one byte
    assert missing_files(tmp_path) == [FILES[1]]
    weights.write_bytes(weights.read_bytes() + b"xx")  # one byte too long
    assert missing_files(tmp_path) == [FILES[1]]


@pytest.mark.usefixtures("small_plan")
def test_damaged_spacy_folder_is_replaced(tmp_path: Path) -> None:
    download_voice_files(tmp_path, fetch=FakeServer())
    folder = tmp_path / "spacy/en_core_web_sm-3.8.0"
    (folder / "en_core_web_sm-3.8.0.dist-info" / "RECORD").unlink()
    (folder / "stale.txt").write_text("left from a broken run")
    assert missing_files(tmp_path) == [FILES[2]]

    again = FakeServer()
    download_voice_files(tmp_path, fetch=again)
    assert again.fetched == [FILES[2].url]
    assert (folder / "en_core_web_sm-3.8.0.dist-info" / "RECORD").is_file()
    assert not (folder / "stale.txt").exists()
    assert missing_files(tmp_path) == []
    assert leftovers(tmp_path) == []


@pytest.mark.usefixtures("small_plan")
def test_a_server_sending_too_much_is_cut_off(tmp_path: Path) -> None:
    endless = dict(SERVED, **{FILES[1].url: b"w" * 9000})  # listed size is 5000
    server = FakeServer(endless)
    with pytest.raises(DownloadError, match="more than its expected 5000 bytes"):
        download_voice_files(tmp_path, fetch=server)
    assert not (tmp_path / "kokoro/weights.pth").exists()
    assert leftovers(tmp_path) == []


@pytest.mark.usefixtures("small_plan")
def test_wrong_checksum_keeps_nothing(tmp_path: Path) -> None:
    tampered = dict(SERVED, **{FILES[1].url: b"evil" * 1250})
    with pytest.raises(DownloadError, match="checksum"):
        download_voice_files(tmp_path, fetch=FakeServer(tampered))
    assert not (tmp_path / "kokoro/weights.pth").exists()
    assert leftovers(tmp_path) == []


@pytest.mark.usefixtures("small_plan")
def test_disk_full_gives_a_clear_message_and_no_half_file(tmp_path: Path) -> None:
    server = FakeServer()

    def full(url: str, start: int) -> None:
        if url == FILES[1].url and start == 2000:
            raise OSError(errno.ENOSPC, "No space left on device")

    server.on_block = full
    with pytest.raises(DownloadError, match="not enough disk space"):
        download_voice_files(tmp_path, fetch=server)
    assert not (tmp_path / "kokoro/weights.pth").exists()
    assert leftovers(tmp_path) == []


@pytest.mark.usefixtures("small_plan")
def test_folder_removed_during_the_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    models = tmp_path / "models"
    real_replace = download_module.os.replace

    def remove_then_replace(source: Path, target: Path) -> None:
        shutil.rmtree(models)
        real_replace(source, target)

    monkeypatch.setattr(download_module.os, "replace", remove_then_replace)
    with pytest.raises(DownloadError, match="disappeared"):
        download_voice_files(models, fetch=FakeServer())


@pytest.mark.usefixtures("small_plan")
def test_damaged_wheel_leaves_no_half_unpacked_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken_extract(self: zipfile.ZipFile, path: str) -> None:
        (Path(path) / "en_core_web_sm").mkdir()
        raise OSError(errno.EIO, "read error")

    monkeypatch.setattr(zipfile.ZipFile, "extractall", broken_extract)
    with pytest.raises(DownloadError):
        download_voice_files(tmp_path, fetch=FakeServer())
    assert not (tmp_path / "spacy/en_core_web_sm-3.8.0").exists()
    assert leftovers(tmp_path) == []


@pytest.mark.parametrize("member", ["../escaped.py", "/abs.py", "en_core_web_sm\\..\\x.py"])
def test_wheel_with_unsafe_paths_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, member: str
) -> None:
    evil = wheel_bytes({member: b"print('hi')"})
    served = dict(SERVED, **{"https://example.test/evil.whl": evil})
    files = (
        RemoteFile(
            "https://example.test/evil.whl",
            "spacy/en_core_web_sm-3.8.0",
            len(evil),
            hashlib.sha256(evil).hexdigest(),
            "MIT",
            unpack=True,
        ),
    )
    monkeypatch.setattr(download_module, "download_plan", lambda: DownloadPlan(files, 1, ()))
    models = tmp_path / "models"
    with pytest.raises(DownloadError, match="unsafe path"):
        download_voice_files(models, fetch=FakeServer(served))
    assert not (tmp_path / "escaped.py").exists()
    assert not (models / "spacy/en_core_web_sm-3.8.0").exists()


# --- the real fetch, against a fake requests.get -----------------------------------------


class FakeResponse:
    def __init__(self, blocks: list[bytes], status: int = 200) -> None:
        self.blocks, self.status = blocks, status

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def raise_for_status(self) -> None:
        if self.status >= 400:
            raise requests.HTTPError(f"{self.status} error")

    def iter_content(self, chunk_size: int) -> list[bytes]:
        return self.blocks


def test_requests_fetch_streams_with_a_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, object]] = []

    def get(url: str, **kwargs: object) -> FakeResponse:
        calls.append({"url": url, **kwargs})
        return FakeResponse([b"ab", b"cd"])

    monkeypatch.setattr(download_module.requests, "get", get)
    out, counted = io.BytesIO(), []
    download_module._fetch_with_requests("https://example.test/f", out, counted.append)
    assert out.getvalue() == b"abcd"
    assert counted == [2, 2]
    assert calls[0]["stream"] is True
    assert calls[0]["timeout"]


@pytest.mark.parametrize(
    "failure",
    [requests.ConnectionError("offline"), requests.Timeout("slow"), None],
)
def test_requests_fetch_turns_failures_into_network_errors(
    monkeypatch: pytest.MonkeyPatch, failure: Exception | None
) -> None:
    def get(url: str, **kwargs: object) -> FakeResponse:
        if failure:
            raise failure
        return FakeResponse([], status=404)

    monkeypatch.setattr(download_module.requests, "get", get)
    with pytest.raises(NetworkError, match="could not download"):
        download_module._fetch_with_requests("https://example.test/f", io.BytesIO(), print)
