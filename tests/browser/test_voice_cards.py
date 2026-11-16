"""The Voices page's cards (#419): a sample per voice, one playing at a time, by keyboard,
drawn disabled until app.js wires them, and read by axe in light, dark and German."""

from __future__ import annotations

from playwright.sync_api import Page, expect
from test_flow import reload_holding_back_app_js, until

from conftest import Hold, Live, check_axe
from sci2audio.voices import preview_text


def playing(page: Page) -> bool:
    return bool(page.locator("#voice-sample").evaluate("a => !a.paused && !!a.src"))


def test_a_sample_plays_by_keyboard_and_a_second_stops_the_first(
    signed_in: Page, live: Live
) -> None:
    page = signed_in
    live.install_voice()
    page.goto(live.url + "/voice")
    heart = page.get_by_role("button", name="Play a sample of Heart")
    heart.focus()
    page.keyboard.press("Enter")
    stop_heart = page.get_by_role("button", name="Stop the sample of Heart")
    expect(stop_heart).to_have_text("Stop the sample")
    until(lambda: playing(page))
    assert live.voice.spoken[-1] == (preview_text("en"), "af_heart", 1.0)
    check_axe(page, "voices, a sample playing")
    # a second Play stops the first at once, before its own sample is made
    page.locator("#voice-sample").evaluate("a => { a.loop = true; }")  # still playing
    stopped = page.locator("#voice-sample").evaluate(
        """a => {
            document.querySelector('[data-voice="bm_george"]').click();
            return a.paused && !a.getAttribute("src");
        }"""
    )
    assert stopped
    expect(page.get_by_role("button", name="Play a sample of Heart")).to_be_visible()
    expect(page.get_by_role("button", name="Stop the sample of George")).to_be_visible()
    until(lambda: live.voice.spoken[-1][1] == "bm_george")
    until(lambda: playing(page))
    assert page.locator(".voice-play[aria-label^='Stop']").count() == 1  # one at a time
    page.get_by_role("button", name="Stop the sample of George").click()
    until(lambda: not playing(page))
    expect(page.locator(".voice-play[aria-label^='Stop']")).to_have_count(0)
    # the sample keeps no position: played again, it starts from the beginning
    page.get_by_role("button", name="Play a sample of George").click()
    until(lambda: playing(page))
    assert page.locator("#voice-sample").evaluate("a => a.currentTime") < 1


def count_ended_jobs(page: Page) -> None:
    """Count each preview job's end as the page's own handler gets it (`window.ended`)."""
    page.evaluate(
        """() => {
            const original = window.follow;
            window.ended = 0;
            window.follow = (url, progress, end, quiet) =>
                original(url, progress, (job) => { end(job); window.ended += 1; }, quiet);
        }"""
    )


def test_a_sample_stopped_while_it_is_made_never_plays(signed_in: Page, live: Live) -> None:
    """#446 review S1a: Stop, pressed while the sample is still being made, wins over the
    job that ends after it; the sample never plays."""
    page = signed_in
    live.install_voice()
    hold = Hold(after=0)  # the sample's first sentence waits
    live.voice.fail_on = hold
    page.goto(live.url + "/voice")
    count_ended_jobs(page)
    page.get_by_role("button", name="Play a sample of Heart").click()
    try:
        assert hold.reached.wait(30)
        page.get_by_role("button", name="Stop the sample of Heart").click()
        expect(page.get_by_role("button", name="Play a sample of Heart")).to_be_visible()
    finally:
        hold.gate.set()
    page.wait_for_function("() => window.ended === 1")
    assert page.locator("#voice-sample").evaluate("a => a.paused && !a.getAttribute('src')")
    page.wait_for_timeout(300)  # a play started by the end would show by now
    assert not playing(page)
    expect(page.locator(".voice-play[aria-label^='Stop']")).to_have_count(0)


def test_a_sample_played_to_its_end_gives_the_button_back(signed_in: Page, live: Live) -> None:
    """#446 review S1c: when the sample ends, its button offers Play again."""
    page = signed_in
    live.install_voice()
    page.goto(live.url + "/voice")
    page.get_by_role("button", name="Play a sample of Heart").click()
    until(lambda: playing(page))
    page.locator("#voice-sample").evaluate("a => { a.playbackRate = 16; }")  # to its end soon
    heart = page.get_by_role("button", name="Play a sample of Heart")
    expect(heart).to_be_visible(timeout=30_000)
    expect(heart).to_have_text("Play a sample")
    expect(page.locator(".voice-play[aria-label^='Stop']")).to_have_count(0)


def test_the_sample_buttons_wait_for_the_script(signed_in: Page, live: Live) -> None:
    page = signed_in
    live.install_voice()
    page.goto(live.url + "/voice")
    release = reload_holding_back_app_js(page, live)
    buttons = page.locator("button.voice-play")
    expect(buttons.first).to_be_attached()
    assert buttons.count() > 1
    for n in range(buttons.count()):
        expect(buttons.nth(n)).to_be_disabled()
    release()
    for n in range(buttons.count()):
        expect(buttons.nth(n)).to_be_enabled()


def test_the_cards_pass_axe_with_and_without_the_voice_and_in_german(
    signed_in: Page, live: Live
) -> None:
    page = signed_in
    page.goto(live.url + "/voice")
    expect(page.locator(".voice-card.missing").first).to_be_visible()
    check_axe(page, "voices, not installed")
    live.install_voice()
    page.goto(f"{live.url}/language?language=de&back=/voice")
    expect(page.get_by_role("button", name="Hörprobe abspielen: Heart")).to_be_enabled()
    check_axe(page, "de: voices")
    page.goto(f"{live.url}/language?language=en&back=/voice")
