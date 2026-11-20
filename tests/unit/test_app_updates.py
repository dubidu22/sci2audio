"""The opt-in update check (#217, AQ-07, D-837): off by default, at most one request a day
to the release source once the person turns it on, nothing sent but the request itself,
and no failure ever reaches the server. No test here touches the network: the request is
a fake, or the real one with its transport replaced, always under `no_network()`."""

from __future__ import annotations

import contextlib
import errno
import json
import logging
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
import requests
from hypothesis import given
from hypothesis import strategies as st

from sci2audio.app import updates
from sci2audio.app.files import partial_path
from sci2audio.app.updates import (
    RELEASES_URL,
    Outcome,
    UpdateCheck,
    UpdateCheckFailed,
    fetch_latest_release,
    latest_version,
    load_update_state,
    release_page,
)
from sci2audio.testing import no_network

START = datetime(2026, 11, 20, 9, 0, tzinfo=UTC)
LOGGER = "sci2audio.app.updates"


class Clock:
    def __init__(self) -> None:
        self.now = START

    def __call__(self) -> datetime:
        return self.now


class FakeRelease:
    """The release source: answers with `tag`, or raises `error`; `gate` holds it back."""

    def __init__(self, tag: str = "v1.5.0", error: BaseException | None = None) -> None:
        self.tag = tag
        self.error = error
        self.calls = 0
        self.gate: threading.Event | None = None
        self.entered = threading.Event()

    def __call__(self) -> bytes:
        self.calls += 1
        self.entered.set()
        if self.gate is not None:
            assert self.gate.wait(10)
        if self.error is not None:
            raise self.error
        # a foreign link in the answer must never be what the interface shows
        return json.dumps({"tag_name": self.tag, "html_url": "https://evil.example/x"}).encode()


@pytest.fixture
def file(tmp_path: Path) -> Path:
    return tmp_path / "config" / "update-check.json"


def checker(file: Path, fetch: Any, clock: Clock | None = None, current: str = "1.4.0") -> Any:
    return UpdateCheck(file, fetch=fetch, now=clock or Clock(), current=current)


def turned_on(file: Path, fetch: Any, clock: Clock) -> UpdateCheck:
    check = checker(file, fetch, clock)
    check.set_enabled(True)
    check.join(10)
    return check


# --- off by default ----------------------------------------------------------------------


def test_off_by_default_makes_no_request(file: Path) -> None:
    fetch = FakeRelease()
    with no_network() as attempts:
        check = checker(file, fetch)
        assert check.state().enabled is False
        assert check.poll().enabled is False
        assert check.check().enabled is False
        check.join(10)
    assert fetch.calls == 0
    assert attempts == []
    assert not file.exists()  # nothing is written until the person chooses


@pytest.mark.parametrize(
    "content",
    [
        b"",
        b"{",
        b"[]",
        b"\xff\xfe",
        b'{"version": 2, "enabled": true}',
        b'{"version": true, "enabled": true}',  # true is not version 1
        b'{"version": 1, "enabled": "yes"}',
        b'{"version": 1, "enabled": 1}',
        b'{"enabled": true}',
    ],
)
def test_a_damaged_file_means_off(file: Path, content: bytes) -> None:
    file.parent.mkdir(parents=True)
    file.write_bytes(content)
    fetch = FakeRelease()
    check = checker(file, fetch)
    assert check.state().enabled is False
    check.poll()
    check.join(10)
    assert fetch.calls == 0


def test_a_folder_in_place_of_the_file_means_off(file: Path) -> None:
    file.mkdir(parents=True)
    fetch = FakeRelease()
    check = checker(file, fetch)
    assert check.state().enabled is False
    check.poll()
    check.join(10)
    assert fetch.calls == 0


# --- turned on: at most once a day -------------------------------------------------------


def test_turning_it_on_checks_once_and_is_remembered(file: Path) -> None:
    fetch, clock = FakeRelease(), Clock()
    check = turned_on(file, fetch, clock)
    assert fetch.calls == 1
    state = check.state()
    assert (state.enabled, state.checked_at, state.outcome, state.latest) == (
        True,
        START,
        Outcome.NEWER,
        "1.5.0",
    )
    again = load_update_state(file)  # the next start reads the same
    assert again == state
    assert json.loads(file.read_text(encoding="utf-8")) == {
        "version": 1,
        "enabled": True,
        "checked_at": "2026-11-20T09:00:00+00:00",
        "outcome": "newer",
        "latest": "1.5.0",
    }


