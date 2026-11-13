"""OWASP ZAP baseline scan of the local server (#12, AQ-03; D-364 to D-372).

    uv run python scripts/zap_scan.py                  # needs Docker (see below)
    uv run python scripts/zap_scan.py --out zap-out    # where the reports go
    uv run python scripts/zap_scan.py --help

A passive scan, as ZAP's baseline scan is: ZAP only looks at what goes back and forth and
never attacks. The script

1. starts the real server on 127.0.0.1 with a fresh work folder, the fake voice and a fake
   voice download, as the browser tests do (no models, no network);
2. starts ZAP in Docker as a proxy (`--network host`: the server answers only
   `Host: 127.0.0.1:<port>`, D-194);
3. walks the main flow through that proxy in Chromium (Playwright), as a person does, in
   English and in German: open files, the analysis, the voice set-up and download, a
   preview, the audiobook, the player, every API route, the language switch, and the
   answers without the start cookie (401) and to a wrong Host (421);
4. lets ZAP's spider crawl from `/` with the start cookie, in both languages;
5. waits for the passive scan, then judges the alerts (D-367): High and Medium always
   fail; Low fails unless `scripts/zap/accepted.toml` accepts it with a reason and a
   decision; Informational is listed only, each with the explanation the same file
   gives for its rule (`[[informational]]`), or "not yet explained". It also fails when
   a route of the app was never scanned with a real answer (a 401, 403 or 421 refusal
   doesn't count), or a page was not seen in both languages, so a broken walk can't
   pass by scanning nothing.

It writes `zap-summary.md`, `zap-alerts.json` and ZAP's own HTML report to `--out` and
exits with 0 (passed), 1 (findings or gaps) or 2 (could not run: a broken accepted list,
no Docker, ZAP or the server not starting, or the walk not doing what a person would).

Docker: Linux, or Docker Desktop 4.34 or later on macOS and Windows with host networking
turned on (D-371). CI runs it in `.github/workflows/zap.yml` (D-364).
"""

from __future__ import annotations

import argparse
import contextlib
import json
import re
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import tomllib
import traceback
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
ACCEPTED = Path(__file__).resolve().parent / "zap" / "accepted.toml"
# ZAP 2.17.0, the "stable" image of 2 Nov 2026; bumped by hand (D-370, release checklist)
IMAGE = (
    "ghcr.io/zaproxy/zaproxy@sha256:"
    "9624669db72f54d86c4b46a7064518bd9bf79d8c61a4c31befa9923489f328af"
)
RISKS = ("Informational", "Low", "Medium", "High")
ACCEPTABLE = frozenset({"Low"})  # High and Medium are fixed, never accepted (D-369)
LANGUAGES = ("en", "de")
DECISION = re.compile(r"D-\d+")
ACCEPTED_KEYS = frozenset({"rule", "risk", "url", "reason", "decision"})
NOTE_KEYS = frozenset({"rule", "reason", "decision"})
# the middleware's own refusals: an answer with one of these never counts as the route
# scanned (the 401 page and the 421 answer are checked on their own)
REFUSALS = frozenset({401, 403, 421})
NO_DOCUMENT = "0" * 16  # a document id that is never opened: the "not found" page
# a name that points at 127.0.0.1 inside ZAP's container only: DNS rebinding (D-194)
REBOUND = "rebound.example"


# --- judging (pure; tests/unit/test_zap_scan.py) ------------------------------------------


@dataclass(frozen=True)
class Alert:
    """One ZAP alert on one URL. `url` is the path and query, without the origin, whose
    port changes from run to run."""

    rule: int
    name: str
    risk: str
    url: str
    method: str = "GET"
    param: str = ""
    evidence: str = ""

    @classmethod
    def from_zap(cls, raw: dict[str, Any]) -> Alert:
        parts = urlsplit(str(raw.get("url", "")))
        url = parts.path + (f"?{parts.query}" if parts.query else "")
        risk = str(raw.get("risk", ""))
        if risk not in RISKS:
            raise ValueError(f"ZAP gave an alert with an unknown risk {risk!r}")
        return cls(
            rule=int(raw.get("pluginId", 0)),
            name=str(raw.get("name") or raw.get("alert") or ""),
            risk=risk,
            url=url or "/",
            method=str(raw.get("method") or "GET"),
            param=str(raw.get("param") or ""),
            evidence=str(raw.get("evidence") or ""),
        )


