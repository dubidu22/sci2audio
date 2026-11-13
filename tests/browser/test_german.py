"""The interface in German (#79, AQ-02; D-288 to D-293): the main flow and the other page
states with axe-core in light and dark colours (D-257), the language switch by keyboard,
and the privacy page in both languages.

The browser here asks for German (`locale` de-DE, so `Accept-Language: de-DE,…`), as a
browser set to German does; the switch then changes the language with its cookie.
"""

from __future__ import annotations

import re
import threading
from typing import Any

import pytest
from playwright.sync_api import Page, expect
from test_flow import PDF, gated, slow, until
from test_keyboard import press_on, tab_to

from conftest import Live, check_axe, settled
from sci2audio.voices import PREVIEW_TEXT, EngineError
from sci2audio.web.i18n import COOKIE
from sci2audio.web.jobs import JobKind


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args: dict[str, Any]) -> dict[str, Any]:
    return {**browser_context_args, "locale": "de-DE"}


def open_paper(page: Page) -> str:
    page.set_input_files("#file", files=[PDF])
    page.get_by_role("button", name="Öffnen und analysieren").click()
    page.wait_for_url(re.compile(r"/documents/[0-9a-f]{16}"))
    expect(page.locator("#summary")).to_be_visible()
    settled(page)
    return page.url.rsplit("/", 1)[1].split("#")[0]


def expect_german(page: Page) -> None:
    expect(page.locator("html")).to_have_attribute("lang", "de")


