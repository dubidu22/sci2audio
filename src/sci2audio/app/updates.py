"""The opt-in update check (#217, AQ-07, D-837): the one network call besides the voice
download, and only once the person turns it on.

Off by default. When on, at most one request a day: `GET RELEASES_URL` with the two
`HEADERS` and nothing else (no cookie, no credentials from `~/.netrc`, no proxy from the
environment, no redirect followed). Of the answer only the release's tag is used; the link
shown is built here (`release_page`), so the answer can never put a foreign link or text in
the interface. Nothing is downloaded or installed.

The choice and the last result are kept in `update-check.json` next to the settings file.
A missing or damaged file means off. The check runs in a daemon thread and never raises
into the server: every failure is a failed check, logged once and retried the next day.
"""

from __future__ import annotations

import json
import logging
import re
import threading
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path

import requests

from sci2audio import __version__
from sci2audio.app.files import write_text_atomically

RELEASES_URL = "https://api.github.com/repos/dubidu22/sci2audio/releases/latest"
RELEASE_PAGE = "https://github.com/dubidu22/sci2audio/releases/tag/v{version}"
# GitHub's API refuses a request without a User-Agent; this one names no version or system
HEADERS = {"User-Agent": "sci2audio", "Accept": "application/vnd.github+json"}
TIMEOUT = (5, 10)  # seconds: connect, and between two received chunks
LIMIT = 1 << 20  # a release's answer is about 30 KB
DAY = timedelta(days=1)
STATE_NAME = "update-check.json"
STATE_VERSION = 1
# ASCII digits only (other scripts' digits make no version); six digits bound the numbers
_TAG = re.compile(r"v([0-9]{1,6})\.([0-9]{1,6})\.([0-9]{1,6})")
_VERSION = re.compile(r"([0-9]{1,6})\.([0-9]{1,6})\.([0-9]{1,6})")

logger = logging.getLogger(__name__)

Version = tuple[int, int, int]
Fetch = Callable[[], bytes]


class Outcome(StrEnum):
    NEWER = "newer"
    CURRENT = "current"
    FAILED = "failed"


class UpdateCheckFailed(Exception):
    """The release source could not be asked, or its answer holds no release tag."""


@dataclass(frozen=True)
class UpdateState:
    """The person's choice and the last check's result, as `update-check.json` keeps them."""

    enabled: bool = False
    checked_at: datetime | None = None
    outcome: Outcome | None = None
    latest: str | None = None  # "X.Y.Z" of the last answer that named one

    def due(self, now: datetime) -> bool:
        """On, and not checked in the last day (a check dated after `now` means the clock
        was set back: due, so the checks never stop for good)."""
        if not self.enabled:
            return False
        return self.checked_at is None or not self.checked_at <= now < self.checked_at + DAY


def release_page(version: str) -> str:
    return RELEASE_PAGE.format(version=version)


def _version(text: str) -> Version | None:
    found = _VERSION.match(text)
    if found is None:
        return None
    major, minor, patch = (int(part) for part in found.groups())
    return (major, minor, patch)


def latest_version(body: bytes) -> Version:
    """The version the release source's answer names; UpdateCheckFailed if it names none."""
    try:
        data = json.loads(body)
    except (ValueError, RecursionError) as error:  # not JSON, not UTF-8, nested too deeply
        raise UpdateCheckFailed("the answer is not JSON") from error
    tag = data.get("tag_name") if isinstance(data, dict) else None
    found = _TAG.fullmatch(tag) if isinstance(tag, str) else None
    if found is None:
        raise UpdateCheckFailed("the answer names no release")
    major, minor, patch = (int(part) for part in found.groups())
    return (major, minor, patch)


def fetch_latest_release() -> bytes:
    """The release source's answer about the latest release: one GET, nothing else sent."""
    session = requests.Session()
    session.trust_env = False  # no credentials from ~/.netrc, no proxy or CA bundle from env
    session.headers.clear()
    session.headers.update(HEADERS)
    try:
        with (
            session,
            session.get(
                RELEASES_URL, timeout=TIMEOUT, allow_redirects=False, stream=True
            ) as answer,
        ):
            if answer.status_code != 200:
                raise UpdateCheckFailed(f"the release source answered {answer.status_code}")
            body = bytearray()
            for chunk in answer.iter_content(64 * 1024):
                body += chunk
                if len(body) > LIMIT:
                    raise UpdateCheckFailed("the answer is too long")
            return bytes(body)
    except requests.RequestException as error:
        raise UpdateCheckFailed(type(error).__name__) from error