@dataclass(frozen=True)
class Accepted:
    """A Low alert accepted with a written reason: one rule on the URLs `url` matches in
    full (path and query)."""

    rule: int
    risk: str
    url: re.Pattern[str]
    reason: str
    decision: str

    def covers(self, alert: Alert) -> bool:
        return (
            alert.rule == self.rule
            and alert.risk == self.risk
            and self.url.fullmatch(alert.url) is not None
        )


class AcceptedListError(ValueError):
    """`accepted.toml` is not as described at its top."""


@dataclass(frozen=True)
class Note:
    """Why an informational alert of one rule is no problem here (for the summary)."""

    rule: int
    reason: str
    decision: str


def _tables(path: Path, name: str) -> list[Any]:
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise AcceptedListError(f"{path}: {error}") from error
    unknown = set(data) - {"accepted", "informational"}
    if unknown:
        raise AcceptedListError(f"{path}: unknown table(s) {sorted(unknown)}")
    entries = data.get(name, [])
    if not isinstance(entries, list):
        raise AcceptedListError(f"{path}: `{name}` must be an array of tables")
    return entries


def _checked(where: str, entry: Any, wanted: frozenset[str]) -> dict[str, Any]:
    """The entry's keys and the three fields every entry has (rule, reason, decision)."""
    if not isinstance(entry, dict):
        raise AcceptedListError(f"{where}: not a table")
    keys = set(entry)
    if keys != wanted:
        missing, extra = wanted - keys, keys - wanted
        raise AcceptedListError(
            f"{where}: missing {sorted(missing)}, unknown {sorted(extra)}"
            if missing and extra
            else f"{where}: missing {sorted(missing)}"
            if missing
            else f"{where}: unknown {sorted(extra)}"
        )
    rule, reason, decision = entry["rule"], entry["reason"], entry["decision"]
    if not isinstance(rule, int) or isinstance(rule, bool) or rule <= 0:
        raise AcceptedListError(f"{where}: rule must be a ZAP rule number")
    if not isinstance(reason, str) or len(reason.strip()) < 20:
        raise AcceptedListError(f"{where}: the reason must say why (20 characters or more)")
    if not isinstance(decision, str) or not DECISION.fullmatch(decision):
        raise AcceptedListError(f"{where}: decision must look like D-123")
    return entry


def load_notes(path: Path) -> dict[int, Note]:
    """The `[[informational]]` entries by rule; one per rule."""
    notes: dict[int, Note] = {}
    for number, entry in enumerate(_tables(path, "informational"), 1):
        where = f"{path}: informational entry {number}"
        entry = _checked(where, entry, NOTE_KEYS)
        if entry["rule"] in notes:
            raise AcceptedListError(f"{where}: rule {entry['rule']} is explained twice")
        notes[entry["rule"]] = Note(entry["rule"], entry["reason"].strip(), entry["decision"])
    return notes


def load_accepted(path: Path) -> tuple[Accepted, ...]:
    entries = _tables(path, "accepted")
    found: list[Accepted] = []
    for number, entry in enumerate(entries, 1):
        where = f"{path}: entry {number}"
        entry = _checked(where, entry, ACCEPTED_KEYS)
        rule, risk, url = entry["rule"], entry["risk"], entry["url"]
        reason, decision = entry["reason"], entry["decision"]
        if risk not in ACCEPTABLE:
            raise AcceptedListError(
                f"{where}: only Low alerts can be accepted; {risk!r} must be fixed (D-369)"
            )
        if not isinstance(url, str) or not url:
            raise AcceptedListError(f"{where}: url must be a regular expression")
        try:
            pattern = re.compile(url)
        except re.error as error:
            raise AcceptedListError(f"{where}: url is not a regular expression: {error}") from error
        found.append(Accepted(rule, risk, pattern, reason.strip(), decision))
    return tuple(found)


@dataclass
class Verdict:
    failing: list[Alert] = field(default_factory=list)
    accepted: list[tuple[Alert, Accepted]] = field(default_factory=list)
    informational: list[Alert] = field(default_factory=list)
    stale: list[Accepted] = field(default_factory=list)  # reported, never failing (D-367)
    gaps: list[str] = field(default_factory=list)  # routes or languages never scanned

    @property
    def passed(self) -> bool:
        return not self.failing and not self.gaps


