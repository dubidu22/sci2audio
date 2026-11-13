"""The judging part of the ZAP baseline scan (#12; D-367 to D-369): which alerts fail, which
an accepted entry covers, what counts as never scanned, and the accepted list's format.
The scan itself needs Docker and runs in `.github/workflows/zap.yml`."""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "zap_scan.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("zap_scan", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["zap_scan"] = module  # dataclasses look their module up by name
    spec.loader.exec_module(module)
    return module


zap = _load()

GOOD = """
[[accepted]]
rule = 10031
risk = "Low"
url = '/documents/[0-9a-f]{16}\\?category=.*'
reason = "Jinja2 escapes the value and CSP forbids inline script."
decision = "D-368"
"""


def alert(
    rule: int = 10031, risk: str = "Low", url: str = "/documents/0123456789abcdef?category=x"
):
    return zap.Alert(rule=rule, name="a rule", risk=risk, url=url)


def accepted(tmp_path: Path, text: str = GOOD) -> tuple:
    path = tmp_path / "accepted.toml"
    path.write_text(text, encoding="utf-8")
    return zap.load_accepted(path)


# --- judging -------------------------------------------------------------------------------


@pytest.mark.parametrize("risk", ["High", "Medium"])
def test_high_and_medium_always_fail(tmp_path: Path, risk: str) -> None:
    verdict = zap.judge([alert(risk=risk)], accepted(tmp_path))
    assert not verdict.passed
    assert [a.risk for a in verdict.failing] == [risk]


def test_a_low_alert_fails_unless_accepted(tmp_path: Path) -> None:
    assert not zap.judge([alert()], ()).passed
    verdict = zap.judge([alert()], accepted(tmp_path))
    assert verdict.passed
    assert [(a.rule, e.decision) for a, e in verdict.accepted] == [(10031, "D-368")]
    assert verdict.stale == []


def test_informational_never_fails() -> None:
    verdict = zap.judge([alert(risk="Informational")], ())
    assert verdict.passed
    assert len(verdict.informational) == 1


@pytest.mark.parametrize(
    "other",
    [
        alert(rule=10032),  # another rule
        alert(url="/documents/0123456789abcdef"),  # the pattern must match in full
        alert(url="/privacy?category=x"),  # another page
    ],
)
def test_an_entry_covers_only_its_rule_and_urls(tmp_path: Path, other) -> None:
    verdict = zap.judge([other], accepted(tmp_path))
    assert verdict.failing == [other]


def test_an_entry_that_matched_nothing_is_stale_but_does_not_fail(tmp_path: Path) -> None:
    verdict = zap.judge([], accepted(tmp_path))
    assert verdict.passed
    assert [e.rule for e in verdict.stale] == [10031]
    text = zap.summary(verdict, image="zap", origin="127.0.0.1", messages=3, when="now")
    assert "matched nothing" in text


def test_the_same_alert_twice_is_counted_once() -> None:
    verdict = zap.judge([alert(risk="High"), alert(risk="High")], ())
    assert len(verdict.failing) == 1


def test_failures_come_highest_risk_first() -> None:
    verdict = zap.judge([alert(risk="Low"), alert(risk="High"), alert(risk="Medium")], ())
    assert [a.risk for a in verdict.failing] == ["High", "Medium", "Low"]


def test_gaps_fail_the_scan_even_without_alerts() -> None:
    verdict = zap.judge([], (), ["GET /voice was never scanned"])
    assert not verdict.passed
    text = zap.summary(verdict, image="zap", origin="127.0.0.1", messages=0, when="now")
    assert "**Failed.**" in text
    assert "GET /voice was never scanned" in text


def test_the_summary_lists_each_kind() -> None:
    verdict = zap.judge([alert(risk="Medium"), alert(rule=10027, risk="Informational")], ())
    text = zap.summary(verdict, image="zap@sha256:x", origin="127.0.0.1", messages=9, when="now")
    assert text.startswith("# ZAP baseline scan\n\n**Failed.**")
    assert "| Medium | 10031 a rule | GET `/documents/0123456789abcdef?category=x` |" in text
    assert "| Informational | 10027 a rule |" in text
    assert "9 requests" in text


# --- alerts from ZAP --------------------------------------------------------------------------


def test_an_alert_from_zap_drops_the_origin() -> None:
    raw = {
        "pluginId": "10021",
        "name": "X-Content-Type-Options Header Missing",
        "risk": "Low",
        "url": "http://127.0.0.1:51234/static/app.js?v=1",
        "method": "GET",
        "param": "x-content-type-options",
        "evidence": "",
    }
    found = zap.Alert.from_zap(raw)
    assert (found.rule, found.risk, found.url) == (10021, "Low", "/static/app.js?v=1")


def test_an_alert_with_an_unknown_risk_is_refused() -> None:
    with pytest.raises(ValueError, match="unknown risk"):
        zap.Alert.from_zap({"pluginId": "1", "risk": "Critical", "url": "http://x/"})


# --- the accepted list ------------------------------------------------------------------------


def test_the_list_in_the_repository_loads() -> None:
    zap.load_accepted(zap.ACCEPTED)