def load_update_state(file: Path) -> UpdateState:
    """The state kept in `file`; off when it is missing, unreadable or damaged."""
    try:
        data = json.loads(file.read_text(encoding="utf-8"))
    except (OSError, ValueError, RecursionError):
        return UpdateState()
    if not isinstance(data, dict):
        return UpdateState()
    version = data.get("version")
    if type(version) is not int or version != STATE_VERSION:  # true is not version 1
        return UpdateState()
    checked_at = None
    if isinstance(data.get("checked_at"), str):
        try:
            checked_at = datetime.fromisoformat(data["checked_at"])
        except ValueError:
            checked_at = None
        if checked_at is not None and checked_at.tzinfo is None:
            checked_at = None
    outcome = data.get("outcome")
    outcome = outcome if isinstance(outcome, str) else None
    latest = data.get("latest")
    return UpdateState(
        enabled=data.get("enabled") is True,
        checked_at=checked_at,
        outcome=Outcome(outcome) if outcome in {str(o) for o in Outcome} else None,
        latest=latest if isinstance(latest, str) and _VERSION.fullmatch(latest) else None,
    )


def save_update_state(state: UpdateState, file: Path) -> None:
    """Keep `state` in `file`, all or nothing (OSError if it can't be written)."""
    data = {
        "version": STATE_VERSION,
        "enabled": state.enabled,
        "checked_at": None if state.checked_at is None else state.checked_at.isoformat(),
        "outcome": None if state.outcome is None else str(state.outcome),
        "latest": state.latest,
    }
    file.parent.mkdir(parents=True, exist_ok=True)
    write_text_atomically(file, json.dumps(data, indent=2) + "\n", overwrite=True)


def _utc_now() -> datetime:
    return datetime.now(UTC)


class UpdateCheck:
    """One server run's update check: `file` keeps the state, `fetch` asks the release
    source (tests pass a fake), `now` is the clock, `current` the running version.
    `available` false is a server that never checks (`sci2audio listen`, D-837): the
    choice can still be changed, but no request is made and no notice shown."""

    def __init__(
        self,
        file: Path,
        *,
        fetch: Fetch = fetch_latest_release,
        now: Callable[[], datetime] = _utc_now,
        current: str = __version__,
        available: bool = True,
    ) -> None:
        self.file = file
        self.available = available
        self._fetch = fetch
        self._now = now
        self._current = _version(current) or (0, 0, 0)
        self._lock = threading.Lock()  # every read-modify-write of the state
        self._unsaved: UpdateState | None = None  # a result the disk would not take
        # turned off in this run: holds even when the disk would not take the choice, since
        # the person asked for no more requests
        self._off = False
        self._thread: threading.Thread | None = None

    def state(self) -> UpdateState:
        with self._lock:
            return self._read()

    def _read(self) -> UpdateState:
        state = self._unsaved if self._unsaved is not None else load_update_state(self.file)
        return replace(state, enabled=False) if self._off else state

    def _due(self, now: datetime) -> bool:
        """Due by what this run holds and by the file: either one saying off is off."""
        if not self.available or not self._read().due(now):
            return False
        return self._unsaved is None or load_update_state(self.file).enabled

    def set_enabled(self, enabled: bool) -> UpdateState:
        """Turn the check on or off (OSError if the choice can't be saved). Off takes effect
        for this run even then; on does not. Turning it on starts a check when none was
        made in the last day."""
        with self._lock:
            if not enabled:
                self._off = True
            state = replace(self._read(), enabled=enabled)
            save_update_state(state, self.file)
            self._unsaved = None
            self._off = not enabled
        self.poll()
        return state

    def poll(self) -> UpdateState:
        """The state now; starts a check in the background when one is due."""
        with self._lock:
            state = self._read()
            running = self._thread is not None and self._thread.is_alive()
            if self._due(self._now()) and not running:
                self._thread = threading.Thread(
                    target=self.check, name="sci2audio-update-check", daemon=True
                )
                self._thread.start()
        return state

    def join(self, timeout: float | None = None) -> None:
        """Wait for a check in the background to end (tests, and nothing else waits)."""
        thread = self._thread
        if thread is not None:
            thread.join(timeout)

    def check(self) -> UpdateState:
        """Ask the release source now if a check is due, and keep the result."""
        now = self._now()
        with self._lock:
            if not self._due(now):  # read again: turned off or removed meanwhile
                return self._read()
        try:
            found = latest_version(self._fetch())
        # every failure, whatever raised it, is the day's failed check, never the server's
        except Exception as error:
            logger.warning("the update check did not work: %s", error)
            outcome, latest = Outcome.FAILED, None
        else:
            newer = found > self._current
            outcome, latest = (Outcome.NEWER if newer else Outcome.CURRENT), _text(found)
        with self._lock:
            # the choice as it is now: the person may have turned it off during the request
            state = replace(self._read(), checked_at=now, outcome=outcome, latest=latest)
            try:
                save_update_state(state, self.file)
            except OSError as error:
                logger.warning("the update check's result could not be saved: %s", error)
                self._unsaved = state
            else:
                self._unsaved = None
        return state

    def newer_version(self) -> str | None:
        """The newer version to tell the person about, or None (off, none, or installed)."""
        state = self.state()
        if not self.available or not state.enabled or state.latest is None:
            return None
        latest = _version(state.latest)
        return state.latest if latest is not None and latest > self._current else None

    def release_url(self) -> str | None:
        version = self.newer_version()
        return None if version is None else release_page(version)


def _text(version: Version) -> str:
    return ".".join(str(part) for part in version)
