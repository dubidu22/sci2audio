"""The Settings page in a real browser (#388; D-671, D-673): appearance and announcements by
keyboard, kept in their cookies; the defaults for new audiobooks saved without losing the
other settings; a bad folder explained; axe in English and German."""

from __future__ import annotations

from playwright.sync_api import Page, expect
from test_keyboard import press_on, tab_to

from conftest import Live, check_axe, saving
from sci2audio.app import JobSettings, load_settings, save_settings
from sci2audio.textprep import Category
from sci2audio.web.i18n import ANNOUNCE_COOKIE, KEYS_COOKIE, THEME_COOKIE


def cookie(page: Page, name: str) -> dict[str, object] | None:
    return next((c for c in page.context.cookies() if c["name"] == name), None)


def test_dark_chosen_by_keyboard_holds_on_every_page(signed_in: Page, live: Live) -> None:
    page = signed_in
    press_on(page, "Settings")
    page.wait_for_url(live.url + "/settings")
    expect(page.get_by_role("button", name="As the system")).to_have_attribute(
        "aria-pressed", "true"
    )
    check_axe(page, "settings")
    with saving(page, "/appearance"):
        press_on(page, "Dark", "Space")
    page.wait_for_url(live.url + "/settings")
    expect(page.locator("html")).to_have_attribute("data-theme", "dark")
    expect(page.get_by_role("button", name="Dark")).to_have_attribute("aria-pressed", "true")
    page.wait_for_load_state("load")
    background = page.evaluate("() => getComputedStyle(document.body).backgroundColor")
    assert background == "rgb(17, 19, 23)"  # the dark desk, though the system is light
    check_axe(page, "settings, dark chosen")
    page.goto(live.url + "/voice")
    expect(page.locator("html")).to_have_attribute("data-theme", "dark")
    chosen = cookie(page, THEME_COOKIE)
    assert chosen is not None
    assert chosen["value"] == "dark"
    assert chosen["httpOnly"] is True
    assert chosen["sameSite"] == "Strict"
    assert live.url.rsplit(":", 1)[1] not in THEME_COOKIE  # outlasts the server run (D-671)
    page.goto(live.url + "/settings")
    with saving(page, "/appearance"):
        page.get_by_role("button", name="Light").click()
    page.wait_for_url(live.url + "/settings")
    expect(page.locator("html")).to_have_attribute("data-theme", "light")
    page.emulate_media(color_scheme="dark")
    page.wait_for_load_state("load")
    background = page.evaluate("() => getComputedStyle(document.body).backgroundColor")
    assert background == "rgb(237, 239, 242)"  # light chosen beats a dark system
    page.emulate_media(color_scheme="light")


def test_the_defaults_are_saved_and_every_other_setting_is_kept(
    signed_in: Page, live: Live
) -> None:
    page = signed_in
    kept = JobSettings(switched_off=frozenset({Category.CITATIONS}), letter_pace="slower")
    save_settings(kept, live.config.config_file)
    page.goto(live.url + "/settings")
    folder = live.config.output_folder.parent / "My audiobooks"
    page.get_by_label("Audiobook folder").fill(str(folder))
    tab_to(page, "settings-speed")
    for _ in range(3):
        page.keyboard.press("ArrowLeft")
    expect(page.locator("#settings-speed-value")).to_have_text("0.85 times")
    press_on(page, "Save the defaults")
    message = page.locator("#message")
    expect(message).to_have_text("Saved. New audiobooks use these defaults.")
    expect(message).to_be_focused()
    saved, warnings = load_settings(live.config.config_file)
    assert warnings == []
    assert saved.output_folder == folder
    assert saved.speed == 0.85
    assert saved.switched_off == kept.switched_off
    assert saved.letter_pace == "slower"
    page.reload()
    expect(page.get_by_label("Audiobook folder")).to_have_value(str(folder))
    check_axe(page, "settings after saving")


def test_a_folder_that_is_no_full_path_is_explained(signed_in: Page, live: Live) -> None:
    page = signed_in
    page.goto(live.url + "/settings")
    page.get_by_label("Audiobook folder").fill("audiobooks")
    page.get_by_role("button", name="Save the defaults").click()
    message = page.locator("#message")
    expect(message).to_contain_text("must be a full path")
    expect(message).to_be_focused()
    assert not live.config.config_file.exists()
    check_axe(page, "settings with a bad folder")


def test_the_announce_switch_saves_itself(signed_in: Page, live: Live) -> None:
    page = signed_in
    page.goto(live.url + "/settings")
    switch = page.get_by_role("switch", name="Announce the sentence being read to screen readers")
    expect(switch).not_to_be_checked()
    expect(page.locator("#announce-save-line")).to_be_hidden()  # the script saves on change
    tab_to(page, "settings-announce")
    # the page is on /settings already: wait for the save, not for the address (#429)
    with saving(page, "/appearance"):
        page.keyboard.press("Space")
    page.wait_for_url(live.url + "/settings")
    expect(switch).to_be_checked()
    chosen = cookie(page, ANNOUNCE_COOKIE)
    assert chosen is not None
    assert chosen["value"] == "on"
    with saving(page, "/appearance"):
        switch.click()
    page.wait_for_url(live.url + "/settings")
    expect(switch).not_to_be_checked()
    assert (cookie(page, ANNOUNCE_COOKIE) or {}).get("value") == "off"


def test_the_keys_switch_saves_itself_and_every_page_carries_it(
    signed_in: Page, live: Live
) -> None:
    """#451 review S3: on by default; switched off, every page says so to its scripts."""
    page = signed_in
    page.goto(live.url + "/settings")
    switch = page.get_by_role("switch", name="Keyboard shortcuts")
    expect(switch).to_be_checked()
    expect(page.locator("#keys-save-line")).to_be_hidden()
    with saving(page, "/appearance"):
        switch.click()
    page.wait_for_url(live.url + "/settings")
    expect(switch).not_to_be_checked()
    assert (cookie(page, KEYS_COOKIE) or {}).get("value") == "off"
    check_axe(page, "settings, keys off")
    page.goto(live.url + "/privacy")
    expect(page.locator("html")).to_have_attribute("data-keys", "off")
    page.keyboard.press("?")
    expect(page.locator("#keys")).to_be_hidden()
    page.goto(live.url + "/settings")
    with saving(page, "/appearance"):
        switch.click()
    page.wait_for_url(live.url + "/settings")
    expect(switch).to_be_checked()
    assert (cookie(page, KEYS_COOKIE) or {}).get("value") == "on"
    expect(page.locator("html")).not_to_have_attribute("data-keys", "off")


def test_settings_in_german(signed_in: Page, live: Live) -> None:
    page = signed_in
    page.goto(live.url + "/language?language=de&back=/settings")
    expect(page.get_by_role("heading", level=1)).to_have_text("Einstellungen")
    for words in ("Darstellung", "Sprache der Oberfläche", "Vorgaben für neue Hörbücher"):
        expect(page.get_by_role("heading", level=2, name=words)).to_be_visible()
    expect(page.get_by_role("button", name="Wie das System")).to_be_visible()
    announce = page.get_by_role("switch", name="Gelesenen Satz für Screenreader ansagen")
    expect(announce).to_be_visible()
    expect(page.get_by_role("switch", name="Tastenkürzel")).to_be_checked()
    expect(page.get_by_role("link", name="Bibliothek, 0 Dokumente", exact=True)).to_be_visible()
    check_axe(page, "de: settings")