def judge(
    alerts: Iterable[Alert], accepted: Sequence[Accepted], gaps: Iterable[str] = ()
) -> Verdict:
    verdict = Verdict(gaps=list(gaps))
    used: set[int] = set()
    for alert in sorted(set(alerts), key=_order):
        if alert.risk == "Informational":
            verdict.informational.append(alert)
            continue
        entry = next((e for e in accepted if e.risk in ACCEPTABLE and e.covers(alert)), None)
        if entry is None:
            verdict.failing.append(alert)
        else:
            verdict.accepted.append((alert, entry))
            used.add(id(entry))
    verdict.stale = [entry for entry in accepted if id(entry) not in used]
    return verdict


def _order(alert: Alert) -> tuple[int, int, str, str]:
    return (-RISKS.index(alert.risk), alert.rule, alert.url, alert.param)


# --- coverage: every route of the app, every page in both languages ----------------------


@dataclass(frozen=True)
class Seen:
    """One request and answer from ZAP's history."""

    method: str
    path: str
    status: int
    language: str | None  # <html lang> of an HTML answer


@dataclass(frozen=True)
class Route:
    method: str
    template: str
    pattern: re.Pattern[str]
    page: bool  # an HTML page: must be seen in every language


def gaps_in(routes: Iterable[Route], seen: Iterable[Seen], extra: Iterable[str] = ()) -> list[str]:
    """What the scan never saw: a route never answered for real (a 401, 403 or 421 refusal
    doesn't count: the spider's refused POSTs and the 401 pages would otherwise stand in
    for routes the walk never reached), a page not answered in one of the languages, and
    the middleware's own answers (start link, 401 in both languages, 421)."""
    seen = list(seen)
    missing: list[str] = []
    for route in routes:
        hits = [
            s
            for s in seen
            if s.method == route.method
            and route.pattern.fullmatch(s.path)
            and s.status not in REFUSALS
        ]
        if not hits:
            missing.append(f"{route.method} {route.template} was never scanned")
            continue
        if route.page:
            for language in LANGUAGES:
                if not any(s.language == language for s in hits):
                    missing.append(f"{route.method} {route.template} was not seen in {language!r}")
    checks = {
        "the start link (303 with the cookie)": lambda s: s.path == "/start" and s.status == 303,
        "the 401 page in English": lambda s: s.status == 401 and s.language == "en",
        "the 401 page in German": lambda s: s.status == 401 and s.language == "de",
        "the 421 answer to a wrong Host": lambda s: s.status == 421,
    }
    for label, check in checks.items():
        if not any(check(s) for s in seen):
            missing.append(f"{label} was never scanned")
    missing.extend(extra)
    return missing


def routes_of(app: Any) -> list[Route]:
    """Every method of every route of the app (the static files mount counts once).

    FastAPI 0.16x keeps an included router as one entry that points at the original
    router; older versions copy its routes in. Both are followed, and a test checks the
    list holds the app's pages and API routes."""
    from starlette.routing import Mount

    found: list[Route] = []
    pending = list(app.router.routes)
    while pending:
        route = pending.pop(0)
        included = getattr(route, "original_router", None)
        if included is not None:
            pending[:0] = list(included.routes)
            continue
        if isinstance(route, Mount):
            pattern = re.compile(re.escape(route.path) + "/.+")
            found.append(Route("GET", f"{route.path}/…", pattern, False))
            continue
        page = "HTMLResponse" in repr(getattr(route, "response_class", ""))
        for method in sorted(getattr(route, "methods", None) or ()):
            if method != "HEAD":
                found.append(Route(method, route.path, route.path_regex, page))
    return found


# --- the summary ----------------------------------------------------------------------------


