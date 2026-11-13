"""The minimal pages (D-204): they render, escape what the person opened, and load nothing
from outside the server."""

from __future__ import annotations

import re
from importlib.resources import files
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from web_helpers import (
    app_and_config,
    browser,
    offline,  # noqa: F401 - fixture
    pdf_bytes,
    upload,
    wait,
)

pytestmark = pytest.mark.usefixtures("offline")

WEB = files("sci2audio.web")
EXTERNAL = re.compile(r"(?i)(https?:)?//[a-z0-9.-]+\.[a-z]{2,}|url\(\s*['\"]?https?:")


@pytest.fixture
def server(tmp_path: Path) -> tuple[FastAPI, Any]:
    return app_and_config(tmp_path)


def test_the_pages_render_and_escape_names(server: tuple[FastAPI, Any]) -> None:
    app, config = server
    client = browser(app, config)
    index = client.get("/")
    assert index.status_code == 200
    assert index.headers["content-type"].startswith("text/html")
    assert "Open a document" in index.text
    assert "No document opened yet." in index.text
    assert "The voice is not installed yet." in index.text
    client.headers["Origin"] = "http://127.0.0.1:8123"  # as the page's own script sends
    doc = upload(client, pdf_bytes(), "a &amp; b 'x'.pdf")
    page = client.get("/")
    assert "a &amp;amp; b &#39;x&#39;.pdf" in page.text
    document = client.get(f"/documents/{doc['id']}")
    assert document.status_code == 200
    assert "Not analysed yet." in document.text
    job = client.post(
        "/api/v1/jobs",
        json={"kind": "script", "document": doc["id"]},
        headers={"Origin": "http://127.0.0.1:8123"},
    ).json()
    wait(client, job["id"])
    analysed = client.get(f"/documents/{doc['id']}")
    assert "Chapters" in analysed.text
    assert 'name="chapter"' in analysed.text
    page = client.get(f"/jobs/{job['id']}")
    assert page.status_code == 200
    assert f"/api/v1/jobs/{job['id']}/events" in page.text
    assert "a%20%26amp%3B%20b" in page.text  # the file links are URL-encoded


def test_missing_documents_and_jobs_answer_404_pages(server: tuple[FastAPI, Any]) -> None:
    app, config = server
    client = browser(app, config)
    for path in ("/documents/0123456789abcdef", "/documents/<b>", "/jobs/nothing"):
        response = client.get(path)
        assert response.status_code == 404
        assert "Not found" in response.text
        assert "<b>" not in response.text.split("<main>")[1]


def resource_texts() -> dict[str, str]:
    texts = {}
    for folder in ("templates", "static"):
        for item in (WEB / folder).iterdir():
            texts[f"{folder}/{item.name}"] = item.read_text(encoding="utf-8")
    return texts


def test_no_page_loads_anything_from_outside() -> None:
    texts = resource_texts()
    assert {"templates/base.html", "static/app.js", "static/app.css"} <= set(texts)
    for name, text in texts.items():
        assert not EXTERNAL.search(text), name
    script = texts["static/app.js"]
    for url in re.findall(r"[\"'`](/[^\"'`]*)", script):
        assert url.startswith(("/api/v1/", "/documents/", "/jobs/")), url
    assert "<script>" not in "".join(t for n, t in texts.items() if n.startswith("templates"))
    assert " style=" not in "".join(texts.values())  # the CSP allows no inline styles


def test_static_files_are_served(server: tuple[FastAPI, Any]) -> None:
    app, config = server
    client = browser(app, config)
    assert (
        client.get("/static/app.js")
        .headers["content-type"]
        .startswith(("text/javascript", "application/javascript"))
    )
    assert client.get("/static/app.css").headers["content-type"].startswith("text/css")
    assert client.get("/static/../server.py").status_code == 404
