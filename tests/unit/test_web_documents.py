"""Opening files and pasted text (D-198): stored in the document's own working folder,
named as opened, limited in size, safe against a full disk."""

from __future__ import annotations

import errno
import hashlib
import io
import os
import time
import unicodedata
from collections.abc import Iterator
from pathlib import Path, PurePath
from typing import Any

import pytest
from fastapi import FastAPI
from hypothesis import given
from hypothesis import strategies as st
from web_helpers import (
    app_and_config,
    offline,  # noqa: F401 - fixture
    pdf_bytes,
    program,
    upload,
)

from sci2audio.extraction import extract_pdf
from sci2audio.web import documents
from sci2audio.web.documents import DocumentStore, stored_name

pytestmark = pytest.mark.usefixtures("offline")


@pytest.fixture
def server(tmp_path: Path) -> tuple[FastAPI, Any]:
    return app_and_config(tmp_path)


def leftovers(root: Path) -> list[Path]:
    return [path for path in root.rglob("*.part")]


def test_an_opened_file_is_kept_in_its_working_folder(server: tuple[FastAPI, Any]) -> None:
    app, config = server
    data = pdf_bytes()
    doc = upload(program(app, config), data, "My Paper (2024).pdf")
    digest = hashlib.sha256(data).hexdigest()
    assert doc == {
        "id": digest[:16],
        "name": "My Paper (2024).pdf",
        "size": len(data),
        "has_report": False,
        "has_audio": False,
        "speech_cache_bytes": 0,
    }
    kept = config.work_root / digest[:16] / "source" / "My Paper (2024).pdf"
    assert kept.read_bytes() == data
    assert extract_pdf(kept).source.sha256 == digest  # the id is the source's own hash
    assert leftovers(config.work_root) == []


def test_the_same_bytes_find_the_same_folder_and_the_new_name_wins(
    server: tuple[FastAPI, Any],
) -> None:
    app, config = server
    client = program(app, config)
    data = pdf_bytes()
    first = upload(client, data, "draft.pdf")
    (config.work_root / first["id"] / "chunks").mkdir()  # what an earlier run left
    second = upload(client, data, "final.pdf")
    assert second["id"] == first["id"]
    assert second["name"] == "final.pdf"
    folder = config.work_root / first["id"]
    assert sorted(p.name for p in (folder / "source").iterdir()) == ["final.pdf"]
    assert (folder / "chunks").is_dir()
    other = upload(client, pdf_bytes("Another text."), "draft.pdf")
    assert other["id"] != first["id"]
    listed = client.get("/api/v1/documents").json()
    assert {d["id"] for d in listed} == {first["id"], other["id"]}
    assert listed[0]["id"] == other["id"]  # most recently opened first
    assert client.get(f"/api/v1/documents/{first['id']}").json()["name"] == "final.pdf"


def test_a_document_in_use_keeps_its_old_file(tmp_path: Path) -> None:
    store = DocumentStore(tmp_path, upload_limit=10_000, text_limit=10_000)
    first = store.store("a.pdf", io.BytesIO(b"%PDF-1.4 x"))
    second = store.store("b.pdf", io.BytesIO(b"%PDF-1.4 x"), in_use=first.id)
    assert first.source.is_file()
    assert second.source.is_file()
    third = store.store("c.pdf", io.BytesIO(b"%PDF-1.4 x"))
    assert sorted(p.name for p in third.source.parent.iterdir()) == ["c.pdf"]


@pytest.mark.parametrize(
    ("sent", "kept"),
    [
        ("paper.pdf", "paper.pdf"),
        ("PAPER.PDF", "PAPER.pdf"),
        ("C:\\Users\\me\\Desktop\\paper.pdf", "paper.pdf"),
        ("folder/sub/paper.pdf", "paper.pdf"),
        ("../../etc/paper.pdf", "paper.pdf"),
        ("a<b>c:d|e?f*.pdf", "a b c d e f.pdf"),
        ("con.pdf", "_con.pdf"),
        ("..pdf", "document.pdf"),
        ("<b>bold</b>.pdf", "b.pdf"),  # the last part after a slash
        ("<script>alert(1).pdf", "script alert(1).pdf"),
        ("a\U000e57eeb.pdf", "a b.pdf"),  # unassigned: APFS refuses it (#491)
    ],
)
def test_stored_names(sent: str, kept: str) -> None:
    assert stored_name(sent) == kept


