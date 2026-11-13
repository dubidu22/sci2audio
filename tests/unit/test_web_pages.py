"""The interface's pages (#77, D-244 to D-261): they render every step, escape what the
person opened, take every string from the table, and load nothing from outside the server.
The browser tests in `tests/browser/` drive the same pages with Playwright."""

from __future__ import annotations

import html
import json
import re
from importlib.resources import files
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from web_helpers import (
    ORIGIN,
    app_and_config,
    browser,
    offline,  # noqa: F401 - fixture
    paper_bytes,
    pdf_bytes,
    upload,
    wait,
)

from sci2audio.textprep import Category
from sci2audio.web import pages
from sci2audio.web.i18n import strings

pytestmark = pytest.mark.usefixtures("offline")

WEB = files("sci2audio.web")
EXTERNAL = re.compile(r"(?i)(https?:)?//[a-z0-9.-]+\.[a-z]{2,}|url\(\s*['\"]?https?:")


@pytest.fixture
def server(tmp_path: Path) -> tuple[FastAPI, Any]:
    return app_and_config(tmp_path)


def client_of(server: tuple[FastAPI, Any]) -> TestClient:
    app, config = server
    client = browser(app, config)
    client.headers["Origin"] = ORIGIN  # as the page's own script sends
    return client


def analysed(client: TestClient, settings: dict[str, Any] | None = None) -> dict[str, Any]:
    doc = upload(client, paper_bytes(), "a &amp; b 'x'.pdf")
    body = {"kind": "script", "document": doc["id"], "settings": settings or {}}
    job = client.post("/api/v1/jobs", json=body).json()
    assert wait(client, job["id"])["state"] == "done"
    return doc


def main_part(text: str) -> str:
    return text.split('<main id="main" tabindex="-1">')[1].split("</main>")[0]


def test_the_start_page_lists_documents_and_the_voice(server: tuple[FastAPI, Any]) -> None:
    client = client_of(server)
    index = client.get("/")
    assert index.status_code == 200
    assert index.headers["content-type"].startswith("text/html")
    assert "<h1>Open a document</h1>" in index.text
    assert "No document opened yet." in index.text
    assert "The voice is not installed yet." in index.text
    assert 'href="/voice"' in index.text
    assert 'accept=".epub,.pdf"' in index.text
    assert "sci2audio reads EPUB, PDF files" in index.text
    assert 'id="open-text"' not in index.text  # no text extractor yet (D-261)
    doc = upload(client, pdf_bytes(), "a &amp; b 'x'.pdf")
    page = client.get("/").text
    assert "a &amp;amp; b &#39;x&#39;.pdf" in page
    assert f'href="/documents/{doc["id"]}"' in page
    assert f"({strings('en').size(doc['size'])}, not analysed yet)" in page