def test_the_main_flow_in_german(signed_in: Page, live: Live) -> None:
    page = signed_in
    expect_german(page)
    expect(page.get_by_role("heading", level=1)).to_have_text("Dokument öffnen")
    check_axe(page, "de: start page, nothing opened")

    document = open_paper(page)
    expect(page.locator("#summary")).to_have_text(
        "3 Kapitel, davon 2 ausgewählt. sci2audio schlägt 3 Änderungen vor."
        " 1 davon ändert, was Sie hören."
    )
    expect(page.locator("#counts-citations")).to_contain_text("1 hörbar")
    expect(page.locator("#make-note")).to_have_text("Richten Sie zuerst die Stimme ein.")
    check_axe(page, "de: document with its report, voice missing")
    page.get_by_text(re.compile(r"^Zitate: Autor-Jahr- .*: 1 Änderung$")).click()
    expect(page.get_by_role("cell", name="(Smith, 2020)", exact=True)).to_have_attribute(
        "lang", "en"
    )  # the document's words keep their language (D-291)
    reason = page.get_by_role("cell", name=re.compile(r"^citation .* is not read"))
    expect(reason).to_have_attribute("lang", "en")  # the app's words, as written
    expect(page.get_by_role("cell", name="angewendet", exact=True)).to_be_visible()
    check_axe(page, "de: document with a list of changes open")

    # a switch off and the analysis updated, in German
    page.get_by_role("checkbox", name=re.compile("^Zitate")).uncheck()
    expect(page.locator("#changed")).to_be_visible()
    expect(page.locator("#changed")).to_have_text(
        "Sie haben die Auswahl geändert. Aktualisieren Sie die Analyse, um zu sehen, was sich"
        " dadurch ändert."
    )
    page.get_by_role("button", name="Analyse aktualisieren").click()
    expect(page.locator("#changed")).to_be_hidden()
    expect(page.locator("#counts-citations")).to_contain_text("1 ausgeschaltet")
    page.get_by_role("checkbox", name=re.compile("^Zitate")).check()
    page.get_by_role("button", name="Analyse aktualisieren").click()
    expect(page.locator("#changed")).to_be_hidden()

    # the voice, with the privacy page next to the consent (D-293)
    page.get_by_role("link", name="Stimme einrichten").first.click()
    expect(page.get_by_role("heading", level=1)).to_have_text("Stimme einrichten")
    expect(
        page.get_by_role("link", name="Was sci2audio mit dem Netz und Ihren Dateien macht")
    ).to_be_visible()
    check_axe(page, "de: voice setup page")
    page.get_by_role("checkbox", name=re.compile("Ich bin einverstanden")).check()
    page.get_by_role("button", name="Stimme herunterladen").click()
    page.wait_for_url(re.compile(r"/jobs/voices-\d+"))
    expect(page.locator("#result")).to_have_text(
        "Die Stimme ist installiert. Es muss nichts heruntergeladen werden."
    )
    check_axe(page, "de: voice download done")

    # preview and speed: the decimal comma (D-290); the preview sentence stays English
    page.goto(f"{live.url}/documents/{document}")
    speed = page.get_by_role("slider", name="Tempo")
    speed.focus()
    for _ in range(5):
        page.keyboard.press("ArrowRight")
    expect(page.locator("#speed-value")).to_have_text("1,25-fach")
    expect(speed).to_have_attribute("aria-valuetext", "1,25-fach")
    expect(page.locator("#preview-text")).to_have_attribute("lang", "en")
    page.get_by_role("button", name="Anhören").click()
    player = page.locator("#preview-audio")
    expect(player).to_be_visible()
    until(lambda: player.evaluate("audio => audio.readyState") >= 1)
    assert live.voice.spoken[-1][0] == PREVIEW_TEXT
    check_axe(page, "de: document with the voice installed and a preview")

    # the audiobook
    page.get_by_role("button", name="Hörbuch erstellen").click()
    page.wait_for_url(re.compile(r"/jobs/[0-9a-f]{16}-audio-\d+"))
    expect(page.locator("#result")).to_have_text("Ihr Hörbuch ist fertig")
    expect(page.get_by_role("link", name=re.compile(r"^paper\.m4b speichern \("))).to_be_visible()
    check_axe(page, "de: audiobook done")

    # the player (#78): German controls; chapter titles keep the document's language (D-291)
    page.get_by_role("link", name="Mit dem Text anhören").click()
    expect(page.get_by_role("heading", level=1)).to_have_text(re.compile(r"^Anhören: "))
    expect(page.get_by_role("button", name="Abspielen")).to_be_visible()
    language = page.locator("#text").get_attribute("lang")
    assert language
    expect(page.locator(".chapter-button").first).to_have_attribute("lang", language)
    expect(page.locator("#now span")).to_have_attribute("lang", language)
    check_axe(page, "de: listen page")
    page.get_by_role("button", name="Nächstes Kapitel").click()
    expect(page.locator("#now")).to_have_text(re.compile(r"^Kapitel 2 von 2: \S"))
    expect(page.locator("#now span")).to_have_attribute("lang", language)
    expect(page.locator("#message")).to_have_text(re.compile(r"^Kapitel 2 von 2: \S"))
    check_axe(page, "de: listen page after a jump")

    # again: the files exist; the kind's sentence in German, the app's words as details
    page.get_by_role("link", name="Zurück zum Dokument").click()
    page.get_by_role("button", name="Hörbuch erstellen").click()
    expect(page.locator("#result")).to_have_text(
        "Der Auftrag ist fehlgeschlagen: Die Hörbuchdateien gibt es schon."
    )
    details = page.locator("#job p", has_text="Details von sci2audio:")
    expect(details.locator("span[lang=en]")).to_contain_text("exist already")
    check_axe(page, "de: audiobook files exist")
    page.get_by_role("button", name="Diese Dateien ersetzen").click()
    expect(page.locator("#result")).to_have_text("Ihr Hörbuch ist fertig")
    page.get_by_role("button", name="Sprachzwischenspeicher leeren").click()
    expect(page.locator("#message")).to_have_text("Der Sprachzwischenspeicher ist leer.")


