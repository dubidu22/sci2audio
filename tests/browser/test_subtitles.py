"""Subtitles in the browser (#214, D-606): the checkbox on the document page, remembered with
the settings, and the WebVTT file read by Chromium's own WebVTT parser as a `<track>`, cue
for cue on the read-along's times."""

from __future__ import annotations

import itertools
import json
import re
from pathlib import Path

from playwright.sync_api import Page, expect
from test_player import built_m4b
from web_helpers import paper_bytes

from conftest import Live, check_axe, settled

READ_TRACK = """async (url) => {
  const video = document.createElement("video");
  const track = document.createElement("track");
  track.kind = "subtitles";
  track.src = url;
  track.default = true;
  video.append(track);
  document.body.append(video);
  track.track.mode = "hidden";
  await new Promise((done, fail) => {
    if (track.readyState === 2) done();
    track.addEventListener("load", done);
    track.addEventListener("error", () => fail(new Error("the track did not load")));
  });
  const cues = [...track.track.cues].map((cue) => [cue.startTime, cue.endTime, cue.text]);
  video.remove();
  return cues;
}"""


def test_subtitles_are_chosen_on_the_page_and_chromium_reads_them(
    signed_in: Page, live: Live, tmp_path: Path
) -> None:
    page = signed_in
    live.install_voice()
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(paper_bytes())
    page.set_input_files("#file", files=[str(pdf)])
    page.get_by_role("button", name="Open and analyse").click()
    page.wait_for_url(re.compile(r"/documents/[0-9a-f]{16}"))
    expect(page.locator("#summary")).to_be_visible()
    settled(page)  # axe below must not run while the page reloads after its analysis (#365)

    box = page.get_by_role("checkbox", name="Also write subtitles (SRT and WebVTT)")
    expect(box).not_to_be_checked()  # off by default (D-606)
    expect(box).to_have_accessible_description(re.compile("next to each chapter MP3"))
    check_axe(page, "document page with the subtitles choice")
    box.check()
    page.get_by_role("button", name="Make the audiobook").click()
    expect(page.locator("#result")).to_have_text("Your audiobook is ready")
    saved = json.loads(live.config.config_file.read_text(encoding="utf-8"))
    assert saved["subtitles"] is True  # remembered for the next document

    job = page.url.rsplit("/", 1)[1].split("#")[0]
    files = page.evaluate("(url) => fetch(url).then((r) => r.json())", f"/api/v1/jobs/{job}")
    names = [f["name"] for f in files["files"]]
    vtts = [name for name in names if name.endswith(".vtt")]
    # one pair a chapter; the book's own pair comes with its M4B, built on request (#725)
    assert len(vtts) == len([n for n in names if n.endswith(".mp3")])
    assert len([n for n in names if n.endswith(".srt")]) == len(vtts)
    (readalong,) = [name for name in names if name.endswith(".readalong.json")]
    times = page.evaluate(
        "(url) => fetch(url).then((r) => r.json())", f"/api/v1/jobs/{job}/files/{readalong}"
    )
    document = job.split("-")[0]
    folder, m4b = built_m4b(live, document)
    book = folder / m4b.removesuffix(".m4b")
    assert book.with_suffix(".srt").is_file()
    # the book's subtitles are not served (they are saved beside the M4B): Chromium reads
    # them from an address of the test server's
    page.route(
        f"{live.url}/book.vtt",
        lambda route: route.fulfill(
            body=book.with_suffix(".vtt").read_bytes(), content_type="text/vtt"
        ),
    )
    cues = page.evaluate(READ_TRACK, "/book.vtt")
    assert cues, "Chromium read no cue"
    starts = {round(c[0] * 1000) for c in cues}
    ends = {round(c[1] * 1000) for c in cues}
    for chunk in times["chunks"]:  # every chunk starts and ends a cue, at its own times
        assert round(chunk["start"] * 1000) in starts
        assert round(chunk["end"] * 1000) in ends
    assert all(a[1] <= b[0] for a, b in itertools.pairwise(cues))
    assert "We measured it twice." in " ".join(c[2].replace("\n", " ") for c in cues)

    # the next document starts with the remembered choice
    page.goto(live.url + "/")
    page.set_input_files("#file", files=[str(pdf)])
    page.get_by_role("button", name="Open and analyse").click()
    page.wait_for_url(re.compile(r"/documents/[0-9a-f]{16}"))
    expect(
        page.get_by_role("checkbox", name="Also write subtitles (SRT and WebVTT)")
    ).to_be_checked()
