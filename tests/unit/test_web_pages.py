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
from test_layout_language import german_pdf
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
from sci2audio.voices import download_plan
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
    assert 'accept=".epub,.markdown,.md,.pdf,.txt"' in index.text
    assert "sci2audio reads EPUB, MARKDOWN, MD, PDF, TXT files" in index.text
    assert 'id="open-text"' in index.text  # text files are read, so pasted text is (#74)
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
    assert shown == {"switched_off": ["footnote-texts"], "chapters": [0, 1], "language": ""}
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
    assert shown == {"switched_off": ["citations"], "chapters": [1], "language": ""}


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


def test_a_german_text_starts_with_the_german_voice(
    server: tuple[FastAPI, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """#211, D-469: the page starts with the voice the job would use, and its preview
    sentence is in that voice's language; a missing German pack is named."""
    german = list(download_plan(["de"]).files)
    monkeypatch.setattr(pages, "missing_files", lambda folder: german)
    client = client_of(server)
    doc = analysed(client, {"language": "de"})
    page = client.get(f"/documents/{doc['id']}").text
    assert re.search(r'<option value="dm_thorsten" data-language="de-DE" selected>', page)
    assert "Thorsten, German, male (default for German)" in page
    assert 'lang="de"' in page
    assert "So liest diese Stimme Ihren Text vor." in page
    assert "The voice for German is not installed yet." in page
    assert 'data-blocked="needs_voice"' in page  # its job would need the German files
    assert 'id="preview"' in page  # the English voices can still be heard
    english = client.get(f"/documents/{analysed(client)['id']}").text
    assert 'data-blocked=""' in english
    assert re.search(r'<option value="af_heart" data-language="en-US" selected>', english)
    assert "This is how this voice reads your text." in english
    assert "Not every voice is installed yet. Missing: German." in client.get("/").text


def test_the_document_page_says_where_the_language_came_from(
    server: tuple[FastAPI, Any],
) -> None:
    """D-499: the text's language and its source, in the page's language."""
    client = client_of(server)
    guessed = analysed(client)  # an untagged PDF too short to tell its language (D-495)
    page = client.get(f"/documents/{guessed['id']}").text
    assert (
        "Language of the text: English (the text did not show whether it is English or German)."
        in page
    )
    assert 'aria-describedby="text-language voice-language voice-licence"' in page
    chosen = analysed(client, {"language": "de"})
    assert "Language of the text: German (your setting)." in (
        client.get(f"/documents/{chosen['id']}").text
    )
    client.cookies.set("sci2audio-language", "de")
    assert "Sprache des Textes: Deutsch (Ihre Einstellung)." in (
        client.get(f"/documents/{chosen['id']}").text
    )
    german = upload(client, german_pdf(), "studie.pdf")
    body = {"kind": "script", "document": german["id"], "settings": {}}
    job = client.post("/api/v1/jobs", json=body).json()
    assert wait(client, job["id"])["state"] == "done"
    assert "Sprache des Textes: Deutsch (aus dem Text erkannt)." in (
        client.get(f"/documents/{german['id']}").text
    )


def test_a_report_from_before_v1_1_shows_no_language_line(server: tuple[FastAPI, Any]) -> None:
    client = client_of(server)
    assert pages._language_note({"language": "en"}, strings("en")) is None
    assert pages._language_note(None, strings("en")) is None
    note = pages._language_note({"language": "fr", "language_source": "file"}, strings("en"))
    assert note == "Language of the text: fr (as the file states)."
    assert client.get("/").status_code == 200


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
    assert "model.pth" in page  # the German pack (#211)
    items = re.findall(r"<li>([^<]*)</li>", page)
    assert items[:2] == [  # one line per voice pack (D-468)
        "English voices (Kokoro): not installed yet.",
        "German voice Thorsten (Kokoro, by Thorsten-Voice): not installed yet.",
    ]
    hosts = items[2:]
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
    for script in (texts["static/app.js"], texts["static/player.js"]):
        for url in re.findall(r"[\"'`](/[^\"'`]*)", script):
            assert url.startswith(("/api/v1/", "/documents/", "/jobs/")), url
    templates = "".join(t for n, t in texts.items() if n.startswith("templates"))
    assert sorted(re.findall(r"<script[^>]*>", templates, re.IGNORECASE)) == sorted(
        [
            '<script id="strings" type="application/json">',  # data, not code (D-256)
            '<script src="/static/app.js" defer>',
            '<script src="/static/player.js" defer>',  # the listen page only (D-302)
            '<script id="player-data" type="application/json">',  # data, not code
        ]
    )
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


def test_the_check_table_shows_a_line_break_in_an_edit_as_the_report_does() -> None:
    """#118: an edit of a line-end hyphen quotes "↵" or "-↵", not an empty cell."""
    s = strings("en")
    edit = {"category": "characters", "status": "accepted", "spoken": True, "kind": "remove"}
    kept = pages._row({**edit, "original": "\n"}, {}, s)
    joined = pages._row({**edit, "original": "-\n"}, {}, s)
    running = pages._row({**edit, "original": "(Smith,\n2019)"}, {}, s)
    position = pages._row({**edit, "kind": "pause", "original": ""}, {}, s)
    assert (kept.printed, joined.printed, running.printed) == ("↵", "-↵", "(Smith, 2019)")
    assert kept.printed_is_text
    assert (position.printed, position.printed_is_text) == (s("check.position"), False)


GERMAN_NOTE = (
    Path(__file__).resolve().parents[1] / "corpus" / "markdown" / "sci2audio-beispiel-notiz.md"
)


def analysed_note(client: TestClient, doc: dict[str, Any], settings: dict[str, Any]) -> str:
    body = {"kind": "script", "document": doc["id"], "settings": settings}
    job = client.post("/api/v1/jobs", json=body).json()
    assert wait(client, job["id"])["state"] == "done"
    return client.get(f"/documents/{doc['id']}").text


def shown_of(page: str) -> dict[str, Any]:
    found = re.search(r'data-shown="([^"]*)"', page)
    assert found
    return json.loads(html.unescape(found[1]))


def test_the_language_of_the_text_is_chosen_on_the_check_form(
    server: tuple[FastAPI, Any],
) -> None:
    """#212 (D-521, D-522): automatic by default; English, German or the report's own tag;
    the notices follow it; the page keeps the choice for this document's jobs."""
    client = client_of(server)
    doc = upload(client, GERMAN_NOTE.read_bytes(), "notiz.md")
    page = analysed_note(client, doc, {})
    assert re.search(r'<select id="language" name="language" aria-describedby="text-language '
                     r'language-hint">', page)  # fmt: skip
    assert (
        '<option value="" selected>Automatic: as the file states, else guessed from the text'
        in (page)
    )
    assert '<option value="en">English</option><option value="de">German</option>' in page
    assert "Language of the text: German (as the file states)." in page
    assert "Eine Tabelle wird übersprungen." in page
    assert "Fußnote 1." in page
    assert shown_of(page)["language"] == ""
    page = analysed_note(client, doc, {"language": "en"})
    assert '<option value="en" selected>English</option>' in page
    assert "A table is skipped." in page
    assert "Eine Tabelle wird übersprungen." not in page
    assert shown_of(page)["language"] == "en"
    page = analysed_note(client, doc, {"language": "en-GB"})
    assert '<option value="en-GB" selected>en-GB (your setting)</option>' in page
    assert shown_of(page)["language"] == "en-GB"
    client.cookies.set("sci2audio-language", "de")
    page = client.get(f"/documents/{doc['id']}").text
    assert '<label for="language">Sprache des Textes</label>' in page
    assert '<option value="de">Deutsch</option>' in page
    assert "en-GB (Ihre Einstellung)" in page


def test_the_language_choice_is_not_saved_with_the_settings(server: tuple[FastAPI, Any]) -> None:
    client = client_of(server)
    doc = upload(client, GERMAN_NOTE.read_bytes(), "notiz.md")
    analysed_note(client, doc, {"language": "en"})
    assert client.get("/api/v1/settings").json()["settings"]["language"] == ""
    other = analysed(client)  # the next document starts automatic
    assert shown_of(client.get(f"/documents/{other['id']}").text)["language"] == ""