def summary(
    verdict: Verdict,
    *,
    image: str,
    origin: str,
    messages: int,
    when: str,
    notes: dict[int, Note] | None = None,
) -> str:
    notes = notes or {}
    lines = [
        "# ZAP baseline scan",
        "",
        f"{'**Passed.**' if verdict.passed else '**Failed.**'} {when}, image `{image}`, "
        f"{messages} requests seen through ZAP, server {origin} (#12, D-364 to D-372).",
        "",
    ]

    def table(title: str, rows: list[tuple[Alert, str]]) -> None:
        lines.extend([f"## {title}", ""])
        if not rows:
            lines.extend(["None.", ""])
            return
        lines.extend(["| Risk | Rule | Where | Note |", "|---|---|---|---|"])
        for alert, note in rows:
            where = f"{alert.method} `{alert.url}`" + (f" ({alert.param})" if alert.param else "")
            lines.append(
                f"| {alert.risk} | {alert.rule} {alert.name} | {where} | {note.replace('|', '/')} |"
            )
        lines.append("")

    table("Failing", [(a, "fix, or accept a Low one with a reason") for a in verdict.failing])
    if verdict.gaps:
        lines.extend(["## Not scanned", "", *(f"- {gap}" for gap in verdict.gaps), ""])
    table("Accepted (Low)", [(a, f"{e.decision}: {e.reason}") for a, e in verdict.accepted])
    table("Informational (never fails)", [(a, _explained(a, notes)) for a in verdict.informational])
    if verdict.stale:
        lines.extend(["## Accepted entries that matched nothing", ""])
        lines.extend(f"- rule {e.rule} `{e.url.pattern}` ({e.decision})" for e in verdict.stale)
        lines.append("")
    return "\n".join(lines)


def _explained(alert: Alert, notes: dict[int, Note]) -> str:
    note = notes.get(alert.rule)
    return f"{note.decision}: {note.reason}" if note else "not yet explained"


# --- ZAP in Docker ------------------------------------------------------------------------


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class Zap:
    """ZAP's daemon in Docker, on 127.0.0.1 only, its API behind a fresh key."""

    def __init__(self, image: str, port: int) -> None:
        import httpx

        self.docker = shutil.which("docker") or "docker"
        self.image = image
        self.port = port
        self.key = secrets.token_urlsafe(24)
        self.name = f"sci2audio-zap-{port}"
        self.proxy = f"http://127.0.0.1:{port}"
        # trust_env=False: never through a proxy from the environment
        self.client = httpx.Client(base_url=self.proxy, timeout=60, trust_env=False)

    def start(self, timeout: float = 180) -> None:
        command = [
            self.docker, "run", "--detach", "--rm", "--name", self.name, "--network", "host",
            "--add-host", f"{REBOUND}:127.0.0.1",
            self.image, "zap.sh", "-daemon", "-silent",
            "-host", "127.0.0.1", "-port", str(self.port),
            "-config", f"api.key={self.key}",
            "-config", "api.addrs.addr.name=127.0.0.1",
            "-config", "api.addrs.addr.regex=false",
        ]  # fmt: skip
        subprocess.run(command, check=True, capture_output=True, text=True)  # noqa: S603 (no shell)
        deadline = time.monotonic() + timeout
        while True:
            with contextlib.suppress(Exception):
                version = self.view("core", "version")["version"]
                print(f"ZAP {version} is running on {self.proxy}", flush=True)
                return
            if time.monotonic() > deadline:
                raise RuntimeError(f"ZAP did not start within {timeout:.0f} s:\n{self.logs()}")
            time.sleep(2)

    def stop(self) -> None:
        subprocess.run([self.docker, "stop", self.name], capture_output=True, check=False)  # noqa: S603

    def logs(self) -> str:
        done = subprocess.run(  # noqa: S603 (no shell)
            [self.docker, "logs", "--tail", "40", self.name],
            capture_output=True,
            text=True,
            check=False,
        )
        return done.stdout + done.stderr

    def _json(self, component: str, kind: str, name: str, **params: Any) -> Any:
        answer = self.client.get(
            f"/JSON/{component}/{kind}/{name}/", params={"apikey": self.key, **params}
        )
        answer.raise_for_status()
        return answer.json()

    def view(self, component: str, name: str, **params: Any) -> Any:
        return self._json(component, "view", name, **params)

    def action(self, component: str, name: str, **params: Any) -> Any:
        return self._json(component, "action", name, **params)

    def other(self, component: str, name: str) -> str:
        answer = self.client.get(f"/OTHER/{component}/other/{name}/", params={"apikey": self.key})
        answer.raise_for_status()
        return answer.text

    def spider(self, url: str, timeout: float = 300) -> None:
        scan = self.action("spider", "scan", url=url, recurse="true")["scan"]
        deadline = time.monotonic() + timeout
        while int(self.view("spider", "status", scanId=scan)["status"]) < 100:
            if time.monotonic() > deadline:
                raise RuntimeError("ZAP's spider did not finish")
            time.sleep(1)

    def passive_done(self, timeout: float = 300) -> None:
        deadline = time.monotonic() + timeout
        while int(self.view("pscan", "recordsToScan")["recordsToScan"]) > 0:
            if time.monotonic() > deadline:
                raise RuntimeError("ZAP's passive scan did not finish")
            time.sleep(1)

    def alerts(self, origin: str) -> list[dict[str, Any]]:
        found: list[dict[str, Any]] = []
        while True:
            page = self.view("alert", "alerts", baseurl=origin, start=len(found), count=500)
            found.extend(page["alerts"])
            if len(page["alerts"]) < 500:
                return found

    def history(self, origin: str) -> list[Seen]:
        seen: list[Seen] = []
        start = 0
        while True:
            page = self.view("core", "messages", baseurl=origin, start=start, count=100)
            messages = page["messages"]
            seen.extend(_seen(message) for message in messages)
            start += len(messages)
            if len(messages) < 100:
                return seen


