"""The listening position, kept across server runs (#153).

Part one checks the record on hand-made read-along data: what is written, and every reason
a record is ignored. Part two runs a real audio job with the fake voice and real ffmpeg (a
few seconds, allowed in the fast tier) and checks the route that saves the position, the
page's offer, the request checks (D-194) and the faults: disk full, the working folder
removed, a link or a folder where the record goes, a new audiobook.
"""

from __future__ import annotations

import errno
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

import pytest
from test_web_player import make, readalong, server, work_of
from web_helpers import ORIGIN, browser, make_config, program
from web_helpers import offline as offline

from sci2audio.app import files
from sci2audio.web import create_app, player
from sci2audio.web.player import Position, read_position, write_position

STAMP = "0123456789abcdef"
DOC = "fedcba9876543210"


def two_chapters() -> Any:
    # chunks one second apart: chapter 0 holds chunks 0-4 (0 s to 5 s), chapter 1 5-9
    data = readalong([(0, 0, 1)] * 10, (("One", 0), ("Two", 5)), [0] * 5 + [1] * 5)
    return data


# ---- the record, on hand-made data ---------------------------------------------------------


def test_a_position_is_written_and_read_back(tmp_path: Path) -> None:
    data = two_chapters()
    write_position(tmp_path, DOC, STAMP, Position(1, 7.25))
    stored = json.loads((tmp_path / player.POSITION).read_text(encoding="utf-8"))
    assert stored == {
        "format": "sci2audio-web-position",
        "version": 1,
        "document": DOC,
        "audiobook": STAMP,
        "chapter": 1,
        "time": 7.25,
    }
    assert read_position(tmp_path, DOC, STAMP, data) == Position(1, 7.25)
    assert [p.name for p in tmp_path.iterdir()] == [player.POSITION]  # no partial file left


@pytest.mark.parametrize(
    "change",
    [
        {"format": "something-else"},
        {"version": 2},
        {"document": "0000000000000000"},
        {"audiobook": "ffffffffffffffff"},  # another audiobook: a rerun made a new one
        {"chapter": 2},  # no such chapter
        {"chapter": -1},
        {"chapter": "1"},
        {"chapter": True},
        {"time": 3.0},  # in chapter 0, not in chapter 1
        {"time": 10.0},  # the end of the book
        {"time": -1.0},
        {"time": "7"},
        {"time": None},
    ],
)
def test_a_record_that_does_not_fit_is_ignored(tmp_path: Path, change: dict[str, Any]) -> None:
    data = two_chapters()
    write_position(tmp_path, DOC, STAMP, Position(1, 7.25))
    path = tmp_path / player.POSITION
    stored = json.loads(path.read_text(encoding="utf-8"))
    stored.update(change)
    path.write_text(json.dumps(stored), encoding="utf-8")
    assert read_position(tmp_path, DOC, STAMP, data) is None


@pytest.mark.parametrize(
    "text", ["", "{", "[]", "null", '"text"', '{"time": NaN}', "x" * 5000, "\udcff"]
)
def test_a_broken_record_is_ignored(tmp_path: Path, text: str) -> None:
    (tmp_path / player.POSITION).write_text(text, encoding="utf-8", errors="surrogateescape")
    assert read_position(tmp_path, DOC, STAMP, two_chapters()) is None


def test_no_record_and_a_folder_in_its_place_are_ignored(tmp_path: Path) -> None:
    assert read_position(tmp_path, DOC, STAMP, two_chapters()) is None
    (tmp_path / player.POSITION).mkdir()
    assert read_position(tmp_path, DOC, STAMP, two_chapters()) is None
    with pytest.raises(OSError, match=r"directory|denied"):  # Windows: "Access is denied"
        write_position(tmp_path, DOC, STAMP, Position(0, 1.0))


def test_nothing_is_offered_before_the_first_sentence_ends_or_after_the_last(
    tmp_path: Path,
) -> None:
    data = two_chapters()  # 10 s long; chunk n from n s to n + 0.5 s
    for chapter, time in ((0, 0.0), (0, 0.25), (1, 9.5), (1, 10.0)):
        write_position(tmp_path, DOC, STAMP, Position(chapter, time))
        assert read_position(tmp_path, DOC, STAMP, data) is None, time
    for chapter, time in ((0, 0.5), (0, 1.5), (1, 5.0), (1, 9.25)):
        write_position(tmp_path, DOC, STAMP, Position(chapter, time))
        assert read_position(tmp_path, DOC, STAMP, data) == Position(chapter, time), time


def test_a_position_must_lie_in_the_book() -> None:
    data = two_chapters()
    assert player.fits(data, Position(0, 0.0))
    assert player.fits(data, Position(1, 10.0))  # the end is saved when the book ends
    assert not player.fits(data, Position(1, 10.5))
    assert not player.fits(data, Position(0, 5.5))
    assert not player.fits(data, Position(2, 6.0))
    assert not player.fits(data, Position(0, float("nan")))
    assert not player.fits(data, Position(0, float("inf")))