@pytest.mark.parametrize(
    ("text", "message"),
    [
        (GOOD.replace('risk = "Low"', 'risk = "Medium"'), "only Low alerts can be accepted"),
        (GOOD.replace('risk = "Low"', 'risk = "High"'), "only Low alerts can be accepted"),
        (GOOD.replace('decision = "D-368"', 'decision = "soon"'), "decision must look like"),
        (GOOD.replace('decision = "D-368"\n', ""), "missing \\['decision'\\]"),
        (GOOD + 'note = "x"\n', "unknown \\['note'\\]"),
        (GOOD.replace("Jinja2 escapes the value and CSP forbids inline script.", "fine"), "why"),
        (GOOD.replace("rule = 10031", 'rule = "10031"'), "ZAP rule number"),
        (GOOD.replace("rule = 10031", "rule = true"), "ZAP rule number"),
        (GOOD.replace("[0-9a-f]", "[0-9a-f"), "not a regular expression"),
        ("[other]\nx = 1\n", "unknown table"),
        ("accepted = 3\n", "array of tables"),
        ("[[accepted]\n", "accepted.toml"),
    ],
)
def test_a_bad_list_is_refused_with_a_clear_message(
    tmp_path: Path, text: str, message: str
) -> None:
    with pytest.raises(zap.AcceptedListError, match=message):
        accepted(tmp_path, text)


def test_a_missing_list_is_refused(tmp_path: Path) -> None:
    with pytest.raises(zap.AcceptedListError, match=r"no-such\.toml"):
        zap.load_accepted(tmp_path / "no-such.toml")


def test_a_broken_list_stops_the_script_before_anything_starts(tmp_path: Path) -> None:
    path = tmp_path / "accepted.toml"
    path.write_text(GOOD.replace('"Low"', '"High"'), encoding="utf-8")
    assert zap.main(["--accepted", str(path), "--out", str(tmp_path / "out")]) == 2
    assert not (tmp_path / "out").exists()


# --- coverage ---------------------------------------------------------------------------------


def route(template: str, *, page: bool = False, method: str = "GET"):
    pattern = re.compile(re.sub(r"\{[^}]+\}", "[^/]+", template))
    return zap.Route(method, template, pattern, page)


EVERYTHING_ELSE = [
    zap.Seen("GET", "/start", 303, None),
    zap.Seen("GET", "/", 401, "en"),
    zap.Seen("GET", "/", 401, "de"),
    zap.Seen("GET", "/", 421, None),
]


def test_nothing_missing_when_every_route_and_language_was_seen() -> None:
    routes = [route("/voice", page=True), route("/api/v1/jobs/{job_id}", method="POST")]
    seen = [
        zap.Seen("GET", "/voice", 200, "en"),
        zap.Seen("GET", "/voice", 200, "de"),
        zap.Seen("POST", "/api/v1/jobs/abc", 202, None),
        *EVERYTHING_ELSE,
    ]
    assert zap.gaps_in(routes, seen) == []


def test_a_route_never_requested_is_a_gap() -> None:
    routes = [route("/api/v1/voices"), route("/api/v1/voices", method="POST")]
    seen = [zap.Seen("GET", "/api/v1/voices", 200, None), *EVERYTHING_ELSE]
    assert zap.gaps_in(routes, seen) == ["POST /api/v1/voices was never scanned"]


def test_a_page_seen_in_one_language_only_is_a_gap() -> None:
    seen = [zap.Seen("GET", "/privacy", 200, "en"), *EVERYTHING_ELSE]
    assert zap.gaps_in([route("/privacy", page=True)], seen) == [
        "GET /privacy was not seen in 'de'"
    ]


def test_the_middlewares_own_answers_must_be_seen() -> None:
    assert zap.gaps_in([], []) == [
        "the start link (303 with the cookie) was never scanned",
        "the 401 page in English was never scanned",
        "the 401 page in German was never scanned",
        "the 421 answer to a wrong Host was never scanned",
    ]


def test_every_route_of_the_app_is_listed(tmp_path: Path) -> None:
    from web_helpers import app_and_config

    app, _ = app_and_config(tmp_path)
    routes = {(r.method, r.template): r.page for r in zap.routes_of(app)}
    assert routes[("GET", "/documents/{document_id}/listen")] is True
    assert routes[("GET", "/privacy")] is True
    assert routes[("GET", "/language")] is False  # a redirect, not a page
    assert routes[("POST", "/api/v1/documents")] is False
    assert routes[("DELETE", "/api/v1/documents/{document_id}/chunks")] is False
    assert ("GET", "/static/…") in routes
    assert not any(method == "HEAD" for method, _ in routes)
    pages = {template for (method, template), page in routes.items() if page}
    assert pages == {
        "/",
        "/documents/{document_id}",
        "/jobs/{job_id}",
        "/documents/{document_id}/listen",
        "/voice",
        "/privacy",
    }
    assert len(routes) >= 25  # every API route too (29 on 13 Nov 2026)


def test_a_message_from_zap_becomes_what_was_seen() -> None:
    message = {
        "requestHeader": "GET http://127.0.0.1:5/documents/x?y=1 HTTP/1.1\r\nHost: 127.0.0.1:5\r\n",
        "responseHeader": "HTTP/1.1 404 Not Found\r\ncontent-type: text/html\r\n",
        "responseBody": '<!doctype html>\n<html lang="de">\n<head>',
    }
    assert zap._seen(message) == zap.Seen("GET", "/documents/x", 404, "de")