_LANG = re.compile(r'<html lang="([a-z]{2})"')


def _seen(message: dict[str, Any]) -> Seen:
    request = str(message.get("requestHeader", ""))
    response = str(message.get("responseHeader", ""))
    first = request.split("\r\n", 1)[0].split(" ")
    method = first[0] if first else ""
    target = urlsplit(first[1] if len(first) > 1 else "")
    status_line = response.split("\r\n", 1)[0].split(" ")
    status = int(status_line[1]) if len(status_line) > 1 and status_line[1].isdigit() else 0
    found = _LANG.search(str(message.get("responseBody", ""))[:500])
    return Seen(method, target.path or "/", status, found.group(1) if found else None)


# --- the server and the walk ------------------------------------------------------------------


@contextlib.contextmanager
def local_server(work: Path) -> Iterator[tuple[Any, Any, Any]]:
    """The real server on 127.0.0.1 with the browser tests' fakes; yields (app, config,
    fetch)."""
    sys.path[:0] = [str(ROOT / "tests" / "unit"), str(ROOT / "tests" / "browser")]
    import uvicorn
    from audio_fakes import FakeVoice
    from web_helpers import make_config

    import conftest as browser_fixtures  # tests/browser/conftest.py: fakes, small plan
    from sci2audio.voices import download as download_module
    from sci2audio.web import api, create_app, pages
    from sci2audio.web.launch import bind, uvicorn_config

    plan = browser_fixtures.small_plan()
    for module in (download_module, api, pages):
        module.download_plan = lambda: plan  # type: ignore[attr-defined]
    sock = bind()
    config = make_config(work, port=sock.getsockname()[1])
    voice = FakeVoice()
    fetch = browser_fixtures.SlowFetch()
    app = create_app(config, fetch=fetch, voice=lambda models_dir: voice.source())
    server = uvicorn.Server(uvicorn_config(app))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started:
        if time.monotonic() > deadline:
            raise RuntimeError("the server did not start")
        time.sleep(0.02)
    state = app.state.sci2audio
    try:
        yield app, config, fetch
    finally:
        state.stopping.set()
        state.board.shutdown(5)
        state.kept.dispose()
        server.should_exit = True
        thread.join(10)
        sock.close()