def test_disk_full_leaves_the_old_record(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    write_position(tmp_path, DOC, STAMP, Position(1, 7.0))
    before = (tmp_path / player.POSITION).read_bytes()

    def full(path: Path, content: str | bytes) -> None:
        path.write_bytes(b"{")  # a part of it reached the disk
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(files, "_write_partial", full)
    with pytest.raises(OSError, match="No space left"):
        write_position(tmp_path, DOC, STAMP, Position(1, 8.0))
    assert (tmp_path / player.POSITION).read_bytes() == before
    assert [p.name for p in tmp_path.iterdir()] == [player.POSITION]


@pytest.mark.skipif(sys.platform == "win32", reason="symbolic links need rights on Windows")
def test_a_link_in_the_records_place_is_replaced_not_followed(tmp_path: Path) -> None:
    target = tmp_path / "elsewhere.txt"
    target.write_text("keep me", encoding="utf-8")
    work = tmp_path / "work"
    work.mkdir()
    os.symlink(target, work / player.POSITION)
    assert read_position(work, DOC, STAMP, two_chapters()) is None  # never read through it
    write_position(work, DOC, STAMP, Position(0, 2.0))
    assert target.read_text(encoding="utf-8") == "keep me"
    assert not (work / player.POSITION).is_symlink()


def test_the_stamp_is_the_read_along_files_hash(tmp_path: Path) -> None:
    path = tmp_path / "Book.readalong.json"
    path.write_bytes(b"one")
    first = player.audiobook_stamp(path)
    assert len(first) == 16
    assert set(first) <= set("0123456789abcdef")
    # a new audiobook replaces the file whole, as `write_texts` does; on Windows both
    # writes can get the same time and size, so the file's new identity must count
    stat = path.stat()
    new = tmp_path / "new.json"
    new.write_bytes(b"two")
    os.utime(new, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    os.replace(new, path)
    assert path.stat().st_mtime_ns == stat.st_mtime_ns
    assert player.audiobook_stamp(path) != first


# ---- the route and the page, after a real audio job ---------------------------------------

pytestmark = pytest.mark.usefixtures("offline")


def stamp_of(client: Any, doc: str) -> str:
    """The stamp the listen page was drawn with: the player sends it with each save."""
    from test_web_player import player_data

    return str(player_data(client.get(f"/documents/{doc}/listen").text)["audiobook"])


def chapters_of(page: str) -> list[dict[str, Any]]:
    from test_web_player import player_data

    return list(player_data(page)["chapters"])


def test_the_position_is_saved_and_offered_on_the_next_run(tmp_path: Path) -> None:
    client, config = server(tmp_path)
    made = make(client)
    doc = made["doc"]["id"]
    page = client.get(f"/documents/{doc}/listen").text
    assert 'id="resume"' not in page  # nothing saved yet
    second = chapters_of(page)[1]
    at = second["start"] + 1.0
    stamp = stamp_of(client, doc)
    body = {"chapter": 1, "time": at, "audiobook": stamp}
    answer = client.post(f"/api/v1/documents/{doc}/position", json=body)
    assert answer.status_code == 204, answer.text
    # a new server run (a new token and a new app), with the same working folder; the
    # browser test runs it on another port
    again = make_config(tmp_path)
    assert again.token != config.token
    page = program(create_app(again), again).get(f"/documents/{doc}/listen").text
    assert 'id="resume"' in page
    assert "You stopped in chapter 2 at" in page
    assert '<span lang="en">Methods</span>' in page
    assert f'data-time="{at}"' in page
    assert 'data-chapter="1"' in page
    assert "autoplay" not in page


def test_a_position_the_audiobook_does_not_have_is_refused(tmp_path: Path) -> None:
    client, _config = server(tmp_path)
    doc = make(client)["doc"]["id"]
    url = f"/api/v1/documents/{doc}/position"
    stamp = stamp_of(client, doc)
    for body in (
        {"chapter": 5, "time": 1.0},
        {"chapter": 0, "time": 1e6},
        {"chapter": 0, "time": -1},
        {"chapter": 0},
        {"chapter": "x", "time": 1},
        {"chapter": 0, "time": 1, "extra": 1},
        {"chapter": 0, "time": 1, "audiobook": "not-a-stamp"},
    ):
        assert client.post(url, json={"audiobook": stamp, **body}).status_code == 422, body
    assert client.post(url, json={"chapter": 0, "time": 1}).status_code == 422  # no stamp
    assert not (work_of(_config, doc) / player.POSITION).exists()


def test_no_position_without_a_document_or_an_audiobook(tmp_path: Path) -> None:
    client, config = server(tmp_path)
    body = {"chapter": 0, "time": 1.0, "audiobook": "0123456789abcdef"}
    assert client.post("/api/v1/documents/0123456789abcdef/position", json=body).status_code == 404
    from web_helpers import paper_bytes, upload

    doc = upload(client, paper_bytes(), "paper.pdf")["id"]
    assert client.post(f"/api/v1/documents/{doc}/position", json=body).status_code == 404
    assert not (work_of(config, doc) / player.POSITION).exists()


def test_saving_keeps_the_request_checks(tmp_path: Path) -> None:
    _client, config = server(tmp_path)
    app = create_app(config)
    from fastapi.testclient import TestClient

    doc = make(_client)["doc"]["id"]
    url = f"/api/v1/documents/{doc}/position"
    body = {"chapter": 0, "time": 1.5, "audiobook": stamp_of(_client, doc)}
    cookie = browser(app, config)
    # the browser's cookie alone is not enough for a write: it needs the own Origin (D-194)
    assert cookie.post(url, json=body).status_code == 403
    assert cookie.post(url, json=body, headers={"origin": "http://evil.example"}).status_code == 403
    assert cookie.post(url, json=body, headers={"origin": ORIGIN}).status_code == 204
    assert TestClient(app, base_url=ORIGIN).post(url, json=body).status_code == 401  # no token
    foreign = cookie.post(url, json=body, headers={"origin": ORIGIN, "host": "evil.example"})
    assert foreign.status_code == 421


def test_disk_full_answers_503_and_keeps_the_old_position(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, config = server(tmp_path)
    doc = make(client)["doc"]["id"]
    url = f"/api/v1/documents/{doc}/position"
    stamp = stamp_of(client, doc)
    assert client.post(url, json={"chapter": 0, "time": 1.5, "audiobook": stamp}).status_code == 204
    record = work_of(config, doc) / player.POSITION
    before = record.read_bytes()

    def full(path: Path, content: str | bytes) -> None:
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(files, "_write_partial", full)
    answer = client.post(url, json={"chapter": 0, "time": 2.5, "audiobook": stamp})
    assert answer.status_code == 503
    assert answer.json()["error"] == "not-saved"
    assert record.read_bytes() == before


def test_a_removed_working_folder_is_not_made_again(tmp_path: Path) -> None:
    client, config = server(tmp_path)
    doc = make(client)["doc"]["id"]
    stamp = stamp_of(client, doc)
    shutil.rmtree(work_of(config, doc))
    body = {"chapter": 0, "time": 1.5, "audiobook": stamp}
    answer = client.post(f"/api/v1/documents/{doc}/position", json=body)
    assert answer.status_code == 404
    assert not work_of(config, doc).exists()


def test_a_new_audiobook_drops_the_saved_position(tmp_path: Path) -> None:
    client, config = server(tmp_path)
    made = make(client)
    doc = made["doc"]["id"]
    url = f"/api/v1/documents/{doc}/position"
    old = stamp_of(client, doc)
    assert client.post(url, json={"chapter": 0, "time": 1.5, "audiobook": old}).status_code == 204
    record = work_of(config, doc) / player.POSITION
    assert record.exists()
    # the audio job runs again, at another speed: its success removes the record
    body = {"kind": "audio", "document": doc, "overwrite": True, "settings": {"speed": 1.5}}
    job = client.post("/api/v1/jobs", json=body)
    assert job.status_code in (201, 202), job.text
    from web_helpers import events

    final = json.loads(events(client, job.json()["id"])[-1][1])
    assert final["state"] == "done", final
    assert not record.exists()
    assert 'id="resume"' not in client.get(f"/documents/{doc}/listen").text
    # a listen page drawn for the old audiobook, still open, saves on pause: refused,
    # so the new audiobook is not offered a place nobody heard in it (review S1)
    new = stamp_of(client, doc)
    assert new != old
    late = client.post(url, json={"chapter": 0, "time": 1.5, "audiobook": old})
    assert late.status_code == 409
    assert late.json()["error"] == "other-audiobook"
    assert not record.exists()
    assert client.post(url, json={"chapter": 0, "time": 1.5, "audiobook": new}).status_code == 204
    assert record.exists()


def test_a_record_of_another_audiobook_is_not_offered(tmp_path: Path) -> None:
    """The command line can remake the audiobook without the web knowing: the stamp no
    longer matches the read-along file found, so the position is dropped."""
    client, config = server(tmp_path)
    doc = make(client)["doc"]["id"]
    body = {"chapter": 0, "time": 1.5, "audiobook": stamp_of(client, doc)}
    assert client.post(f"/api/v1/documents/{doc}/position", json=body).status_code == 204
    record = work_of(config, doc) / player.POSITION
    stored = json.loads(record.read_text(encoding="utf-8"))
    stored["audiobook"] = "ffffffffffffffff"
    record.write_text(json.dumps(stored), encoding="utf-8")
    assert 'id="resume"' not in client.get(f"/documents/{doc}/listen").text