def test_the_paste_box_appears_once_text_files_are_read(
    server: tuple[FastAPI, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(pages, "supported_suffixes", lambda: [".pdf", ".txt"])
    assert 'id="open-text"' in client_of(server).get("/").text


def test_a_document_before_its_analysis(server: tuple[FastAPI, Any]) -> None:
    client = client_of(server)
    doc = upload(client, pdf_bytes(), "paper.pdf")
    page = client.get(f"/documents/{doc['id']}").text
    assert "This document has not been analysed yet." in page
    assert 'id="analyse"' in page
    assert 'data-blocked="needs_analysis"' in page
    assert "Analyse the document first." in page


def test_the_document_page_shows_the_report_with_switches_and_chapters(
    server: tuple[FastAPI, Any],
) -> None:
    client = client_of(server)
    doc = analysed(client)
    page = client.get(f"/documents/{doc['id']}").text
    for heading in ("1. Check what will be read", "2. Choose a voice", "3. Make the audiobook"):
        assert heading in page
    for category in Category:  # one switch per category (UC-02)
        assert f'id="category-{category}"' in page
    assert re.search(r'id="category-footnote-texts" name="category" value="footnote-texts" ', page)
    assert 'id="category-citations" name="category" value="citations" checked' in page
    assert 'name="chapter" value="0" checked' in page
    assert re.search(r'name="chapter" value="2" aria', page)  # the reference list
    assert "reference list, not read by default" in page
    assert "Choose all" in page
    assert "Choose none" in page
    shown = json.loads(html.unescape(re.search(r'data-shown="([^"]*)"', page)[1]))
    assert shown == {"switched_off": ["footnote-texts"], "chapters": [0, 1]}
    # the latest analysis' files, saved rather than shown (D-255)
    assert f"/api/v1/documents/{doc['id']}/files/a%20%26amp%3B%20b%20%27x%27.report.md" in page
    assert "?download=true" in page
    # voice not installed: the steps say so and the start button explains why (D-252)
    assert 'data-blocked="needs_voice"' in page
    assert 'aria-disabled="true"' in page
    assert 'id="preview"' not in page
    assert 'type="range" id="speed" name="speed" min="0.5" max="2.0" step="0.05"' in page
    assert str(server[1].output_folder) in page


def test_the_controls_start_from_the_report_on_screen(server: tuple[FastAPI, Any]) -> None:
    client = client_of(server)
    doc = analysed(client, {"switched_off": ["citations"], "chapters": [1]})
    page = client.get(f"/documents/{doc['id']}").text
    assert re.search(r'value="citations" aria', page)  # unchecked
    assert 'value="footnote-texts" checked' in page  # the report's choice, not the default
    assert re.search(r'name="chapter" value="0" aria', page)
    assert 'name="chapter" value="1" checked' in page
    shown = json.loads(html.unescape(re.search(r'data-shown="([^"]*)"', page)[1]))
    assert shown == {"switched_off": ["citations"], "chapters": [1]}


def test_make_is_blocked_while_the_report_has_no_chapter_chosen(
    server: tuple[FastAPI, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(pages, "missing_files", lambda folder: [])
    client = client_of(server)
    doc = analysed(client, {"chapters": []})
    page = client.get(f"/documents/{doc['id']}").text
    assert 'data-blocked="needs_chapters"' in page
    assert "Choose at least one chapter and update the analysis." in page
    doc = analysed(client, {"chapters": [1]})
    assert 'data-blocked=""' in client.get(f"/documents/{doc['id']}").text


def test_every_proposed_change_is_listed_with_its_fate(
    server: tuple[FastAPI, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    client = client_of(server)
    doc = analysed(client)
    page = client.get(f"/documents/{doc['id']}").text
    assert "Citations: author-year and numbered citations: 1 change" in page
    assert "Reference list: left out: 2 changes" in page
    assert "(Smith, 2020)" in page
    assert "<td>applied</td>" in page
    assert "<td>not read: its chapter is not chosen</td>" in page  # the reference list's
    assert '<td class="text">not read</td>' in page
    assert "The page shows the first" not in page
    monkeypatch.setattr(pages, "EDITS_SHOWN", 1)
    page = client.get(f"/documents/{doc['id']}").text
    assert "The page shows the first 1 of 2." in page


def test_the_voice_step_once_the_voice_is_installed(
    server: tuple[FastAPI, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(pages, "missing_files", lambda folder: [])
    client = client_of(server)
    doc = analysed(client)
    page = client.get(f"/documents/{doc['id']}").text
    assert 'id="preview"' in page
    assert "This is how this voice reads your text." in page  # #18's preview sentence
    assert 'maxlength="300"' in page
    assert 'data-blocked=""' in page
    assert "Heart, American English, female (default)" in page
    assert "George, British English, male" in page
    assert page.index("(default)") < page.index("George")  # the default voice first
    assert "Kokoro-82M model and voices by hexgrad: Apache License 2.0." in page


def test_the_job_pages(server: tuple[FastAPI, Any]) -> None:
    client = client_of(server)
    doc = upload(client, pdf_bytes(), "paper.pdf")
    job = client.post("/api/v1/jobs", json={"kind": "script", "document": doc["id"]}).json()
    wait(client, job["id"])
    page = client.get(f"/jobs/{job['id']}").text
    assert "Analysis of paper.pdf" in page
    assert f'data-events="/api/v1/jobs/{job["id"]}/events"' in page
    assert ">done<" in page
    assert 'href="/documents/' in page


def test_the_voice_setup_page_shows_the_whole_download(server: tuple[FastAPI, Any]) -> None:
    client = client_of(server)
    page = client.get("/voice").text
    assert "Set up the voice" in page
    assert "kokoro-v1_0.pth" in page
    hosts = re.findall(r"<li>([^<]*)</li>", page)
    assert hosts[:2] == ["github.com", "huggingface.co"]  # with their redirect hosts after
    assert 'id="voice-consent" name="consent" required' in page
    assert re.search(r'data-plan="[0-9a-f]{64}"', page)


def test_missing_documents_and_jobs_answer_404_pages(server: tuple[FastAPI, Any]) -> None:
    client = client_of(server)
    for path in ("/documents/0123456789abcdef", "/documents/<b>", "/jobs/<b>"):
        response = client.get(path)
        assert response.status_code == 404
        assert "Not found" in response.text
        assert "<b>" not in main_part(response.text)


def test_a_running_job_is_named_on_every_page(server: tuple[FastAPI, Any]) -> None:
    import threading

    app, _ = server
    client = client_of(server)
    gate = threading.Event()

    def work(job: Any) -> list[Path]:
        gate.wait(10)
        return []

    from sci2audio.web.jobs import JobKind

    state = app.state.sci2audio
    job = state.board.start(JobKind.VOICES, None, None, work, cancellable=False)
    try:
        page = client.get("/").text
        assert "A job is running: Voice download." in page
        assert f'href="/jobs/{job.id}"' in page
    finally:
        gate.set()
        job.join(10)


# --- the string table (D-256): see test_web_languages.py ----------------------------------


def resource_texts() -> dict[str, str]:
    texts = {}
    for folder in ("templates", "static", "strings"):
        for item in (WEB / folder).iterdir():
            texts[f"{folder}/{item.name}"] = item.read_text(encoding="utf-8")
    return texts


# --- nothing from outside ----------------------------------------------------------------


def test_no_page_loads_anything_from_outside() -> None:
    texts = resource_texts()
    assert {"templates/base.html", "static/app.js", "static/app.css"} <= set(texts)
    for name, text in texts.items():
        assert not EXTERNAL.search(text), name
    script = texts["static/app.js"]
    for url in re.findall(r"[\"'`](/[^\"'`]*)", script):
        assert url.startswith(("/api/v1/", "/documents/", "/jobs/")), url
    templates = "".join(t for n, t in texts.items() if n.startswith("templates"))
    assert re.findall(r"<script[^>]*>", templates, re.IGNORECASE) == [
        '<script id="strings" type="application/json">',  # data, not code (D-256)
        '<script src="/static/app.js" defer>',
    ]
    assert " style=" not in "".join(texts.values())  # the CSP allows no inline styles
    assert re.search(r"<[^>]*\son[a-z]+=", templates) is None  # no inline handlers


def test_static_files_are_served(server: tuple[FastAPI, Any]) -> None:
    client = client_of(server)
    assert (
        client.get("/static/app.js")
        .headers["content-type"]
        .startswith(("text/javascript", "application/javascript"))
    )
    assert client.get("/static/app.css").headers["content-type"].startswith("text/css")
    assert client.get("/static/../server.py").status_code == 404