@pytest.mark.parametrize("name", ["paper.docx", "paper", "", ".pdf", "paper.pdf.exe"])
def test_types_sci2audio_cant_read_are_refused_before_copying(
    server: tuple[FastAPI, Any], name: str
) -> None:
    app, config = server
    response = program(app, config).post(
        "/api/v1/documents", files={"file": (name, b"%PDF-1.4", "application/pdf")}
    )
    assert response.status_code in (415, 422), name
    if response.status_code == 415:
        assert response.json()["error"] == "unsupported-file"
        assert ".pdf" in response.json()["message"]
    assert not config.work_root.exists() or not list(config.work_root.glob("*/source"))


def test_a_file_over_the_limit_is_refused_by_its_length(tmp_path: Path) -> None:
    app, config = app_and_config(tmp_path, upload_limit=1000)
    response = program(app, config).post(
        "/api/v1/documents", files={"file": ("big.pdf", b"x" * 3_000_000, "application/pdf")}
    )
    assert response.status_code == 413
    assert response.json()["error"] == "too-large"
    assert not config.work_root.exists()


def test_a_file_over_the_limit_is_refused_while_copying(tmp_path: Path) -> None:
    app, config = app_and_config(tmp_path, upload_limit=1000)
    response = program(app, config).post(
        "/api/v1/documents", files={"file": ("big.pdf", b"x" * 1001, "application/pdf")}
    )
    assert response.status_code == 413
    assert "big.pdf" in response.json()["message"]
    assert leftovers(config.work_root) == []
    assert list(config.work_root.glob("*/source")) == []


def test_a_body_without_its_length_is_refused(server: tuple[FastAPI, Any]) -> None:
    app, config = server

    def chunks() -> Iterator[bytes]:
        yield b'{"text": "a"}'

    response = program(app, config).post(
        "/api/v1/documents/text", content=chunks(), headers={"content-type": "application/json"}
    )
    assert response.status_code == 411