def walk(config: Any, proxy: str, chromium: str | None) -> None:
    """The main flow through ZAP, in English and then in German (D-366)."""
    import httpx
    from playwright.sync_api import expect, sync_playwright
    from web_helpers import paper_bytes, pdf_bytes

    origin = config.origin
    expect.set_options(timeout=60_000)
    paper = {"name": "paper.pdf", "mimeType": "application/pdf", "buffer": paper_bytes()}
    note = {"name": "note.pdf", "mimeType": "application/pdf", "buffer": pdf_bytes()}
    outside: list[str] = []

    def fence(route: Any) -> None:
        """The pages may talk to this server only, as in the browser tests."""
        if route.request.url.startswith(origin + "/"):
            route.continue_()
        else:
            outside.append(route.request.url)
            route.abort()

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=chromium,
            proxy={"server": proxy},
            # Chromium never sends 127.0.0.1 through a proxy unless told to
            args=["--proxy-bypass-list=<-loopback>"],
        )
        try:
            # without the start cookie: the 401 page in both languages (Accept-Language)
            for locale in ("en-GB", "de-DE"):
                context = browser.new_context(locale=locale)
                context.route("**/*", fence)
                page = context.new_page()
                answer = page.goto(f"{origin}/")
                _check(answer is not None and answer.status == 401, "no 401 without the cookie")
                context.request.get(f"{origin}/openapi.json")
                context.close()

            context = browser.new_context(locale="en-GB", accept_downloads=True)
            context.route("**/*", fence)
            context.route(EVENTS, _direct_stream(config))  # added last, so asked first
            page = context.new_page()
            page.set_default_timeout(60_000)
            ids = _walk_english(page, context, origin, config.start_url, paper, note)
            # the language switch, a GET form in the header (D-321)
            page.goto(f"{origin}/privacy")
            page.locator("form.languages button[value=de]").click()
            expect(page.locator("html")).to_have_attribute("lang", "de")
            for path in _pages(ids):
                answer = page.goto(origin + path)
                _check(answer is not None, path)
                expect(page.locator("html")).to_have_attribute("lang", "de")
            context.close()
        finally:
            browser.close()
    _check(not outside, f"the pages tried to reach something else: {outside}")

    # a wrong Host (DNS rebinding, D-194): another name for 127.0.0.1, through ZAP
    with httpx.Client(proxy=proxy, trust_env=False, timeout=30) as client:
        answer = client.get(f"http://{REBOUND}:{config.port}/")
        _check(answer.status_code == 421, f"a wrong Host got {answer.status_code}")


class WalkError(RuntimeError):
    """The walk did not see what a person would."""


def _check(condition: object, message: str) -> None:
    if not condition:
        raise WalkError(message)


EVENTS = re.compile(r"/api/v1/jobs/[^/?]+/events$")


def _direct_stream(config: Any) -> Any:
    """ZAP 2.17 passes a server-sent event stream on to the browser without its body, so
    the page would wait for a job's end forever. The walk fetches the pages' own streams
    straight from the server (they end with the job); ZAP sees the stream's answer once
    through `_every_api_route`, headers and all."""
    import httpx

    direct = httpx.Client(
        base_url=config.origin,
        headers={"Authorization": f"Bearer {config.token}"},
        timeout=300,
        trust_env=False,
    )

    def handle(route: Any) -> None:
        answer = direct.get(urlsplit(route.request.url).path)
        route.fulfill(
            status=answer.status_code,
            headers=dict(answer.headers),
            body=answer.content,
        )

    return handle


@dataclass(frozen=True)
class Ids:
    paper: str
    note: str
    script_job: str
    audio_job: str
    voice_job: str


def _pages(ids: Ids) -> list[str]:
    return [
        "/",
        "/privacy",
        "/voice",
        f"/documents/{ids.paper}",
        f"/documents/{NO_DOCUMENT}",
        f"/jobs/{ids.script_job}",
        f"/jobs/{ids.audio_job}",
        f"/jobs/{ids.voice_job}",
        f"/documents/{ids.paper}/listen",
        f"/documents/{ids.note}/listen",  # nothing to play
    ]


