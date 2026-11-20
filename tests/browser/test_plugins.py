"""The text-step plugins in a real browser (#668, #685): the document page lists the plugins
an analysis ran with, and the privacy page names the installed ones and what a plugin can
do; both pass axe, the privacy page in English and German."""

from __future__ import annotations

from playwright.sync_api import Page, expect
from test_flow import open_paper
from web_helpers import plugin_steps

from conftest import Live, check_axe
from sci2audio.app import JobRunner


def with_plugin(live: Live) -> None:
    live.state.runner = JobRunner(plugin_steps())


def test_the_document_page_lists_its_plugins_and_passes_axe(signed_in: Page, live: Live) -> None:
    page = signed_in
    with_plugin(live)
    open_paper(page, live)
    plugins = page.locator("#plugins")
    expect(plugins).to_contain_text("ampersand-and")
    expect(plugins).to_contain_text("sci2audio-example 0.1")
    check_axe(page, "document page with a text-step plugin")


def test_the_privacy_page_names_the_plugin_and_passes_axe(signed_in: Page, live: Live) -> None:
    page = signed_in
    page.goto(live.url + "/privacy")
    expect(page.locator("#plugins-installed")).to_contain_text("No text-step plugins are installed")
    with_plugin(live)
    page.reload()
    expect(page.locator("#plugins-installed")).to_contain_text("ampersand-and")
    check_axe(page, "privacy page with a text-step plugin")
    page.goto(live.url + "/language?language=de&back=/privacy")
    expect(page.locator("html")).to_have_attribute("lang", "de")
    expect(page.locator("#plugins-installed")).to_contain_text("ampersand-and")
    check_axe(page, "privacy page with a text-step plugin, German")