def test_a_full_disk_leaves_nothing(
    server: tuple[FastAPI, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    app, config = server

    def full(fd: int) -> None:
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(documents.os, "fsync", full)
    response = program(app, config).post(
        "/api/v1/documents", files={"file": ("paper.pdf", pdf_bytes(), "application/pdf")}
    )
    assert response.status_code == 507
    assert response.json() == {
        "error": "disk-full",
        "message": "not enough disk space to open paper.pdf; free some space",
    }
    assert leftovers(config.work_root) == []
    assert list(config.work_root.glob("*/source/*")) == []


def test_another_write_error_is_named(
    server: tuple[FastAPI, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    app, config = server

    def denied(source: Any, target: Any) -> None:
        raise PermissionError(errno.EACCES, "Permission denied")

    monkeypatch.setattr(documents.os, "replace", denied)
    response = program(app, config).post(
        "/api/v1/documents", files={"file": ("paper.pdf", pdf_bytes(), "application/pdf")}
    )
    assert response.status_code == 500
    assert response.json()["error"] == "store-failed"
    assert "Permission denied" in response.json()["message"]
    assert leftovers(config.work_root) == []


def test_pasted_text_is_kept_as_a_text_file(server: tuple[FastAPI, Any]) -> None:
    """Text files are read (#74), so pasted text is taken as `<name>.txt` (D-350)."""
    app, config = server
    client = program(app, config)
    response = client.post("/api/v1/documents/text", json={"text": "Grüße.\n", "name": "Notes"})
    assert response.status_code == 201
    doc = response.json()
    assert doc["name"] == "Notes.txt"
    kept = config.work_root / doc["id"] / "source" / "Notes.txt"
    assert kept.read_bytes() == "Grüße.\n".encode()
    default = client.post("/api/v1/documents/text", json={"text": "x"}).json()
    assert default["name"] == "pasted text.txt"
    for body in ({"text": ""}, {"text": "x", "name": "n" * 201}, {"text": "x", "other": 1}):
        assert client.post("/api/v1/documents/text", json=body).status_code == 422


def test_pasted_text_over_the_limit_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app, config = app_and_config(tmp_path, text_limit=10)
    response = program(app, config).post("/api/v1/documents/text", json={"text": "ü" * 6})
    assert response.status_code == 413  # 12 bytes of UTF-8


@pytest.mark.parametrize(
    "document_id", ["0123456789abcdef", "nothing", "../../etc", "ABCDEF0123456789"]
)
def test_unknown_documents(server: tuple[FastAPI, Any], document_id: str) -> None:
    app, config = server
    client = program(app, config)
    for path in ("", "/report", "/chapters"):
        response = client.get(f"/api/v1/documents/{document_id}{path}")
        assert response.status_code == 404
        assert response.json()["error"] == "not-found"


def test_no_report_before_the_first_analysis(server: tuple[FastAPI, Any]) -> None:
    app, config = server
    client = program(app, config)
    doc = upload(client, pdf_bytes())
    for path in ("/report", "/chapters"):
        response = client.get(f"/api/v1/documents/{doc['id']}{path}")
        assert response.status_code == 404
        assert response.json()["error"] == "no-report"


def test_folders_without_a_source_are_not_documents(server: tuple[FastAPI, Any]) -> None:
    app, config = server
    (config.work_root / "0123456789abcdef" / "source").mkdir(parents=True)
    (config.work_root / "not-a-document").mkdir()
    (config.work_root / ".incoming").mkdir()
    assert program(app, config).get("/api/v1/documents").json() == []


@given(st.text(max_size=300))
def test_any_name_is_kept_inside_its_folder(name: str) -> None:
    kept = stored_name(name + "_.pdf")
    assert kept.endswith(".pdf")
    assert "/" not in kept
    assert "\\" not in kept
    assert "\x00" not in kept
    assert all(unicodedata.category(c) != "Cn" for c in kept)  # macOS refuses them (#491)
    assert PurePath(kept).name == kept
    assert kept not in (".pdf", "..pdf")
    assert len(kept.encode()) <= 255
    folder = Path("/root/0123456789abcdef/source")
    assert (folder / kept).parent == folder
    assert os.path.normpath(folder / kept).startswith(str(folder))


def test_a_new_server_removes_uploads_a_killed_one_left_behind(tmp_path: Path) -> None:
    incoming = tmp_path / "work" / documents.INCOMING
    incoming.mkdir(parents=True)
    stale, fresh, other = incoming / "a.part", incoming / "b.part", incoming / "note.txt"
    for path in (stale, fresh, other):
        path.write_bytes(b"x")
    # times from time.time() with a minute to spare, never a file's own mtime against it:
    # on Windows a file written just now can carry an mtime a little after time.time() (#157)
    over_an_hour_ago = time.time() - documents.STALE_UPLOAD - 60
    os.utime(stale, (over_an_hour_ago, over_an_hour_ago))
    app_and_config(tmp_path)  # starting a server clears what is stale
    assert sorted(path.name for path in incoming.iterdir()) == ["b.part", "note.txt"]
    # a minute old against a limit of half a minute, not "just now" against 0
    minute_ago = time.time() - 60
    os.utime(fresh, (minute_ago, minute_ago))
    store = DocumentStore(tmp_path / "work", upload_limit=10, text_limit=10)
    assert store.clear_stale_uploads(older_than=30) == [fresh]
    assert sorted(path.name for path in incoming.iterdir()) == ["note.txt"]
    assert (
        DocumentStore(tmp_path / "nothing", upload_limit=1, text_limit=1).clear_stale_uploads()
        == []
    )


NEWER = "\U0001fae8"  # Unicode 15.0: newer than an older Mac's table (#493)


def refuse_newer_targets(monkeypatch: pytest.MonkeyPatch, refused: str = NEWER) -> list[str]:
    """`os.replace` as an APFS whose Unicode table is older than Python's: a target name
    holding `refused` fails with EILSEQ. Returns the target names it was asked for."""
    asked: list[str] = []
    real = os.replace

    def fake(source: Any, target: Any) -> None:
        name = PurePath(os.fspath(target)).name
        asked.append(name)
        if refused in name:
            raise OSError(errno.EILSEQ, os.strerror(errno.EILSEQ), os.fspath(target))
        real(source, target)

    monkeypatch.setattr(documents.os, "replace", fake)
    return asked


@pytest.mark.parametrize(
    ("sent", "kept", "tries"),
    [
        (f"{NEWER} My Paper.pdf", "My Paper.pdf", 2),
        (f"{NEWER}.pdf", "document.pdf", 2),  # nothing old is left: the fallback
    ],
    ids=["retried", "fallback"],
)
def test_a_name_the_file_system_refuses_is_kept_under_the_retried_name(
    server: tuple[FastAPI, Any], monkeypatch: pytest.MonkeyPatch, sent: str, kept: str, tries: int
) -> None:
    """#493: never a 500 "store-failed"; the copy is kept, and the document is listed and
    analysed under the name that was kept."""
    app, config = server
    asked = refuse_newer_targets(monkeypatch)
    data = pdf_bytes()
    response = program(app, config).post(
        "/api/v1/documents", files={"file": (sent, data, "application/pdf")}
    )
    assert response.status_code == 201, response.text
    assert response.json()["name"] == kept
    assert asked == [stored_name(sent), kept][:tries]
    source = config.work_root / response.json()["id"] / "source"
    assert [p.name for p in source.iterdir()] == [kept]
    assert (source / kept).read_bytes() == data
    assert leftovers(config.work_root) == []


def test_a_retried_name_the_file_system_still_refuses_tries_the_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The old characters refused too (a stricter file system): `document` with the suffix."""
    store = DocumentStore(tmp_path, upload_limit=10_000, text_limit=10_000)
    asked = refuse_newer_targets(monkeypatch, refused="Paper")
    kept = store.store("Paper ü.pdf", io.BytesIO(b"%PDF-1.4 x"))
    assert asked == ["Paper ü.pdf", "document.pdf"]  # the old text is the same name
    assert kept.source.name == "document.pdf"


def test_the_last_refusal_is_a_store_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = DocumentStore(tmp_path, upload_limit=10_000, text_limit=10_000)
    refuse_newer_targets(monkeypatch, refused=".pdf")
    with pytest.raises(documents.StoreError, match="could not keep"):
        store.store("Paper.pdf", io.BytesIO(b"%PDF-1.4 x"))
    assert leftovers(tmp_path) == []


def test_another_error_while_placing_a_newer_name_is_tried_once(
    server: tuple[FastAPI, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Only EILSEQ is retried: a full disk while the copy is put in place under a name with
    a newer character is tried exactly once and answers the disk-full error, with nothing
    left behind (review of #583, R2)."""
    app, config = server
    asked: list[str] = []

    def full(source: Any, target: Any) -> None:
        asked.append(PurePath(os.fspath(target)).name)
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(documents.os, "replace", full)
    sent = f"{NEWER} My Paper.pdf"
    response = program(app, config).post(
        "/api/v1/documents", files={"file": (sent, pdf_bytes(), "application/pdf")}
    )
    assert response.status_code == 507
    assert response.json()["error"] == "disk-full"
    assert asked == [stored_name(sent)]
    assert leftovers(config.work_root) == []
    assert list(config.work_root.glob("*/source/*")) == []