def _walk_english(
    page: Any, context: Any, origin: str, start_url: str, paper: Any, note: Any
) -> Ids:
    from playwright.sync_api import expect

    page.goto(start_url)
    _check(page.url == origin + "/", page.url)
    expect(page.locator("html")).to_have_attribute("lang", "en")
    for path in ("/privacy", "/voice", f"/documents/{NO_DOCUMENT}"):
        page.goto(origin + path)

    # open a file and read its analysis
    page.goto(origin + "/")
    page.set_input_files("#file", files=[paper])
    page.locator("#open-file button[type=submit]").click()
    page.wait_for_url(re.compile(r"/documents/[0-9a-f]{16}$"))
    paper_id = page.url.rsplit("/", 1)[1]
    expect(page.locator("#summary")).to_be_visible()
    expect(page.locator("#document[data-events]")).to_have_count(0)
    with page.expect_download():
        page.locator("a[download], a[href*='download=']").first.click()
    # a switch off and back on: the update starts a script job
    page.get_by_role("checkbox", name=re.compile("^Citations")).uncheck()
    page.get_by_role("button", name="Update the analysis").click()
    expect(page.locator("#changed")).to_be_hidden()
    page.get_by_role("checkbox", name=re.compile("^Citations")).check()
    page.get_by_role("button", name="Update the analysis").click()
    expect(page.locator("#changed")).to_be_hidden()

    # the voice: refused without consent, then downloaded (the fake download)
    page.goto(origin + "/voice")
    page.get_by_role("button", name="Download the voice").click()
    page.get_by_role("checkbox", name=re.compile("I agree")).check()
    page.get_by_role("button", name="Download the voice").click()
    page.wait_for_url(re.compile(r"/jobs/voices-\d+$"))
    voice_job = page.url.rsplit("/", 1)[1]
    expect(page.locator("#result")).to_have_text(re.compile("The voice is installed"))

    # a preview, then the audiobook, its files, the player
    page.goto(f"{origin}/documents/{paper_id}")
    page.get_by_role("button", name="Listen").click()
    expect(page.locator("#preview-audio")).to_be_visible()
    page.get_by_role("button", name="Make the audiobook").click()
    page.wait_for_url(re.compile(r"/jobs/[0-9a-f]{16}-audio-\d+$"))
    audio_job = page.url.rsplit("/", 1)[1]
    expect(page.locator("#result")).to_have_text("Your audiobook is ready")
    for link in page.locator("ul.files a").all():
        context.request.get(origin + str(link.get_attribute("href")))
    page.get_by_role("link", name="Listen with the text").click()
    page.wait_for_url(re.compile(r"/listen$"))
    page.locator(".s").first.click()
    page.wait_for_function("() => document.getElementById('audio').readyState >= 1")

    # again: the files exist, then replace them; free the speech cache
    page.goto(f"{origin}/documents/{paper_id}")
    page.get_by_role("button", name="Make the audiobook").click()
    page.get_by_role("button", name="Replace these files").click()
    expect(page.locator("#result")).to_have_text("Your audiobook is ready")
    page.get_by_role("button", name="Free the speech cache").click()
    expect(page.locator("#message")).to_have_text("The speech cache is empty.")

    # a second file, never made into an audiobook: the player has nothing to play
    page.goto(origin + "/")
    page.set_input_files("#file", files=[note])
    page.locator("#open-file button[type=submit]").click()
    page.wait_for_url(re.compile(r"/documents/[0-9a-f]{16}$"))
    note_id = page.url.rsplit("/", 1)[1]
    expect(page.locator("#document[data-events]")).to_have_count(0)

    jobs = context.request.get(f"{origin}/api/v1/jobs").json()
    script_job = next(job["id"] for job in jobs if job["kind"] == "script")
    ids = Ids(paper_id, note_id, script_job, audio_job, voice_job)
    for path in _pages(ids):
        page.goto(origin + path)
    _every_api_route(context, origin, ids)
    return ids


def _every_api_route(context: Any, origin: str, ids: Ids) -> None:
    """The API routes the pages above don't call, as the page's script would: with the
    cookie, and `Origin` on everything that changes something (D-194). Each answer is
    checked, so a refused walk can't pass for a scanned one."""
    same = {"Origin": origin}

    def call(method: str, path: str, *codes: int, **options: Any) -> Any:
        answer = context.request.fetch(origin + path, method=method, **options)
        _check(answer.status in codes, f"{method} {path} answered {answer.status}")
        return answer

    api = "/api/v1"
    document = call("GET", f"{api}/documents/{ids.paper}", 200).json()
    call("GET", f"{api}/documents", 200)
    call("GET", f"{api}/documents/{ids.paper}/report", 200)
    call("GET", f"{api}/documents/{ids.paper}/chapters", 200)
    for name in _names(document, "analysis_files"):
        call("GET", f"{api}/documents/{ids.paper}/files/{name}", 200)
    call("GET", f"{api}/documents/{ids.paper}/files/none.txt", 404)
    call("GET", f"{api}/documents/{ids.paper}/audiobook/none.mp3", 404)
    job = call("GET", f"{api}/jobs/{ids.audio_job}", 200).json()
    for name in _names(job, "files"):
        call("GET", f"{api}/jobs/{ids.audio_job}/files/{name}", 200)
    call("GET", f"{api}/jobs/{ids.audio_job}/events", 200)
    call("GET", f"{api}/voices", 200)
    settings = call("GET", f"{api}/settings", 200).json()["settings"]
    call("PUT", f"{api}/settings", 200, data=settings, headers=same)
    call(
        "POST", f"{api}/documents/text", 201, 415,  # 415 until text files are read (#74)
        data={"text": "A short pasted note.", "name": "note"}, headers=same,
    )  # fmt: skip
    call("POST", f"{api}/jobs/{ids.audio_job}/cancel", 409, headers=same)  # it has ended
    call("POST", f"{api}/voices/preview", 202, data={"text": "A preview."}, headers=same)
    call("DELETE", f"{api}/documents/{ids.paper}/chunks", 204, headers=same)
    call("GET", "/openapi.json", 200)
    # another site as the way back: the switch goes home instead (D-321)
    back = call("GET", "/language?language=en&back=https://elsewhere.example/", 303,
                max_redirects=0)  # fmt: skip
    _check(back.headers.get("location") == "/", "the language switch left the server")


