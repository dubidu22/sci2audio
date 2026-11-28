"""Prepare with the audiobook job inline (#391, D-694, D-695): the paper header, the side
column, and the job's card while it runs, once paused, failed, cancelled and done. The
browser tests (`tests/browser/test_flow.py`, `test_prepare.py`) drive the same page."""

from __future__ import annotations

import html
import re
import threading
import time
from pathlib import Path
from typing import Any

import pytest
from audio_fakes import FakeVoice
from fastapi.testclient import TestClient
from web_helpers import (  # noqa: F401
    ORIGIN,
    book_folder,
    browser,
    make_config,
    offline,
    paper_bytes,
    upload,
    wait,
)

from sci2audio.app import JobError, audio
from sci2audio.voices import EngineError, ModelNotFoundError
from sci2audio.web import create_app, pages
from sci2audio.web.i18n import strings
from sci2audio.web.jobs import JobKind

pytestmark = pytest.mark.usefixtures("offline")


def server(tmp_path: Path, voice: FakeVoice) -> tuple[Any, TestClient]:
    config = make_config(tmp_path)
    app = create_app(config, voice=lambda models_dir: voice.source())
    client = browser(app, config)
    client.headers["Origin"] = ORIGIN  # as the page's own script sends
    return app, client


def start(client: TestClient, document: str) -> str:
    response = client.post("/api/v1/jobs", json={"kind": "audio", "document": document})
    assert response.status_code == 202, response.text
    return str(response.json()["id"])


def card(page: str) -> str:
    """The card's markup: its section (which holds no other section)."""
    found = re.search(r'<section[^>]* id="making".*?</section>', page, re.S)
    assert found, "no card on the page"
    return html.unescape(found.group(0))


