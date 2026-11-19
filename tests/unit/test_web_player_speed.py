"""The player's speed kept for the next Listen page (#651): the cookie's reading, the route
that sets it, and the page that starts from it."""

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st
from test_web_listen import page_of
from test_web_player import make, server
from web_helpers import ORIGIN, anonymous, app_and_config, browser, program

from sci2audio.web.i18n import (
    PLAYER_MAX_SPEED,
    PLAYER_MIN_SPEED,
    PLAYER_SPEED_COOKIE,
    known_player_speed,
    player_speed_text,
)

ROUTE = "/api/v1/player/speed"
TIMES = "\u00d7"  # the multiplication sign


@pytest.mark.parametrize(
    ("text", "speed"),
    [
        ("1.07", 1.07),
        ("1", 1.0),
        ("0.5", 0.5),
        ("3.00", 3.0),
        ("1.234", 1.23),  # kept to 0.01
        ("1.235", 1.24),
        ("0.1", 0.5),  # the nearest limit
        ("12", 3.0),
        ("-2", 0.5),
        (" 1.5 ", 1.5),  # float() reads it as Python does
        (None, None),
        ("", None),
        ("fast", None),
        ("1,07", None),  # the cookie is written with a point only
        ("nan", None),
        ("inf", None),
        ("-inf", None),
        ("1" * 17, None),  # too long to be a speed
    ],
)
def test_the_cookie_is_read_rounded_and_bounded(text: str | None, speed: float | None) -> None:
    assert known_player_speed(text) == speed


@given(st.text(max_size=20) | st.floats().map(repr))
def test_any_cookie_gives_a_speed_in_range_or_none(text: str) -> None:
    speed = known_player_speed(text)
    if speed is not None:
        assert PLAYER_MIN_SPEED <= speed <= PLAYER_MAX_SPEED
        assert speed == round(speed, 2)
        assert known_player_speed(player_speed_text(speed)) == speed  # it reads back


def test_the_route_keeps_the_speed_in_an_httponly_cookie(tmp_path: Path) -> None:
    app, config = app_and_config(tmp_path)
    response = browser(app, config).put(ROUTE, json={"speed": 1.234}, headers={"Origin": ORIGIN})
    assert response.status_code == 200
    assert response.json() == {"speed": 1.23}
    cookie = response.headers["set-cookie"]
    assert cookie.startswith(f"{PLAYER_SPEED_COOKIE}=1.23;")
    attributes = {part.strip().lower() for part in cookie.split(";")[1:]}
    assert "httponly" in attributes
    assert "samesite=strict" in attributes
    assert "path=/" in attributes
    assert "max-age=31536000" in attributes


@pytest.mark.parametrize("speed", [0.5, 1, 3, 2.99])
def test_the_whole_range_is_kept(tmp_path: Path, speed: float) -> None:
    app, config = app_and_config(tmp_path)
    response = program(app, config).put(ROUTE, json={"speed": speed})
    assert response.status_code == 200
    assert response.json() == {"speed": speed}


@pytest.mark.parametrize(
    "body",
    [
        {"speed": 0.49},
        {"speed": 3.01},
        {"speed": 0},
        {"speed": -1},
        {"speed": True},  # strict: true is no speed (#295)
        {"speed": "1.5"},
        {"speed": None},
        {},
        {"speed": 1.5, "more": 1},
        [1.5],
    ],
)
def test_a_wrong_speed_is_refused_and_nothing_is_kept(tmp_path: Path, body: Any) -> None:
    app, config = app_and_config(tmp_path)
    response = program(app, config).put(ROUTE, json=body)
    assert response.status_code == 422
    assert response.json()["error"] == "invalid"
    assert "set-cookie" not in response.headers


def test_a_speed_that_is_not_a_finite_number_is_refused(tmp_path: Path) -> None:
    app, config = app_and_config(tmp_path)
    client = program(app, config)
    for text in ("NaN", "Infinity", "-Infinity", "1e999"):
        response = client.put(
            ROUTE, content=f'{{"speed": {text}}}', headers={"content-type": "application/json"}
        )
        assert response.status_code in (400, 422), text
        assert "set-cookie" not in response.headers


def test_the_route_needs_the_token(tmp_path: Path) -> None:
    app, _config = app_and_config(tmp_path)
    response = anonymous(app).put(ROUTE, json={"speed": 1.5})
    assert response.status_code == 401
    assert "set-cookie" not in response.headers


def _speed_on(page: str) -> dict[str, str]:
    box = re.search(r'<input type="text" id="speed-exact"[^>]*>', page)
    assert box is not None
    found = dict(re.findall(r'([a-z-]+)="([^"]*)"', box[0]))
    button = re.search(r'<span id="speed-now">([^<]*)</span>', page)
    assert button is not None
    found["button"] = button[1]
    found["pressed"] = ",".join(re.findall(r'data-speed="([0-9.]+)" aria-pressed="true"', page))
    return found


def test_the_listen_page_starts_from_the_kept_speed(tmp_path: Path) -> None:
    client, _config = server(tmp_path)
    with client:
        doc = make(client)["doc"]["id"]
        first = _speed_on(page_of(client, doc))
        assert first["value"] == "1.00"
        assert first["data-value"] == "1.00"
        assert first["aria-valuenow"] == "1.00"
        assert first["aria-valuemin"] == "0.50"
        assert first["aria-valuemax"] == "3.00"
        assert first["aria-valuetext"] == f"1.00{TIMES}"
        assert first["button"] == f"1.00{TIMES}"
        assert first["pressed"] == "1.00"
        kept = _speed_on(page_of(client, doc, **{"player-speed": "1.37"}))
        assert kept["value"] == "1.37"
        assert kept["button"] == f"1.37{TIMES}"
        assert kept["pressed"] == ""  # no usual speed is pressed for 1.37
        assert _speed_on(page_of(client, doc, **{"player-speed": "1.5"}))["pressed"] == "1.50"
        # a broken cookie is 1, one out of range the nearest limit
        assert _speed_on(page_of(client, doc, **{"player-speed": "<b>"}))["value"] == "1.00"
        assert _speed_on(page_of(client, doc, **{"player-speed": "9"}))["value"] == "3.00"
        german = page_of(client, doc, **{"player-speed": "1.37", "language": "de"})
        assert _speed_on(german)["value"] == "1,37"
        assert _speed_on(german)["button"] == f"1,37{TIMES}"
        assert "Geben Sie eine Zahl von 0,50 bis 3,00 ein, etwa 1,07." in german
        assert not math.isnan(float(kept["data-value"]))