def test_at_most_one_request_a_day(file: Path) -> None:
    fetch, clock = FakeRelease(), Clock()
    check = turned_on(file, fetch, clock)
    for hours in (0, 1, 23, 23.99):
        clock.now = START + timedelta(hours=hours)
        check.poll()
        check.join(10)
    assert fetch.calls == 1
    clock.now = START + timedelta(hours=24)
    check.poll()
    check.join(10)
    assert fetch.calls == 2
    # a new server run within the day does not check again either
    later = checker(file, fetch, clock)
    later.poll()
    later.join(10)
    assert fetch.calls == 2


def test_turning_it_on_again_within_the_day_does_not_check_again(file: Path) -> None:
    fetch, clock = FakeRelease(), Clock()
    check = turned_on(file, fetch, clock)
    check.set_enabled(False)
    check.set_enabled(True)
    check.join(10)
    assert fetch.calls == 1


def test_a_clock_set_back_does_not_stop_the_checks_for_good(file: Path) -> None:
    fetch, clock = FakeRelease(), Clock()
    check = turned_on(file, fetch, clock)
    clock.now = START - timedelta(days=30)
    check.poll()
    check.join(10)
    assert fetch.calls == 2


def test_turning_it_off_stops_it(file: Path) -> None:
    fetch, clock = FakeRelease(), Clock()
    check = turned_on(file, fetch, clock)
    check.set_enabled(False)
    clock.now = START + timedelta(days=3)
    with no_network() as attempts:
        check.poll()
        check.join(10)
    assert fetch.calls == 1
    assert attempts == []
    assert check.state().enabled is False


def test_two_polls_at_once_make_one_request(file: Path) -> None:
    fetch, clock = FakeRelease(), Clock()
    file.parent.mkdir(parents=True)
    file.write_text('{"version": 1, "enabled": true}', encoding="utf-8")
    fetch.gate = threading.Event()
    check = checker(file, fetch, clock)
    check.poll()
    assert fetch.entered.wait(10)
    for _ in range(5):
        check.poll()
    fetch.gate.set()
    check.join(10)
    assert fetch.calls == 1


# --- what is used of the answer ----------------------------------------------------------


@pytest.mark.parametrize(
    ("tag", "outcome", "newer"),
    [
        ("v1.5.0", Outcome.NEWER, "1.5.0"),
        ("v2.0.0", Outcome.NEWER, "2.0.0"),
        ("v1.4.10", Outcome.NEWER, "1.4.10"),
        ("v1.4.0", Outcome.CURRENT, None),
        ("v1.3.9", Outcome.CURRENT, None),
    ],
)
def test_the_outcome_compares_numbers(
    file: Path, tag: str, outcome: Outcome, newer: str | None
) -> None:
    check = turned_on(file, FakeRelease(tag), Clock())
    assert check.state().outcome is outcome
    assert check.newer_version() == newer


def test_the_link_shown_is_built_here_never_taken_from_the_answer(file: Path) -> None:
    check = turned_on(file, FakeRelease("v1.5.0"), Clock())
    assert check.release_url() == "https://github.com/dubidu22/sci2audio/releases/tag/v1.5.0"
    assert release_page("1.5.0") == check.release_url()
    assert "evil" not in file.read_text(encoding="utf-8")


def test_after_updating_the_notice_goes(file: Path) -> None:
    turned_on(file, FakeRelease("v1.5.0"), Clock())
    updated = checker(file, FakeRelease("v1.5.0"), current="1.5.0")
    assert updated.state().latest == "1.5.0"
    assert updated.newer_version() is None
    assert updated.release_url() is None


def test_off_shows_no_notice_even_with_a_newer_version_known(file: Path) -> None:
    check = turned_on(file, FakeRelease("v1.5.0"), Clock())
    check.set_enabled(False)
    assert check.newer_version() is None


@pytest.mark.parametrize(
    "body",
    [
        b"not json",
        b"\xff",
        b"[]",
        b"null",
        b'{"tag_name": 5}',
        b'{"tag_name": "1.5.0"}',
        b'{"tag_name": "v1.5"}',
        b'{"tag_name": "v1.5.0-rc1"}',
        b'{"tag_name": "v1.5.0\\n"}',
        '{"tag_name": "v\u0661.\u0665.\u0660"}'.encode(),  # Arabic-Indic digits are no number
        b'{"tag_name": "v1234567.0.0"}',
        b"[" * 100_000,
    ],
)
def test_a_strange_answer_is_a_failed_check(file: Path, body: bytes) -> None:
    with pytest.raises(UpdateCheckFailed):
        latest_version(body)
    check = turned_on(file, lambda: body, Clock())
    state = check.state()
    assert (state.outcome, state.latest, state.checked_at) == (Outcome.FAILED, None, START)