def test_progress_and_cancel_in_german(signed_in: Page, live: Live) -> None:
    page = signed_in
    live.install_voice()
    live.voice.fail_on = slow(1.0)
    open_paper(page)
    page.get_by_role("button", name="Hörbuch erstellen").click()
    page.wait_for_url(re.compile(r"/jobs/[0-9a-f]{16}-audio-\d+"))
    progress = page.locator("#job-progress")
    expect(progress).to_contain_text("es wird gesprochen")
    expect(progress).to_contain_text(re.compile(r"\d von \d Sätzen"))
    expect(progress).to_contain_text("das Tempo wird gemessen")
    expect(page.locator(".running")).to_contain_text("Ein Auftrag läuft: Hörbuch von paper.pdf.")
    check_axe(page, "de: audiobook running")
    page.get_by_role("button", name="Abbrechen").click()
    expect(page.locator("#result")).to_have_text("Der Auftrag wurde abgebrochen.")
    check_axe(page, "de: audiobook cancelled")


def test_a_running_download_in_german(signed_in: Page, live: Live) -> None:
    page = signed_in
    live.fetch.delay = 0.4
    page.goto(live.url + "/voice")
    page.get_by_role("checkbox", name=re.compile("Ich bin einverstanden")).check()
    page.get_by_role("button", name="Stimme herunterladen").click()
    page.wait_for_url(re.compile(r"/jobs/voices-\d+"))
    expect(page.locator("#job-progress")).to_contain_text(
        re.compile(r"wird heruntergeladen, \d+\s%")
    )
    check_axe(page, "de: voice download running")
    page.get_by_role("button", name="Abbrechen").click()
    expect(page.locator("#result")).to_have_text("Der Auftrag wurde abgebrochen.")


def test_errors_in_german_with_the_apps_words(signed_in: Page, live: Live) -> None:
    page = signed_in
    # a file sci2audio can't read: said by the page's script
    page.set_input_files(
        "#file",
        files=[{"name": "notes.docx", "mimeType": "application/octet-stream", "buffer": b"x"}],
    )
    page.get_by_role("button", name="Öffnen und analysieren").click()
    message = page.locator("#message")
    expect(message).to_contain_text("Diese Art von Datei kann sci2audio nicht lesen.")
    expect(message.locator("span[lang=en]")).to_have_text(
        "notes.docx: sci2audio can read .epub, .pdf files only"
    )
    expect(message).to_be_focused()
    check_axe(page, "de: start page with an error")

    # another job running: the switch of a document is refused, in German
    open_paper(page)
    job, gate = gated(live.state, JobKind.VOICES, None)
    try:
        page.reload()
        expect(page.locator(".running")).to_contain_text("Ein Auftrag läuft: Download der Stimme.")
        page.get_by_role("checkbox", name="Methods").uncheck()
        page.get_by_role("button", name="Analyse aktualisieren").click()
        expect(message).to_contain_text("Ein anderer Auftrag läuft.")
        expect(message.locator("span[lang=en]")).to_contain_text(f"job {job.id} is running")
        check_axe(page, "de: document while another job runs")
    finally:
        gate.set()
        job.join(10)

    # a damaged file: the analysis failed, said by the page itself
    damaged = {"name": "broken.pdf", "mimeType": "application/pdf", "buffer": b"%PDF-1.4 nothing"}
    page.goto(live.url + "/")
    page.set_input_files("#file", files=[damaged])
    page.get_by_role("button", name="Öffnen und analysieren").click()
    page.wait_for_url(re.compile(r"/documents/[0-9a-f]{16}"))
    expect(page.locator("#analysis-error")).to_contain_text("Die Analyse ist fehlgeschlagen:")
    expect(page.get_by_role("button", name="Dokument analysieren")).to_be_visible()
    check_axe(page, "de: document whose analysis failed")