def words(markup: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", markup))


class Held:
    """The fake voice's `fail_on`: speaks `after` sentences, then holds until `gate`."""

    def __init__(self, after: int) -> None:
        self.after = after
        self.calls = 0
        self.reached = threading.Event()
        self.gate = threading.Event()

    def __call__(self, text: str) -> bool:
        self.calls += 1
        if self.calls > self.after:
            self.reached.set()
            assert self.gate.wait(30)
        return False


# --- where a job stood when it ended (D-695) ----------------------------------------------


@pytest.mark.parametrize(
    ("progress", "expected"),
    [
        ({}, ("before", 0)),
        ({"phase": "reading", "chapters": 0}, ("before", 0)),
        ({"phase": "speaking", "chapters": 2, "chapter_number": 0}, ("before", 0)),
        ({"phase": "speaking", "chapters": 2, "chapter_number": 1}, ("chapter", 1)),
        # the last finished chunk ended chapter 1 and its files are in place: the job was
        # in chapter 2
        (
            {
                "phase": "speaking",
                "chapter": 0,
                "chapters": 2,
                "chapter_number": 1,
                "chapter_done": True,
                "playable": [0],
            },
            ("chapter", 2),
        ),
        # ... while they were still written, it was in chapter 1 (#1060)
        (
            {
                "phase": "speaking",
                "chapter": 0,
                "chapters": 2,
                "chapter_number": 1,
                "chapter_done": True,
                "playable": [],
            },
            ("chapter", 1),
        ),
        # ... and when it ended the last chapter, every chapter was spoken, its files written
        # or not
        (
            {"phase": "speaking", "chapter": 1, "chapters": 2, "chapter_number": 2}
            | {"chapter_done": True, "playable": [0]},
            ("writing", 2),
        ),
        (
            {"phase": "speaking", "chapter": 1, "chapters": 2, "chapter_number": 2}
            | {"chapter_done": True, "playable": [0, 1]},
            ("writing", 2),
        ),
        ({"phase": "encoding", "chapters": 2, "chapter_number": 2}, ("writing", 2)),
    ],
)
def test_where_the_job_stood(progress: dict[str, Any], expected: tuple[str, int]) -> None:
    assert pages._stopped_in(progress) == expected


def test_the_segments_mark_the_chapters_done_and_now() -> None:
    assert pages._segments(3, 0) == ["", "", ""]
    assert pages._segments(3, 2) == ["done", "now", ""]
    assert pages._segments(3, 4) == ["done", "done", "done"]


# --- the running card: the whole job and the chapter being spoken (#1054) ----------------

NBSP = "\u00a0"


def speaking(**changes: Any) -> dict[str, Any]:
    """The progress of a 4-chapter job in its second chapter: 4 of its 10 chunks done."""
    progress = {
        "phase": "speaking",
        "chapter": 1,
        "chapters": 4,
        "chapter_number": 2,
        "chapter_done": False,
        "chapter_chunks_done": 4,
        "chapter_chunks_total": 10,
        "chunks_done": 2013,
        "chunks_total": 6707,
        "seconds_left": 1560.0,
        "playable": [0],
    }
    return {**progress, **changes}


def test_the_running_card_shows_the_whole_job_and_the_chapter_being_spoken() -> None:
    lines = pages._running_lines(strings("en"), speaking())
    assert lines["head"] == "Speaking chapter 2 of 4"
    assert lines["left"] == f"30{NBSP}% · about 26 minutes left"
    assert lines["percent"] == 30
    assert lines["chapter_line"] == f"Chapter 2 of 4: 40{NBSP}%"
    assert lines["segments"] == ["done", "now", "", ""]
    assert lines["chapter_part"] == 40
    german = pages._running_lines(strings("de"), speaking())
    assert german["head"] == "Kapitel 2 von 4 wird gesprochen"
    assert german["chapter_line"] == f"Kapitel 2 von 4: 40{NBSP}%"


def test_the_running_card_says_a_chapter_is_saved_until_it_is_playable() -> None:
    """Colin's case (#1054): the last sentence of chapter 1 is spoken and its MP3 is being
    written, which takes minutes for a long chapter. Until it is playable the card says so,
    and does not yet claim chapter 2 is being spoken with nothing to listen to."""
    last = speaking(
        chapter=0,
        chapter_number=1,
        chapter_done=True,
        chapter_chunks_done=2013,
        chapter_chunks_total=2013,
        playable=[],
    )
    saving = pages._running_lines(strings("en"), last)
    assert saving["head"] == "Saving chapter 1 of 4"
    assert saving["chapter_line"] == f"Chapter 1 of 4: 100{NBSP}%"
    assert saving["segments"] == ["now", "", "", ""]
    assert saving["chapter_part"] == 100
    assert pages._running_lines(strings("de"), last)["head"] == "Kapitel 1 von 4 wird gespeichert"
    # its files are in place: the next chapter begins, at nothing of it spoken
    ready = pages._running_lines(strings("en"), {**last, "ready": 0, "playable": [0]})
    assert ready["head"] == "Speaking chapter 2 of 4"
    assert ready["chapter_line"] == f"Chapter 2 of 4: 0{NBSP}%"
    assert ready["segments"] == ["done", "now", "", ""]
    assert ready["chapter_part"] == 0


def test_the_running_card_before_the_first_sentence_and_while_writing_the_book() -> None:
    before = pages._running_lines(strings("en"), {"phase": "loading-voice", "chapters": 4})
    assert before["chapter_line"] == ""
    assert before["segments"] == ["", "", "", ""]
    # the last chapter is written: every chapter is done, no chapter line
    written = speaking(
        chapter=3, chapter_number=4, chapter_done=True, playable=[0, 1, 2, 3], ready=3
    )
    lines = pages._running_lines(strings("en"), written)
    assert lines["chapter_line"] == ""
    assert lines["segments"] == ["done", "done", "done", "done"]


# --- the paused and failed card: a chapter being saved is not done yet (#1060) -----------


def stopped_card(
    tmp_path: Path, progress: dict[str, Any], end: BaseException, language: str = "en"
) -> dict[str, Any]:
    """The card data of an audio job that ended by `end` with `progress` as its last, on a
    document whose speech cache holds its spoken sentences."""
    app, client = server(tmp_path, FakeVoice())
    doc = upload(client, paper_bytes())
    assert wait(client, start(client, doc["id"]))["state"] == "done"
    state = app.state.sci2audio

    def work(job: Any) -> Any:
        job.report(progress)
        raise end

    job = state.board.start(JobKind.AUDIO, doc["id"], None, work, cancellable=True)
    job.join(10)
    found = state.store.get(doc["id"])
    assert found is not None
    assert found.speech_cache_bytes > 0
    return pages.making_card(state, strings(language), job, found)


# chapter 3 of 4 has its last sentence spoken; its files are being written
SAVING_THIRD = speaking(
    chapter=2,
    chapter_number=3,
    chapter_done=True,
    chapter_chunks_done=10,
    chapter_chunks_total=10,
    playable=[0, 1],
)
PAUSED = audio.JobCancelledError("the job was cancelled; finished parts are kept for a rerun")
FAILED = JobError("could not write the audiobook: the disk is full")


def test_a_card_paused_while_a_chapter_is_saved_says_that_chapter(tmp_path: Path) -> None:
    card = stopped_card(tmp_path, SAVING_THIRD, PAUSED)
    assert card["state"] == "cancelled"
    assert card["title"] == "Paused in chapter 3."
    assert card["segments"] == ["done", "done", "now", ""]
    assert card["kept"] == "2013 of 6707 sentences are spoken and kept."
    assert card["resume"]


def test_a_card_paused_while_a_chapter_is_saved_in_german(tmp_path: Path) -> None:
    assert stopped_card(tmp_path, SAVING_THIRD, PAUSED, "de")["title"] == "In Kapitel 3 pausiert."


def test_a_card_failed_while_a_chapter_is_saved_keeps_only_the_playable_ones(
    tmp_path: Path,
) -> None:
    card = stopped_card(tmp_path, SAVING_THIRD, FAILED)
    assert card["state"] == "failed"
    assert card["title"] == "Making the audiobook stopped in chapter 3"
    assert card["segments"] == ["done", "done", "now", ""]
    assert card["kept"] == (
        "Chapters 1 to 2 are finished and kept. Making it again speaks only what is missing."
    )


@pytest.mark.parametrize("end", [PAUSED, FAILED], ids=["paused", "failed"])
def test_a_card_stopped_once_a_chapter_is_playable_is_in_the_next(
    tmp_path: Path, end: BaseException
) -> None:
    card = stopped_card(tmp_path, {**SAVING_THIRD, "ready": 2, "playable": [0, 1, 2]}, end)
    assert card["segments"] == ["done", "done", "done", "now"]
    if end is PAUSED:
        assert card["title"] == "Paused in chapter 4."
    else:
        assert card["title"] == "Making the audiobook stopped in chapter 4"
        assert card["kept"].startswith("Chapters 1 to 3 are finished and kept.")


def test_a_card_stopped_while_the_last_chapter_is_saved_says_writing(tmp_path: Path) -> None:
    last = {**SAVING_THIRD, "chapter": 3, "chapter_number": 4, "playable": [0, 1, 2]}
    (tmp_path / "failed").mkdir()
    (tmp_path / "paused").mkdir()
    failed = stopped_card(tmp_path / "failed", last, FAILED)
    assert failed["title"] == "Making the audiobook stopped while writing the files"
    assert failed["kept"].startswith("Every chapter is spoken and kept.")
    assert failed["segments"] == ["done", "done", "done", "done"]
    paused = stopped_card(tmp_path / "paused", last, PAUSED)
    assert paused["title"] == "Paused."
    assert paused["segments"] == ["done", "done", "done", "now"]


def test_the_card_paused_while_the_first_chapter_is_written(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pause stops the encoder's feed (D-119): the job's last progress is chapter 1's last
    sentence, its files not in place, so the card is paused in chapter 1."""
    gate = threading.Event()
    reached = held_first_chapter(monkeypatch, gate)
    _app, client = server(tmp_path, FakeVoice())
    doc = upload(client, paper_bytes())
    job = start(client, doc["id"])
    try:
        assert reached.wait(30)
        assert client.post(f"/api/v1/jobs/{job}/cancel").status_code == 202
    finally:
        gate.set()
    assert wait(client, job)["state"] == "cancelled"
    paused = card(client.get(f"/jobs/{job}").text)
    assert re.search(r'<h3 id="result"[^>]*>Paused in chapter 1\.</h3>', paused), paused
    assert re.findall(r'class="job-seg ?(\w*)"', paused) == ["now", ""]


# --- the paper header and the side column -------------------------------------------------


def test_prepare_before_any_audiobook(tmp_path: Path) -> None:
    _app, client = server(tmp_path, FakeVoice())
    doc = upload(client, paper_bytes())
    unread = client.get(f"/documents/{doc['id']}").text
    assert '<h1 id="document-title" tabindex="-1">paper.pdf</h1>' in unread  # the file's name
    script = client.post("/api/v1/jobs", json={"kind": "script", "document": doc["id"]})
    assert wait(client, script.json()["id"])["state"] == "done"
    page = client.get(f"/documents/{doc['id']}").text
    head = page.split('<header class="paper-head">')[1].split("</header>")[0]
    # once read: the title the analysis found, and the meta line
    assert '<h1 id="document-title" tabindex="-1"' in head
    assert re.search(r"<span>\d+ pages?</span>", head), head
    assert re.search(r"<span>English, [^<]+</span>", head), head
    assert 'href="/documents/' + doc["id"] + '" id="tab-prepare" aria-current="page"' in head
    # no audiobook yet: Listen is no link, and says so
    assert '<span class="tab-off" id="tab-listen">' in head
    assert "Listen · No audio yet" in head
    assert f'href="/documents/{doc["id"]}/listen"' not in head
    side = words(page.split('id="side-document"')[1].split("</section>")[0])
    assert "File paper.pdf" in side
    assert re.search(r"Sentences \d+", side)
    assert "What stays where" in page
    assert 'id="making"' not in page  # no job: no card


def test_prepare_after_the_audiobook_links_listen_and_says_its_length(tmp_path: Path) -> None:
    _app, client = server(tmp_path, FakeVoice())
    doc = upload(client, paper_bytes())
    job = start(client, doc["id"])
    assert wait(client, job)["state"] == "done"
    page = client.get(f"/documents/{doc['id']}").text
    head = page.split('<header class="paper-head">')[1].split("</header>")[0]
    assert f'<a href="/documents/{doc["id"]}/listen" id="tab-listen">' in head
    assert re.search(r"<span>[^<]* of audio</span>", head)
    # the document's page shows its last audio job of this run as the card
    assert 'data-state="done"' in card(page)
    listen = client.get(f"/documents/{doc['id']}/listen").text
    assert 'id="tab-listen" aria-current="page"' in listen
    assert 'id="tab-prepare"' in listen


def paper_head_of(client: TestClient, doc: str) -> str:
    page = client.get(f"/documents/{doc}").text
    return page.split('<header class="paper-head">')[1].split("</header>")[0]


@pytest.mark.parametrize(
    ("language", "none"), [("en", "Listen · No audio yet"), ("de", "Anhören · Noch kein Audio")]
)
def test_a_finished_audiobook_whose_chapter_files_are_gone_offers_no_listen_link(
    tmp_path: Path, language: str, none: str
) -> None:
    """#1069: the record of a finished book stays when its MP3s are deleted, but the Listen
    page has nothing to play, so the tab reads "No audio yet" and the header says no length;
    in this server run (its job done) and after a restart (no job on the board)."""
    app, client = server(tmp_path, FakeVoice())
    client.cookies.set("sci2audio-language", language)
    doc = upload(client, paper_bytes())["id"]
    assert wait(client, start(client, doc))["state"] == "done"
    assert f'<a href="/documents/{doc}/listen" id="tab-listen">' in paper_head_of(client, doc)
    config = app.state.sci2audio.config
    for mp3 in book_folder(config.output_folder).glob("*.mp3"):
        mp3.unlink()
    restarted = browser(create_app(config, voice=lambda models_dir: FakeVoice().source()), config)
    restarted.cookies.set("sci2audio-language", language)
    for each in (client, restarted):
        head = paper_head_of(each, doc)
        assert '<span class="tab-off" id="tab-listen">' in head
        assert none in head
        assert f'href="/documents/{doc}/listen"' not in head
        meta = head.split("<nav")[0]  # the meta line, above the tabs
        assert not re.search(r"<span>[^<]* (?:of audio|Audio)</span>", meta), meta


# --- the card -----------------------------------------------------------------------------


def test_the_card_while_the_job_runs_and_once_paused(tmp_path: Path) -> None:
    held = Held(after=1)
    voice = FakeVoice(fail_on=held)
    _app, client = server(tmp_path, voice)
    doc = upload(client, paper_bytes())
    job = start(client, doc["id"])
    try:
        assert held.reached.wait(30)
        page = client.get(f"/jobs/{job}").text
        assert '<h1 id="document-title"' in page  # an audio job's page is Prepare (#391)
        running = card(page)
        assert 'data-state="running"' in running
        assert f'data-cancel="/api/v1/jobs/{job}/cancel"' in running
        assert '<strong id="job-chapter">Speaking chapter 1 of 2</strong>' in running
        assert "1 of 4 sentences" in running
        assert re.search(r'<button[^>]*id="job-pause"[^>]*disabled', running)
        # the confirm names what Cancel deletes and how big it is now
        size = client.get(f"/api/v1/documents/{doc['id']}").json()["speech_cache_bytes"]
        assert size > 0
        sized = strings("en").size(size)
        assert f"Its size now: {sized}." in running
        assert "deletes the speech cache" in running
        assert re.search(
            r'<button[^>]*class="danger" id="job-cancel" disabled>Cancel and delete', running
        )
        assert client.post(f"/api/v1/jobs/{job}/cancel").status_code == 202
    finally:
        held.gate.set()
    assert wait(client, job)["state"] == "cancelled"
    paused = card(client.get(f"/jobs/{job}").text)
    assert 'data-state="cancelled"' in paused
    assert re.search(r'<h3 id="result"[^>]*>Paused in chapter [12]\.</h3>', paused), paused
    assert re.search(r"[12] of 4 sentences are spoken and kept\.", paused)
    assert "Resume" in paused
    assert re.search(r"Free the speech cache \([^)]+\)", paused)


def test_the_card_once_paused_and_the_cache_freed_says_cancelled(tmp_path: Path) -> None:
    held = Held(after=1)
    _app, client = server(tmp_path, FakeVoice(fail_on=held))
    doc = upload(client, paper_bytes())
    job = start(client, doc["id"])
    assert held.reached.wait(30)
    client.post(f"/api/v1/jobs/{job}/cancel")
    held.gate.set()
    assert wait(client, job)["state"] == "cancelled"
    assert client.delete(f"/api/v1/documents/{doc['id']}/chunks").status_code == 204
    cancelled = card(client.get(f"/jobs/{job}").text)
    assert "Cancelled. The speech cache is empty." in cancelled
    assert "Resume" not in cancelled
    assert "Make it again" in cancelled
    assert "Free the speech cache" not in cancelled


def test_the_card_of_a_job_that_failed_before_the_voice_began(tmp_path: Path) -> None:
    voice = FakeVoice(fail_to_make=EngineError("no engine"))
    _app, client = server(tmp_path, voice)
    doc = upload(client, paper_bytes())
    job = start(client, doc["id"])
    assert wait(client, job)["state"] == "failed"
    failed = words(card(client.get(f"/jobs/{job}").text))
    assert "Making the audiobook stopped before the voice began" in failed
    assert "Nothing is spoken yet." in failed
    assert "Make it again" in failed


def test_the_card_of_a_job_that_failed_in_its_second_chapter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The kept wording counts the chapters before the one it stopped in (D-695)."""
    voice = FakeVoice()
    app, client = server(tmp_path, voice)
    doc = upload(client, paper_bytes())

    def stop_in_chapter_two(text: str) -> bool:
        job = app.state.sci2audio.board.current
        progress = job.snapshot()["progress"] or {}
        if progress.get("chapter_number") == 1 and progress.get("chapter_done"):
            raise ModelNotFoundError("the voice's files went away")
        return False

    voice.fail_on = stop_in_chapter_two
    job = start(client, doc["id"])
    assert wait(client, job)["state"] == "failed"
    failed = words(card(client.get(f"/jobs/{job}").text))
    assert "Making the audiobook stopped in chapter 2" in failed
    assert "Chapter 1 is finished and kept. Making it again speaks only what is missing." in failed


def test_the_card_of_a_job_that_failed_in_its_first_chapter(tmp_path: Path) -> None:
    """In the first chapter no chapter is finished: what is kept is the sentences."""
    voice = FakeVoice()
    app, client = server(tmp_path, voice)
    doc = upload(client, paper_bytes())

    def stop_in_chapter_one(text: str) -> bool:
        job = app.state.sci2audio.board.current
        progress = job.snapshot()["progress"] or {}
        if progress.get("chapter_number") == 1 and not progress.get("chapter_done"):
            raise ModelNotFoundError("the voice's files went away")
        return False

    voice.fail_on = stop_in_chapter_one
    job = start(client, doc["id"])
    assert wait(client, job)["state"] == "failed"
    failed = words(card(client.get(f"/jobs/{job}").text))
    assert "Making the audiobook stopped in chapter 1" in failed
    assert "The sentences spoken so far are kept. Making it again speaks only what is" in failed


def test_the_card_of_a_job_paused_before_its_first_sentence(tmp_path: Path) -> None:
    """Paused while the voice loads: nothing was spoken and nothing freed, so the card says
    paused, not cancelled, and offers Resume (#433)."""
    voice = FakeVoice()
    gate, loading = threading.Event(), threading.Event()
    make = voice.make

    def held_make() -> Any:
        loading.set()
        assert gate.wait(30)
        return make()

    voice.make = held_make  # type: ignore[method-assign]
    _app, client = server(tmp_path, voice)
    doc = upload(client, paper_bytes())
    job = start(client, doc["id"])
    assert loading.wait(30)
    assert client.post(f"/api/v1/jobs/{job}/cancel").status_code == 202
    gate.set()
    assert wait(client, job)["state"] == "cancelled"
    assert client.get(f"/api/v1/documents/{doc['id']}").json()["speech_cache_bytes"] == 0
    paused = card(client.get(f"/jobs/{job}").text)
    assert re.search(r'<h3 id="result"[^>]*>Paused\.</h3>', paused), paused
    assert '<p id="job-kept">Nothing is spoken yet.</p>' in paused
    assert "Cancelled" not in paused
    assert "Resume" in paused
    # Resume restarts with this run's settings, and the card says so (#433)
    assert "This uses the settings this run was started with" in paused


def held_encoding(monkeypatch: pytest.MonkeyPatch, gate: threading.Event | None) -> None:
    """Writing the files waits for `gate`, or fails at once when there is none."""
    encode = audio._Chapters.finish  # the book's own files, after every chapter's (#723)

    def writing(*args: Any, **kwargs: Any) -> Any:
        if gate is None:
            raise JobError("could not write the audiobook: the disk is full")
        assert gate.wait(30)
        return encode(*args, **kwargs)

    monkeypatch.setattr(audio._Chapters, "finish", writing)


def test_the_card_of_a_job_that_failed_while_writing_the_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every chapter was spoken: the card says so, and every segment is done (#433)."""
    held_encoding(monkeypatch, None)
    _app, client = server(tmp_path, FakeVoice())
    doc = upload(client, paper_bytes())
    job = start(client, doc["id"])
    assert wait(client, job)["state"] == "failed"
    failed = card(client.get(f"/jobs/{job}").text)
    assert "Making the audiobook stopped while writing the files" in failed
    assert "Every chapter is spoken and kept. Making it again only writes the files." in failed
    assert failed.count('class="job-seg done"') == 2
    assert 'class="job-seg"' not in failed
    assert 'class="job-seg now"' not in failed


def test_the_running_card_while_the_files_are_written(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gate = threading.Event()
    held_encoding(monkeypatch, gate)
    app, client = server(tmp_path, FakeVoice())
    doc = upload(client, paper_bytes())
    job = start(client, doc["id"])
    try:
        board = app.state.sci2audio.board
        deadline = time.monotonic() + 30
        while (board.current.snapshot()["progress"] or {}).get("phase") != "encoding":
            # clock-bound: the wait loop's way out after 30 s; what it waits for is far quicker
            assert time.monotonic() < deadline, "the job never began writing"
            time.sleep(0.02)
        running = card(client.get(f"/jobs/{job}").text)
        assert 'data-state="running"' in running
        assert running.count('class="job-seg done"') == 2
        assert 'class="job-seg"' not in running
        assert 'class="job-seg now"' not in running
    finally:
        gate.set()
    assert wait(client, job)["state"] == "done"


def held_first_chapter(monkeypatch: pytest.MonkeyPatch, gate: threading.Event) -> threading.Event:
    """Writing the first chapter's files waits for `gate`, as a long chapter's MP3 takes
    minutes (#1054); the event returned is set once the job waits there."""
    write = audio._Chapters.done
    reached = threading.Event()

    def writing(chapters: Any, *args: Any, **kwargs: Any) -> Any:
        if not chapters.added:
            reached.set()
            assert gate.wait(30)
        return write(chapters, *args, **kwargs)

    monkeypatch.setattr(audio._Chapters, "done", writing)
    return reached


def tab(page: str) -> str:
    head = page.split('<header class="paper-head">')[1].split("</header>")[0]
    found = re.search(r'<(a|span)[^>]*id="tab-listen".*?</\1>', head, re.S)
    assert found, head
    return found.group(0)


def test_the_job_page_while_the_first_chapter_is_saved_and_once_it_is_playable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Colin's path (#1054): the job page `/jobs/<id>` while chapter 1's files are written
    says so, offers nothing to listen to yet and keeps "No audio yet"; once chapter 1 is
    playable and chapter 2 is spoken, it offers Start listening and the Listen tab is a link,
    and the chapter line names chapter 2. The job page and Prepare draw the same."""
    gate = threading.Event()
    reached = held_first_chapter(monkeypatch, gate)
    held = Held(after=3)  # chapter 1's title and sentence, chapter 2's title
    _app, client = server(tmp_path, FakeVoice(fail_on=held))
    doc = upload(client, paper_bytes())
    job = start(client, doc["id"])
    try:
        assert reached.wait(30)
        for path in (f"/jobs/{job}", f"/documents/{doc['id']}"):
            page = client.get(path).text
            saving = card(page)
            assert '<strong id="job-chapter">Saving chapter 1 of 2</strong>' in saving, path
            assert re.search(r'id="job-chapter-progress"[^>]*>Chapter 1 of 2: 100\s%<', saving)
            assert 'id="start-listening-box" hidden>' in saving
            assert tab(page).startswith('<span class="tab-off" id="tab-listen">')
            assert "Listen · No audio yet" in tab(page)
        gate.set()
        assert held.reached.wait(30)
        listen = f'href="/documents/{doc["id"]}/listen"'
        for path in (f"/jobs/{job}", f"/documents/{doc['id']}"):
            page = client.get(path).text
            spoken = card(page)
            assert '<strong id="job-chapter">Speaking chapter 2 of 2</strong>' in spoken, path
            assert re.search(r'id="job-chapter-progress"[^>]*>Chapter 2 of 2: \d+\s%<', spoken)
            assert 'id="start-listening-box">' in spoken
            assert tab(page) == (
                f'<a {listen} id="tab-listen"><svg class="i s" aria-hidden="true" '
                'focusable="false"><use href="#i-speaker"></use></svg><span>Listen</span></a>'
            )
            # the segments: chapter 1 full, chapter 2 filled as far as it is spoken
            assert re.search(r'<progress class="job-seg done" max="100" value="100">', spoken)
            assert re.search(r'<progress class="job-seg now" max="100" value="\d+">', spoken)
    finally:
        gate.set()
        held.gate.set()
    assert wait(client, job)["state"] == "done"


def test_the_card_once_done(tmp_path: Path) -> None:
    _app, client = server(tmp_path, FakeVoice())
    doc = upload(client, paper_bytes())
    job = start(client, doc["id"])
    assert wait(client, job)["state"] == "done"
    done = card(client.get(f"/jobs/{job}").text)
    assert re.search(r'<h3 id="result"[^>]*>Your audiobook is ready</h3>', done)
    assert f'href="/documents/{doc["id"]}/listen"' in done
    # the chapters' files; the whole book is built on request from Listen (#725)
    assert re.search(r"paper - 01 [^<]*\.mp3", done)
    assert ".m4b" not in done
    assert 'id="cache-free"' in done


def test_other_jobs_keep_their_own_page(tmp_path: Path) -> None:
    app, client = server(tmp_path, FakeVoice())
    gate = threading.Event()
    job = app.state.sci2audio.board.start(
        JobKind.VOICES, None, None, lambda job: gate.wait(30) and [], cancellable=False
    )
    try:
        page = client.get(f"/jobs/{job.id}").text
        assert 'id="making"' not in page
        assert 'id="job"' in page
        assert "paper-head" not in page
    finally:
        gate.set()
        job.join(10)


# --- Resume keeps "replace"; the existing-files card; freeing asks first (D-733) -------------


def test_the_paused_card_carries_the_jobs_own_replace(tmp_path: Path) -> None:
    held = Held(after=1)
    voice = FakeVoice()
    _app, client = server(tmp_path, voice)
    doc = upload(client, paper_bytes())
    assert wait(client, start(client, doc["id"]))["state"] == "done"
    assert client.delete(f"/api/v1/documents/{doc['id']}/chunks").status_code == 204
    voice.fail_on = held
    response = client.post(
        "/api/v1/jobs", json={"kind": "audio", "document": doc["id"], "overwrite": True}
    )
    job = response.json()["id"]
    assert held.reached.wait(30)
    client.post(f"/api/v1/jobs/{job}/cancel")
    held.gate.set()
    assert wait(client, job)["state"] == "cancelled"
    paused = card(client.get(f"/jobs/{job}").text)
    assert 'data-overwrite="true"' in paused
    assert "Resume" in paused


def test_a_first_builds_card_does_not_say_replace(tmp_path: Path) -> None:
    _app, client = server(tmp_path, FakeVoice())
    doc = upload(client, paper_bytes())
    job = start(client, doc["id"])
    assert wait(client, job)["state"] == "done"
    assert 'data-overwrite="false"' in card(client.get(f"/jobs/{job}").text)


def test_the_existing_files_card_says_the_spoken_sentences_are_kept(tmp_path: Path) -> None:
    """Replacing reuses the speech cache: the card says so and offers no cache button, the
    one button that would lose the spoken sentences."""
    _app, client = server(tmp_path, FakeVoice())
    doc = upload(client, paper_bytes())
    assert wait(client, start(client, doc["id"]))["state"] == "done"
    assert client.get(f"/api/v1/documents/{doc['id']}").json()["speech_cache_bytes"] > 0
    job = start(client, doc["id"])
    assert wait(client, job)["error"]["error"] == "output-exists"
    exists = card(client.get(f"/jobs/{job}").text)
    assert "The audiobook files exist already." in exists
    assert (
        '<p id="job-kept">The sentences spoken so far are kept. '
        "Replacing speaks only what is missing.</p>" in exists
    )
    assert 'id="job-replace"' in exists
    assert "cache-free" not in exists
    assert "Free the speech cache" not in exists


def test_the_existing_files_card_with_an_empty_cache_says_nothing_is_kept(
    tmp_path: Path,
) -> None:
    _app, client = server(tmp_path, FakeVoice())
    doc = upload(client, paper_bytes())
    assert wait(client, start(client, doc["id"]))["state"] == "done"
    assert client.delete(f"/api/v1/documents/{doc['id']}/chunks").status_code == 204
    job = start(client, doc["id"])
    assert wait(client, job)["error"]["error"] == "output-exists"
    exists = card(client.get(f"/jobs/{job}").text)
    assert "The audiobook files exist already." in exists
    assert "job-kept" not in exists
    assert "are kept" not in exists
    assert "cache-free" not in exists


def test_the_cache_button_is_inside_a_confirm(tmp_path: Path) -> None:
    """The DELETE button sits only inside the confirm box that names what goes; the box's
    opener deletes nothing (app.js wires only #cache-free)."""
    _app, client = server(tmp_path, FakeVoice())
    doc = upload(client, paper_bytes())
    job = start(client, doc["id"])
    assert wait(client, job)["state"] == "done"
    done = card(client.get(f"/jobs/{job}").text)
    box = re.search(r'<details class="confirm" id="free-box">.*?</details>', done, re.S)
    assert box, done
    inside = box.group(0)
    assert re.search(r'<summary class="btn" id="cache-free-open">Free the speech cache \(', inside)
    assert "This deletes every sentence spoken for this document (" in inside
    assert re.search(r'<button[^>]*class="danger" id="cache-free" disabled>Delete the', inside)
    assert done.count('id="cache-free"') == 1


def test_the_german_strings_of_the_confirm_and_the_kept_line() -> None:
    de = strings("de")
    assert de("making.free_now") == "Sprachzwischenspeicher löschen"
    assert de("making.kept_replace").startswith("Die bisher gesprochenen Sätze bleiben erhalten.")
    assert "{size}" not in de("making.free_goes", size="2 MB")
