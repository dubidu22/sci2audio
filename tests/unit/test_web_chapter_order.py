"""The chapter order on the document page and in web jobs (#119)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
from test_web_player import server
from web_helpers import events, paper_bytes, upload
from web_helpers import offline as offline

from sci2audio.web.pages import _chapter_order

pytestmark = pytest.mark.usefixtures("offline")


def chapters(*chosen: int) -> list[dict[str, Any]]:
    return [{"index": n, "title": f"C{n}", "selected": n in chosen} for n in range(4)]


def titles(listed: list[dict[str, Any]]) -> list[str]:
    return [c["title"] for c in listed]


def test_printed_order_lists_every_chapter_as_printed() -> None:
    for recorded in (None, [0, 2], [2, 0, 9], "x", [True]):
        listed, chosen = _chapter_order(chapters(0, 2), recorded)
        if recorded == [2, 0, 9]:
            assert titles(listed) == ["C2", "C0", "C1", "C3"]
            assert chosen == [2, 0]
            continue
        assert titles(listed) == ["C0", "C1", "C2", "C3"], recorded
        assert chosen == [0, 2], recorded


def test_a_chosen_order_lists_the_chosen_first_then_the_rest_as_printed() -> None:
    listed, chosen = _chapter_order(chapters(1, 3), [3, 1])
    assert titles(listed) == ["C3", "C1", "C0", "C2"]
    assert chosen == [3, 1]


def test_an_audio_job_keeps_the_order_given(tmp_path: Path) -> None:
    client, _config = server(tmp_path)
    doc = upload(client, paper_bytes(), "paper.pdf")["id"]
    body = {"kind": "script", "document": doc, "settings": {"chapters": [1, 0]}}
    job = client.post("/api/v1/jobs", json=body).json()
    final = json.loads(events(client, job["id"])[-1][1])
    assert final["state"] == "done", final
    report = client.get(f"/api/v1/documents/{doc}/report").json()
    assert report["settings"]["chapters"] == [1, 0]
    page = client.get(f"/documents/{doc}").text
    assert page.index('id="chapter-1"') < page.index('id="chapter-0"')
    assert '"chapters": [1, 0]' in page.replace("&#34;", '"').replace("&quot;", '"')
    audio = {"kind": "audio", "document": doc, "settings": {"chapters": [1, 0]}}
    made = client.post("/api/v1/jobs", json=audio).json()
    done = json.loads(events(client, made["id"])[-1][1])
    assert done["state"] == "done", done
    assert done["settings"]["chapters"] == [1, 0]
    listen = client.get(f"/documents/{doc}/listen").text
    outline = re.findall(r'<span class="ot">([^<]*)</span>', listen)
    assert outline == ["Methods", "Introduction"]


def test_a_report_from_before_the_publisher_flag_still_reads() -> None:
    """#376: a report JSON written before the flag existed has no `publisher` key."""
    from sci2audio.web.models import ChapterOut

    old = {"index": 0, "title": "1 Intro", "blocks": [0, 3], "first_page": 1}
    old |= {"references": False, "selected": True, "utterances": 3}
    assert ChapterOut.model_validate(old).publisher is False