@given(
    st.recursive(
        st.none() | st.booleans() | st.integers() | st.floats() | st.text(),
        lambda children: st.lists(children) | st.dictionaries(st.text(), children),
        max_leaves=20,
    )
    | st.dictionaries(st.just("tag_name"), st.text(max_size=20))
)
def test_any_answer_gives_a_version_or_a_failure(value: object) -> None:
    body = json.dumps(value).encode()
    try:
        version = latest_version(body)
    except UpdateCheckFailed:
        return
    assert isinstance(value, dict)
    assert tuple(int(n) for n in value["tag_name"][1:].split(".")) == version


@given(st.binary(max_size=200))
def test_any_bytes_give_a_version_or_a_failure(body: bytes) -> None:
    with contextlib.suppress(UpdateCheckFailed):
        latest_version(body)


# --- what is sent: the real request, its transport replaced ------------------------------


class Transport:
    """Takes the place of requests' HTTP adapter: records what would go out."""

    def __init__(
        self, status: int = 200, body: bytes | None = None, error: Exception | None = None
    ) -> None:
        self.status = status
        self.body = body if body is not None else b'{"tag_name": "v1.5.0"}'
        self.error = error
        self.sent: list[tuple[requests.PreparedRequest, dict[str, Any]]] = []

    def __call__(
        self, adapter: Any, request: requests.PreparedRequest, **kwargs: Any
    ) -> requests.Response:
        self.sent.append((request, kwargs))
        if self.error is not None:
            raise self.error
        response = requests.Response()
        response.status_code = self.status
        response.url = request.url or ""
        response.request = request
        response.raw = _Raw(self.body)
        if 300 <= self.status < 400:
            response.headers["Location"] = "https://evil.example/elsewhere"
        return response


class _Raw:
    def __init__(self, body: bytes) -> None:
        self.body = body

    def stream(self, size: int, decode_content: bool = True) -> Any:
        for start in range(0, len(self.body), size):
            yield self.body[start : start + size]

    def close(self) -> None:
        pass

    def release_conn(self) -> None:
        pass


@pytest.fixture
def transport(monkeypatch: pytest.MonkeyPatch) -> Transport:
    found = Transport()

    def send(adapter: Any, request: requests.PreparedRequest, **kwargs: Any) -> requests.Response:
        return found(adapter, request, **kwargs)

    monkeypatch.setattr(requests.adapters.HTTPAdapter, "send", send)
    return found


def test_the_request_is_one_get_with_two_headers(transport: Transport) -> None:
    with no_network() as attempts:
        body = fetch_latest_release()
    assert attempts == []
    assert latest_version(body) == (1, 5, 0)
    [(request, kwargs)] = transport.sent
    assert request.method == "GET"
    assert request.url == RELEASES_URL
    assert RELEASES_URL == "https://api.github.com/repos/dubidu22/sci2audio/releases/latest"
    assert request.body is None
    assert dict(request.headers) == {
        "User-Agent": "sci2audio",
        "Accept": "application/vnd.github+json",
    }
    assert kwargs["timeout"] == (5, 10)
    assert not kwargs.get("proxies")
    assert kwargs.get("cert") is None