def _names(record: dict[str, Any], key: str) -> list[str]:
    files = record.get(key) or []
    return [str(f["name"]) for f in files if isinstance(f, dict) and "name" in f]


# --- the run -----------------------------------------------------------------------------


def run(image: str, out: Path, accepted_file: Path, chromium: str | None) -> int:
    accepted = load_accepted(accepted_file)  # a broken list fails before anything starts
    notes = load_notes(accepted_file)
    if shutil.which("docker") is None:
        print("zap_scan: Docker is needed (https://docs.docker.com/get-docker/)", file=sys.stderr)
        return 2
    out.mkdir(parents=True, exist_ok=True)
    zap = Zap(image, free_port())
    with (
        tempfile.TemporaryDirectory(prefix="sci2audio-zap-") as work,
        local_server(Path(work)) as (app, config, fetch),
    ):
        origin = config.origin
        print(f"sci2audio is running at {origin}", flush=True)
        try:
            zap.start()  # in here, so a start that fails or times out is stopped too
            walk(config, zap.proxy, chromium)
            # the spider, with the start cookie, once per language (spider requests only)
            for language in LANGUAGES:
                cookie = f"{config.cookie_name}={config.token}; sci2audio-language={language}"
                with contextlib.suppress(Exception):  # none yet before the first
                    zap.action("replacer", "removeRule", description="sci2audio")
                zap.action(
                        "replacer", "addRule", description="sci2audio", enabled="true",
                        matchType="REQ_HEADER", matchRegex="false", matchString="Cookie",
                        replacement=cookie, initiators="3",
                    )  # fmt: skip
                zap.spider(f"{origin}/")
            zap.passive_done()
            # the wrong-Host request went to another name for the same server
            sites = (origin, f"http://{REBOUND}:{config.port}")
            raw = [alert for site in sites for alert in zap.alerts(site)]
            seen = [message for site in sites for message in zap.history(site)]
            report = zap.other("core", "htmlreport")
        except Exception:
            print(zap.logs(), file=sys.stderr)
            raise
        finally:
            zap.stop()
        outside = [url for url in fetch.fetched if not url.startswith("https://example.test/")]
        if outside:
            raise RuntimeError(f"the server fetched something real: {outside}")
        routes = routes_of(app)
    # the start link's token is spent once the server stops; it still stays out of reports
    raw = json.loads(json.dumps(raw).replace(config.token, "<token>"))
    report = report.replace(config.token, "&lt;token&gt;")
    (out / "zap-report.html").write_text(report, "utf-8")
    alerts = [Alert.from_zap(item) for item in raw]
    verdict = judge(alerts, accepted, gaps_in(routes, seen))
    when = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    text = summary(
        verdict, image=image, origin="127.0.0.1", messages=len(seen), when=when, notes=notes
    )
    (out / "zap-summary.md").write_text(text + "\n", "utf-8")
    (out / "zap-alerts.json").write_text(json.dumps(raw, indent=1) + "\n", "utf-8")
    print(text)
    return 0 if verdict.passed else 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--image", default=IMAGE, help="the ZAP image (default: the pinned one)")
    parser.add_argument("--out", type=Path, default=Path("zap-out"), help="report folder")
    parser.add_argument(
        "--accepted",
        type=Path,
        default=ACCEPTED,
        help="accepted Low alerts and notes on informational ones",
    )
    parser.add_argument(
        "--chromium", default=None, help="a Chromium to use instead of Playwright's own"
    )
    args = parser.parse_args(argv)
    try:
        return run(args.image, args.out, args.accepted, args.chromium)
    except AcceptedListError as error:
        print(f"zap_scan: {error}", file=sys.stderr)
        return 2
    except Exception:  # Docker, ZAP, the server or the walk: could not run, not a finding
        traceback.print_exc()
        print("zap_scan: the scan could not run (see above)", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