def test_a_failed_job_in_german(signed_in: Page, live: Live) -> None:
    page = signed_in
    live.install_voice()
    open_paper(page)
    live.voice.fail_to_make = EngineError("the model file is damaged")
    page.get_by_role("button", name="Hörbuch erstellen").click()
    page.wait_for_url(re.compile(r"/jobs/[0-9a-f]{16}-audio-\d+"))
    expect(page.locator("#result")).to_contain_text("Der Auftrag ist fehlgeschlagen:")
    expect(page.get_by_role("button", name="Neu starten")).to_be_visible()
    check_axe(page, "de: audiobook failed")


def test_pages_that_dont_exist_in_german(signed_in: Page, live: Live) -> None:
    page = signed_in
    for path in ("/documents/0123456789abcdef", "/jobs/nothing"):
        response = page.goto(live.url + path)
        assert response is not None
        assert response.status == 404
        expect(page.get_by_role("heading", level=1)).to_have_text("Nicht gefunden")
        check_axe(page, f"de: not found: {path}")


def test_the_privacy_page_in_both_languages_from_the_footer(signed_in: Page, live: Live) -> None:
    page = signed_in
    press_on(page, "Wie sci2audio mit Ihren Daten umgeht")
    page.wait_for_url(live.url + "/privacy")
    expect(page.get_by_role("heading", level=1)).to_have_text(
        "Datenschutz: Was auf diesem Computer bleibt"
    )
    expect(page.get_by_text(str(live.config.work_root), exact=True)).to_be_visible()
    expect(page.get_by_role("listitem").filter(has_text="example.test")).to_be_visible()
    check_axe(page, "de: privacy page")
    page.get_by_role("button", name="English").click()
    page.wait_for_url(live.url + "/privacy")
    expect(page.locator("html")).to_have_attribute("lang", "en")
    expect(page.get_by_role("heading", level=1)).to_have_text(
        "Privacy: what stays on this computer"
    )
    check_axe(page, "en: privacy page")


def test_the_language_switch_by_keyboard(signed_in: Page, live: Live) -> None:
    page = signed_in
    document = open_paper(page)
    expect(page.get_by_role("button", name="Deutsch")).to_have_attribute("aria-pressed", "true")
    press_on(page, "English")
    page.wait_for_url(f"{live.url}/documents/{document}")
    expect(page.locator("html")).to_have_attribute("lang", "en")
    expect(page.get_by_role("heading", level=2, name="1. Check what will be read")).to_be_visible()
    expect(page.get_by_role("button", name="English")).to_have_attribute("aria-pressed", "true")
    check_axe(page, "en: document after the switch")

    # the choice is the cookie's, so it holds in a new tab despite the German browser
    cookie = next(c for c in page.context.cookies() if c["name"] == COOKIE)
    assert cookie["value"] == "en"
    assert cookie["sameSite"] == "Strict"
    assert cookie["httpOnly"] is True
    other = page.context.new_page()
    other.route(
        "**/*",
        lambda route: (
            route.continue_() if route.request.url.startswith(live.url + "/") else route.abort()
        ),
    )
    other.goto(live.url + "/voice")
    expect(other.locator("html")).to_have_attribute("lang", "en")
    other.close()

    # and back to German, by keyboard again
    page.goto(f"{live.url}/documents/{document}")
    tab_to(page, "Deutsch")
    page.keyboard.press("Space")
    page.wait_for_url(f"{live.url}/documents/{document}")
    expect_german(page)
    check_axe(page, "de: document after switching back")


def test_the_switch_keeps_the_job_page_running(signed_in: Page, live: Live) -> None:
    """Switching while a job runs comes back to the same job page, still following it."""
    page = signed_in
    gate = threading.Event()
    job = live.state.board.start(
        JobKind.VOICES, None, None, lambda job: gate.wait(30) and [], cancellable=False
    )
    try:
        page.goto(f"{live.url}/jobs/{job.id}")
        expect(page.locator("#job-state")).to_have_text("läuft")
        page.get_by_role("button", name="English").click()
        page.wait_for_url(f"{live.url}/jobs/{job.id}")
        expect(page.locator("#job-state")).to_have_text("running")
    finally:
        gate.set()
        job.join(10)