def test_netrc_cookies_and_proxies_from_the_system_add_nothing(
    transport: Transport, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    netrc = tmp_path / "netrc"
    netrc.write_text("machine api.github.com login someone password secret\n", encoding="utf-8")
    monkeypatch.setenv("NETRC", str(netrc))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.example:3128")
    monkeypatch.setenv("REQUESTS_CA_BUNDLE", str(tmp_path / "nothing.pem"))
    with no_network():
        fetch_latest_release()
    [(request, kwargs)] = transport.sent
    assert "Authorization" not in request.headers
    assert "Cookie" not in request.headers
    assert not kwargs.get("proxies")
    assert kwargs.get("verify") is True


@pytest.mark.parametrize("status", [301, 302, 304, 403, 404, 500])
def test_any_answer_but_200_fails_and_no_redirect_is_followed(
    transport: Transport, status: int
) -> None:
    transport.status = status
    with no_network(), pytest.raises(UpdateCheckFailed):
        fetch_latest_release()
    assert len(transport.sent) == 1


def test_a_long_answer_is_cut_off(transport: Transport) -> None:
    transport.body = b'{"tag_name": "v1.5.0", "x": "' + b"a" * (2 << 20) + b'"}'
    with no_network(), pytest.raises(UpdateCheckFailed, match="too long"):
        fetch_latest_release()


@pytest.mark.parametrize(
    "error",
    [requests.Timeout("slow"), requests.ConnectionError("down"), requests.exceptions.SSLError()],
)
def test_transport_errors_are_a_failed_check(transport: Transport, error: Exception) -> None:
    transport.error = error
    with no_network(), pytest.raises(UpdateCheckFailed):
        fetch_latest_release()


# --- fault injection ---------------------------------------------------------------------


def test_no_network_is_a_failed_check_logged_once(
    file: Path, caplog: pytest.LogCaptureFixture
) -> None:
    clock = Clock()
    with no_network() as attempts, caplog.at_level(logging.WARNING, LOGGER):
        check = turned_on(file, fetch_latest_release, clock)
    assert attempts  # it tried, and was refused
    assert check.state().outcome is Outcome.FAILED
    warnings = [r for r in caplog.records if r.name == LOGGER]
    assert len(warnings) == 1
    assert "update check" in warnings[0].getMessage()


def test_a_timeout_is_retried_only_the_next_day(file: Path) -> None:
    fetch, clock = FakeRelease(error=UpdateCheckFailed("Timeout")), Clock()
    check = turned_on(file, fetch, clock)
    assert check.state().outcome is Outcome.FAILED
    clock.now = START + timedelta(hours=12)
    check.poll()
    check.join(10)
    assert fetch.calls == 1
    fetch.error = None
    clock.now = START + timedelta(days=1)
    check.poll()
    check.join(10)
    assert (fetch.calls, check.state().outcome) == (2, Outcome.NEWER)


def test_any_error_of_the_fetch_never_leaves_the_check(file: Path) -> None:
    check = turned_on(file, FakeRelease(error=RuntimeError("surprise")), Clock())
    assert check.state().outcome is Outcome.FAILED


def test_disk_full_keeps_the_result_for_this_run(
    file: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    fetch, clock = FakeRelease(), Clock()
    check = checker(file, fetch, clock)
    real = updates.write_text_atomically
    real_calls = 0

    def full(target: Path, text: str, *, overwrite: bool) -> None:
        nonlocal real_calls
        if real_calls == 0:  # turning it on still works
            real_calls += 1
            return real(target, text, overwrite=overwrite)
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(updates, "write_text_atomically", full)
    with caplog.at_level(logging.WARNING, LOGGER):
        check.set_enabled(True)
        check.join(10)
    state = check.state()
    assert (state.enabled, state.outcome, state.latest) == (True, Outcome.NEWER, "1.5.0")
    assert check.newer_version() == "1.5.0"
    assert any("could not be saved" in r.getMessage() for r in caplog.records)
    # the file still holds the choice, without the result
    assert load_update_state(file).enabled is True
    assert load_update_state(file).checked_at is None
    # and within this run it is not asked again
    check.poll()
    check.join(10)
    assert fetch.calls == 1


def test_turning_it_on_on_a_full_disk_says_so(file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def full(target: Path, text: str, *, overwrite: bool) -> None:
        raise OSError(errno.ENOSPC, "No space left on device")

    fetch = FakeRelease()
    monkeypatch.setattr(updates, "write_text_atomically", full)
    check = checker(file, fetch)
    with pytest.raises(OSError, match="No space"):
        check.set_enabled(True)
    check.join(10)
    assert fetch.calls == 0
    assert check.state().enabled is False


def test_killed_while_writing_the_result_leaves_the_old_file(
    file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clock = Clock()
    file.parent.mkdir(parents=True)
    file.write_text('{"version": 1, "enabled": true}', encoding="utf-8")  # on, never checked
    before = file.read_bytes()

    def killed(target: Path, text: str, *, overwrite: bool) -> None:
        partial_path(target).write_text(text[: len(text) // 2], encoding="utf-8")
        raise KeyboardInterrupt  # stands for the process dying between the two steps

    fetch = FakeRelease()
    monkeypatch.setattr(updates, "write_text_atomically", killed)
    with pytest.raises(KeyboardInterrupt):
        checker(file, fetch, clock).check()
    monkeypatch.undo()
    assert file.read_bytes() == before
    restarted = checker(file, fetch, clock)
    assert restarted.state().enabled is True
    assert restarted.state().checked_at is None
    restarted.poll()
    restarted.join(10)
    assert restarted.state().outcome is Outcome.NEWER


def test_a_file_removed_before_the_request_means_no_request(file: Path) -> None:
    fetch, clock = FakeRelease(), Clock()
    check = turned_on(file, fetch, clock)
    clock.now = START + timedelta(days=2)
    file.unlink()
    with no_network() as attempts:
        check.poll()
        check.join(10)
    assert fetch.calls == 1
    assert attempts == []


def test_turning_it_off_during_a_check_stays_off(file: Path) -> None:
    fetch, clock = FakeRelease(), Clock()
    fetch.gate = threading.Event()
    check = checker(file, fetch, clock)
    check.set_enabled(True)
    assert fetch.entered.wait(10)
    check.set_enabled(False)  # answers while the request still waits
    fetch.gate.set()
    check.join(10)
    assert check.state().enabled is False
    assert load_update_state(file).enabled is False
