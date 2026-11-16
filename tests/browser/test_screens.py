"""Screenshots of every page for a review (#386, D-627): run by the label-triggered workflow
`.github/workflows/ui-screens.yml`, skipped everywhere else.

Set `SCI2AUDIO_SCREENS` to a folder to run it: every page state at 1440 x 900 and 1280 x 800,
in light English, dark English and light German, as `<state>-<width>-<variant>.png`. The
pages show corpus documents only (`tests/corpus/LICENSES.md`), the fake voice and the fake
download of conftest, so nothing leaves the test server. The images are for people to
compare with the design's `prototype/app/screens/`; they are not golden files and nothing
compares them pixel by pixel (no two systems draw text alike).
"""

from __future__ import annotations

import os
import re
from collections.abc import Callable
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect
from test_flow import gated

from conftest import Live, settled
from sci2audio.voices import EngineError
from sci2audio.web.jobs import JobKind

FOLDER = os.environ.get("SCI2AUDIO_SCREENS", "")
CORPUS = Path(__file__).resolve().parents[1] / "corpus"
PAPER = CORPUS / "papers" / "joss2021-waskom-seaborn.pdf"  # CC BY 4.0
NOTE = CORPUS / "markdown" / "sci2audio-sample-note.md"  # written for the corpus, CC0
SIZES = {1440: 900, 1280: 800}
VARIANTS = {"light": ("en", "light"), "dark": ("en", "dark"), "de": ("de", "light")}

pytestmark = pytest.mark.skipif(not FOLDER, reason="screenshots only on the ui:screens label")


def shoot(page: Page, live: Live, state: str, path: str, out: Path) -> None:
    """One page state in every size and variant."""
    for variant, (language, scheme) in VARIANTS.items():
        page.goto(f"{live.url}/language?language={language}&back={path}")
        page.emulate_media(color_scheme=scheme)  # type: ignore[arg-type]
        for width, height in SIZES.items():
            page.set_viewport_size({"width": width, "height": height})
            page.wait_for_load_state("load")
            page.evaluate("() => document.fonts.ready")
            page.screenshot(
                path=out / f"{state}-{width}-{variant}.png", animations="disabled", caret="hide"
            )
    page.emulate_media(color_scheme="light")
    page.goto(f"{live.url}/language?language=en&back=/")


def open_file(page: Page, live: Live, source: Path) -> str:
    page.goto(live.url + "/")
    page.set_input_files("#file", str(source))
    page.get_by_role("button", name="Open and analyse").click()
    page.wait_for_url(re.compile(r"/documents/[0-9a-f]{16}"))
    expect(page.locator("#summary")).to_be_visible(timeout=60_000)
    settled(page)
    return page.url.rsplit("/", 1)[1].split("#")[0]


def test_every_page_as_screenshots(signed_in: Page, live: Live) -> None:
    page = signed_in
    out = Path(FOLDER)
    out.mkdir(parents=True, exist_ok=True)
    take: Callable[[str, str], None] = lambda state, path: shoot(page, live, state, path, out)  # noqa: E731

    take("library-firstrun", "/")
    take("voices-missing", "/voice")
    take("settings", "/settings")
    take("privacy", "/privacy")
    take("not-found", "/jobs/nothing")

    live.install_voice()
    take("library-empty", "/")  # no document, the voice installed: the specimen (#389)
    paper = open_file(page, live, PAPER)
    open_file(page, live, NOTE)
    take("library", "/")
    take("document", f"/documents/{paper}")
    take("voices", "/voice")

    job, gate = gated(live.state, JobKind.VOICES, None)  # a running job, on its page and the rail
    try:
        take("job-running", f"/jobs/{job.id}")
        take("library-job-running", "/")
    finally:
        gate.set()
        job.join(10)

    live.voice.fail_to_make = EngineError("the model file is damaged")
    page.goto(f"{live.url}/documents/{paper}")
    page.get_by_role("button", name="Make the audiobook").click()
    page.wait_for_url(re.compile(r"/jobs/[0-9a-f]{16}-audio-\d+"))
    expect(page.locator("#result")).to_contain_text("The job failed")
    take("job-failed", page.url.removeprefix(live.url))

    live.voice.fail_to_make = None
    page.goto(f"{live.url}/documents/{paper}")
    page.get_by_role("button", name="Make the audiobook").click()
    page.wait_for_url(re.compile(r"/jobs/[0-9a-f]{16}-audio-\d+"))
    expect(page.locator("#result")).to_have_text("Your audiobook is ready", timeout=120_000)
    take("job-done", page.url.removeprefix(live.url))
    take("listen", f"/documents/{paper}/listen")

    shots = sorted(out.glob("*.png"))
    assert len(shots) == 14 * len(SIZES) * len(VARIANTS)
