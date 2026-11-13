"""Each PDF extraction refuses (#5, D-393 to D-398) reaches the web app with its message: the
job fails as "job-failed" with the app's words, and the document page says so in English and
in German, the app's words marked as English (D-291)."""

from __future__ import annotations

import html
import re
from pathlib import Path

import pytest
from broken_pdfs import REFUSED, Refused
from pdf_maker import dense_pdf
from web_helpers import ORIGIN, app_and_config, browser, offline, upload, wait  # noqa: F401

from sci2audio.extraction import pdf
from sci2audio.web.i18n import COOKIE, load_table

pytestmark = [pytest.mark.usefixtures("offline"), pytest.mark.timeout(120)]

# The total-character limit, shrunk so a small file reaches it (its value is pinned in
# test_extraction_pdf_broken.py)
TOO_MANY_IN_ALL = Refused(
    "too-many-characters-in-all",
    lambda: dense_pdf(3, 1_200),
    "{name}: the PDF is too large or damaged (more than 2,500 characters)",
)
CASES = (*REFUSED, TOO_MANY_IN_ALL)


def shown_error(page: str) -> str:
    found = re.search(r'<p class="error" id="analysis-error">(.*?)</p>', page, re.S)
    assert found is not None, "no analysis error on the page"
    return html.unescape(found[1])


@pytest.mark.parametrize("case", CASES, ids=[case.id for case in CASES])
def test_a_refused_pdf_is_explained_in_english_and_german(
    case: Refused, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(pdf, "MAX_CHARS", 2_500)
    app, config = app_and_config(tmp_path)
    client = browser(app, config)
    client.headers["Origin"] = ORIGIN
    doc = upload(client, case.make(), "paper.pdf")
    job = client.post(
        "/api/v1/jobs", json={"kind": "script", "document": doc["id"], "settings": {}}
    ).json()
    ended = wait(client, job["id"])
    words = case.expected("paper.pdf")
    assert ended["state"] == "failed"
    assert ended["error"] == {"error": "job-failed", "message": words}

    shown: dict[str, str] = {}
    for language in ("en", "de"):
        table = load_table(language)
        client.cookies.set(COOKIE, language)
        shown[language] = shown_error(client.get(f"/documents/{doc['id']}").text)
        reason = table["document.analysis_failed"].format(reason=table["error.job-failed"])
        details = f'{table["common.details"]} <span lang="en">{words}</span>'
        assert shown[language] == f"{reason} {details}"
    assert shown["en"].startswith("The analysis failed: The job could not finish.")
    assert shown["de"].startswith(
        "Die Analyse ist fehlgeschlagen: Der Auftrag konnte nicht abgeschlossen werden."
    )
