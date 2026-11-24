"""The interface in English and German and the privacy page (#79, D-288 to D-293).

- The two string tables mirror each other: same keys, same plural forms, same placeholders;
  every key used is there and every key is used; German is really German (D-289).
- The page language: the switch's cookie, else `Accept-Language`, else English; the switch
  only ever sends the browser back to a path on this server (D-288).
- Every page renders in German without an English sentence of the table on it.
- The privacy page says what the code does: each of its points is checked here against the
  server (D-293).
"""

from __future__ import annotations

import ast
import html
import json
import re
import string
from datetime import UTC, datetime
from importlib.resources import files
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request
from web_helpers import (
    ORIGIN,
    anonymous,
    app_and_config,
    browser,
    offline,  # noqa: F401 - fixture
    paper_bytes,
    upload,
    wait,
)

import sci2audio.web
from sci2audio.app import updates
from sci2audio.app.settings import LETTER_PACES
from sci2audio.textprep import BUILT_IN_STEPS as BUILT_IN
from sci2audio.textprep import Category
from sci2audio.voices import PACKS, VOICES, download_plan
from sci2audio.web import exports, i18n, library, pages, player, server, window
from sci2audio.web.api import REDIRECTS, plan_hosts
from sci2audio.web.config import HOST
from sci2audio.web.i18n import (
    COOKIE,
    LANGUAGES,
    from_accept_language,
    language_of,
    load_table,
    local_path,
    strings,
)
from sci2audio.web.jobs import JobKind, JobState
from sci2audio.web.launch import uvicorn_config

pytestmark = pytest.mark.usefixtures("offline")

WEB = files("sci2audio.web")
SOURCE = Path(sci2audio.web.__file__).parent
EN = load_table("en")
DE = load_table("de")

# German values that are rightly the same as the English ones
SAME_IN_GERMAN = {
    "common.app",  # the name
    "common.language_en",  # each language named in its own language
    "common.language_de",
    "common.megabytes",
    "common.kilobytes",
    "js.percent",
    "document.title",  # only the document's name
    "document.problem",  # a step id and the app's words
    "check.chapter_line",  # only the chapter's title
    "privacy.cookies_title",  # "Cookies"
    "voice.letter_pace_normal",  # "Normal" (#295)
    "listen.speed_value",  # the number and the times sign, the number in the page language (#152)
    "library.minutes",  # "min" (#389)
    "export.ris",  # "Zotero", the program the file is for (#399)
    "export.md",  # "Obsidian"
}


def base(key: str) -> str:
    """A plural form's key without its form."""
    return re.sub(r"\.(one|other)$", "", key)


def placeholders(text: str) -> set[str]:
    return {name for _, name, _, _ in string.Formatter().parse(text) if name}


@pytest.fixture
def server_(tmp_path: Path) -> tuple[FastAPI, Any]:
    return app_and_config(tmp_path)


def client_in(server_: tuple[FastAPI, Any], language: str | None) -> TestClient:
    app, config = server_
    client = browser(app, config)
    client.headers["Origin"] = ORIGIN
    if language is not None:
        client.cookies.set(COOKIE, language)
    return client


# --- the two tables (D-289) -------------------------------------------------------------


def test_both_tables_have_the_same_keys_and_placeholders() -> None:
    assert set(EN) - set(DE) == set(), "missing from strings/de.toml"
    assert set(DE) - set(EN) == set(), "missing from strings/en.toml"
    for key in EN:
        assert placeholders(EN[key]) == placeholders(DE[key]), key


def test_plurals_have_one_and_other_and_count_with_n() -> None:
    for table in (EN, DE):
        forms: dict[str, set[str]] = {}
        for key in table:
            if base(key) != key:
                forms.setdefault(base(key), set()).add(key.rsplit(".", 1)[1])
        for key, found in forms.items():
            assert found == {"one", "other"}, key
            assert key not in table, f"{key} is both a text and a plural"
            assert "n" in placeholders(table[f"{key}.other"]), key
            assert "n" not in placeholders(table[f"{key}.one"]), key  # it says 1


def resource_texts() -> dict[str, str]:
    texts = {}
    for folder in ("templates", "static"):
        for item in (WEB / folder).iterdir():
            if item.is_file():  # static/fonts/ holds the bundled fonts (#385)
                texts[f"{folder}/{item.name}"] = item.read_text(encoding="utf-8")
    return texts


def error_kinds() -> set[str]:
    """Every error kind the server, its pages or a job can send to the page."""
    code = "\n".join(path.read_text(encoding="utf-8") for path in SOURCE.glob("*.py"))
    kinds = set(re.findall(r'ApiError\(\s*\d+,\s*"([a-z-]+)"', code))
    kinds |= set(re.findall(r'_error\(\s*\d+,\s*"([a-z-]+)"', code))
    kinds |= set(re.findall(r'JobFailure\(\s*"([a-z-]+)"', code))
    tasks = (SOURCE / "tasks.py").read_text(encoding="utf-8")
    kinds |= set(re.findall(r'^\s*\("([a-z-]+)",\s*\w+', tasks, re.M))  # tasks._KINDS
    kinds |= set(re.findall(r'^\s*kind = "([a-z-]+)"', code, re.M))  # documents' errors
    kinds |= set(server._STATUS_KINDS.values()) | {"error", "invalid", "disk-full"}
    return kinds


def used_keys() -> set[str]:
    texts = resource_texts()
    found: set[str] = set()
    templates = "".join(text for name, text in texts.items() if name.startswith("templates"))
    found |= set(re.findall(r"""\bt\(\s*'([a-z_.-]+[a-z])'""", templates))
    found |= {f"make.{key}" for key in re.findall(r"'(needs_[a-z]+)'", templates)}
    found |= {f"common.language_{code}" for code in LANGUAGES}
    for name in ("work", "output", "settings", "voice"):  # privacy.html's folder list
        found |= {f"privacy.{name}", f"privacy.{name}_label"}
    found |= {f"job.state_{s}" for s in JobState}
    found |= {f"job.title_{kind}" for kind in JobKind}
    for script in (texts["static/app.js"], texts["static/player.js"]):
        found |= set(re.findall(r"""tr\(\s*["`']([a-z_.]+)["`']""", script))
    # the player's reasons, named where they are raised (#78)
    found |= set(
        re.findall(
            r"""PlayerError\(\s*["']([a-z_.]+)["']""",
            Path(player.__file__).read_text(encoding="utf-8"),
        )
    )
    found |= {f"make.needs_{key}" for key in ("analysis", "voice", "update", "chapters")}
    found |= {f"category.{category}" for category in Category}
    found |= {f"accent.{voice.language}" for voice in VOICES}
    found |= {f"pack.{language}" for language in PACKS}  # pages names packs (D-468)
    found |= {f"setup.pack_{language}" for language in PACKS}
    found |= {f"error.{kind}" for kind in error_kinds()}
    found |= {f"voice.letter_pace_{pace}" for pace in LETTER_PACES}  # pages names each pace
    found |= {f"library.state_{key}" for key in pages.CHIPS}  # a chip's word (#389)
    found |= {f"library.when_{kind}" for kind in ("today", "yesterday")}  # library.when
    found |= {f"library.{kind}s" for kind in pages.CAPTURE_KINDS}  # a flag strip's words (#418)
    for module in (pages, i18n, window, exports):
        path = Path(str(module.__file__))
        source = path.read_text(encoding="utf-8")
        found |= set(re.findall(r"""\b(?:t|s|self\.t)\(\s*f?["']([a-z_.-]+[a-z])["']""", source))
    found |= {key for key in EN if key.startswith("phase.")}
    found |= {"voice.accent_female", "voice.accent_male", "common.language", "common.app"}
    found |= {"common.decimal"}  # i18n.Strings.number and the script
    found |= {f"redirect.{host}" for host in REDIRECTS}
    # the captures (#397): named by type in listen.html and player.js, and why capturing is
    # off on the Listen page
    kinds = ("note", "quote", "mark")
    found |= {f"capture.{kind}" for kind in kinds}
    found |= {f"capture.{word}_{kind}" for word in ("saved", "removed", "kind") for kind in kinds}
    found |= {f"capture.saved_{kind}_page" for kind in kinds}  # with a PDF's page (#888)
    found |= {"capture.unreadable", "capture.markers", "capture.unsaved"}
    # why the Captures page shows none of a document's captures (#398), named in captures.html
    found |= {"captures.unreadable", "captures.markers", "captures.unsaved"}
    return found


def test_every_string_used_is_in_both_tables_and_every_string_is_used() -> None:
    used = used_keys()
    for language, table in (("en", EN), ("de", DE)):
        keys = {base(key) for key in table}
        assert used - keys == set(), f"missing from strings/{language}.toml"
        assert keys - used == set(), f"in strings/{language}.toml but not used"


def test_every_error_kind_has_a_sentence() -> None:
    kinds = error_kinds()
    assert {"busy", "output-exists", "voice-failed", "wrong-origin", "store-failed"} <= kinds
    for kind in kinds:
        assert f"error.{kind}" in EN, kind
        assert f"error.{kind}" in DE, kind


def test_german_is_not_english_left_untranslated() -> None:
    same = {key for key in EN if EN[key] == DE[key] and len(EN[key]) > 2}
    assert same <= SAME_IN_GERMAN, sorted(same - SAME_IN_GERMAN)


def test_german_typography() -> None:
    for key, text in DE.items():
        assert '"' not in text, key  # „…“, never straight quotes
        assert "”" not in text, key  # the English closing quote
        assert "'" not in text, key  # the typographic apostrophe instead
        assert "..." not in text, key  # the ellipsis character
        assert text.count("„") == text.count("“"), key
        assert re.search(r"\d (MB|KB|Byte|%)", text) is None, key  # no-break space
    for key, text in EN.items():
        assert '"' not in text, key
        assert re.search(r"\d (MB|KB|bytes?|%)", text) is None, key
    assert DE["common.decimal"] == ","
    assert EN["common.decimal"] == "."


def test_german_addresses_the_reader_as_sie() -> None:
    words = set(re.findall(r"\b\w+\b", " ".join(DE.values()).lower()))
    assert not words & {"du", "dein", "deine", "deinen", "deiner", "dir", "dich"}
    assert "sie" in words


# --- plurals, numbers, sizes (D-290) -----------------------------------------------------


@pytest.mark.parametrize(
    ("language", "one", "many"),
    [
        ("en", "X: 1 change", "X: 2 changes"),
        ("de", "X: 1 Änderung", "X: 2 Änderungen"),
    ],
)
def test_plurals(language: str, one: str, many: str) -> None:
    s = strings(language)
    assert s("check.category_changes", label="X", n=1) == one
    assert s("check.category_changes", label="X", n=2) == many
    assert s("check.category_changes", label="X", n=0).startswith("X: 0")


def test_numbers_and_sizes() -> None:
    en, de = strings("en"), strings("de")
    assert en.number(1.25) == "1.25"
    assert de.number(1.25) == "1,25"
    assert en.number(1.0) == "1"
    assert de.number(0.9) == "0,9"
    assert de("voice.speed_value", value=de.number(1.25)) == "1,25-fach"
    assert en.size(1) == "1\u00a0byte"
    assert en.size(512) == "512\u00a0bytes"
    assert en.size(48_000) == "48\u00a0KB"
    assert en.size(355_000_000) == "355\u00a0MB"
    assert en.size(1_250_000) == "1.2\u00a0MB"
    assert de.size(1_250_000) == "1,2\u00a0MB"
    assert de.size(512) == "512\u00a0Byte"


def test_the_script_strings_cannot_end_the_data_block() -> None:
    odd = "</script><script>alert(1)</script> <!--<script> & -->"
    s = i18n.Strings("en", {**EN, "js.lost": odd})
    block = s.script_json()
    assert not set("<>&") & set(block)  # nothing in it can change how the page parses
    assert json.loads(block)["js.lost"] == odd
    assert json.loads(i18n.data_block({"t": odd})) == {"t": odd}


# --- the page language (D-288) ----------------------------------------------------------


@pytest.mark.parametrize(
    ("header", "language"),
    [
        (None, None),
        ("", None),
        ("de", "de"),
        ("de-DE,de;q=0.9,en;q=0.8", "de"),
        ("de-AT", "de"),
        ("en-US,de;q=0.5", "en"),
        ("fr, de;q=0.5", "de"),
        ("fr-FR, it", None),
        ("*", None),
        ("en;q=0.2, de;q=0.7", "de"),
        ("de;q=0, en", "en"),
        ("DE-ch", "de"),
        ("de;q=abc, en", "en"),
        ("de;q=1.0.0, en;q=0.5", "en"),
        (";;,,", None),
        ("x" * 5000, None),
    ],
)
def test_the_browsers_languages(header: str | None, language: str | None) -> None:
    assert from_accept_language(header) == language


def request_with(headers: dict[str, str]) -> Request:
    raw = [(name.lower().encode(), value.encode()) for name, value in headers.items()]
    return Request({"type": "http", "headers": raw})


def test_only_a_known_language_reaches_the_cookie() -> None:
    assert i18n.known_language("de") == "de"
    assert i18n.known_language("en") == "en"
    for text in (None, "", "fr", "DE", "de;", "de\r\nSet-Cookie: x=1", "en "):
        assert i18n.known_language(text) is None


def test_the_cookie_wins_and_english_is_the_default() -> None:
    assert language_of(request_with({})) == "en"
    assert language_of(request_with({"Accept-Language": "de"})) == "de"
    both = {"Accept-Language": "de", "Cookie": f"{COOKIE}=en"}
    assert language_of(request_with(both)) == "en"
    assert language_of(request_with({"Cookie": f"{COOKIE}=de"})) == "de"
    assert language_of(request_with({"Cookie": f"{COOKIE}=fr", "Accept-Language": "de"})) == "de"


@pytest.mark.parametrize(
    ("back", "where"),
    [
        ("/documents/0123456789abcdef", "/documents/0123456789abcdef"),
        ("/jobs/x-script-1?a=b", "/jobs/x-script-1?a=b"),
        ("/", "/"),
        (None, "/"),
        ("", "/"),
        ("//evil.test/", "/"),
        ("/\\evil.test", "/"),
        ("https://evil.test/", "/"),
        ("evil.test", "/"),
        ("javascript:alert(1)", "/"),
        ("/a\nb", "/"),
        ("/a\tb", "/"),
    ],
)
def test_the_switch_goes_back_only_to_this_server(back: str | None, where: str) -> None:
    assert local_path(back) == where


def test_the_switch_sets_its_own_cookie_and_goes_back(server_: tuple[FastAPI, Any]) -> None:
    client = client_in(server_, None)
    response = client.get(
        "/language", params={"language": "de", "back": "/voice"}, follow_redirects=False
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/voice"
    cookie = response.headers["set-cookie"]
    assert cookie.startswith(f"{COOKIE}=de;")
    assert "Max-Age=31536000" in cookie
    assert "SameSite=strict" in cookie
    assert "Path=/" in cookie
    assert "HttpOnly" in cookie
    assert len(response.headers.get_list("set-cookie")) == 1  # the start cookie untouched
    page = client.get("/voice")
    assert '<html lang="de">' in page.text
    assert "<h1>Stimme einrichten</h1>" in page.text


def test_the_switch_refuses_an_unknown_language_and_foreign_targets(
    server_: tuple[FastAPI, Any],
) -> None:
    client = client_in(server_, None)
    response = client.get(
        "/language",
        params={"language": "fr", "back": "//evil.test/"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/"
    assert "set-cookie" not in response.headers


def test_the_switch_is_guarded_like_every_page(server_: tuple[FastAPI, Any]) -> None:
    app, config = server_
    params = {"language": "de", "back": "/"}
    # without the start cookie or token: a link from another site carries no SameSite=Strict
    # cookie
    assert anonymous(app).get("/language", params=params).status_code == 401
    # with the cookie, but from another site
    client = browser(app, config)
    client.headers["Sec-Fetch-Site"] = "cross-site"
    assert client.get("/language", params=params).status_code == 403
    del client.headers["Sec-Fetch-Site"]
    client.headers["Origin"] = "http://evil.test"
    assert client.get("/language", params=params).status_code == 403
    for refused in (anonymous(app), client):
        assert COOKIE not in refused.cookies


def test_the_language_cookie_grants_nothing(server_: tuple[FastAPI, Any]) -> None:
    app, config = server_
    client = anonymous(app)
    client.cookies.set(COOKIE, "de")
    assert client.get("/").status_code == 401
    assert config.cookie_name != COOKIE


@pytest.mark.parametrize(
    ("cookie", "accept", "language"),
    [
        (None, None, "en"),
        ("de", None, "de"),
        (None, "de-DE,de;q=0.9", "de"),
        ("en", "de", "en"),
        ("fr", "de", "de"),
    ],
)
def test_the_page_without_the_start_cookie_is_in_the_readers_language(
    server_: tuple[FastAPI, Any], cookie: str | None, accept: str | None, language: str
) -> None:
    """The 401 page someone sees before the start link is the only page outside the
    templates; it follows the same choice of language (#142)."""
    app, _ = server_
    client = anonymous(app)
    if cookie is not None:
        client.cookies.set(COOKIE, cookie)
    headers = {"Accept-Language": accept} if accept else {}
    for path in ("/", "/start?token=wrong", "/privacy"):
        response = client.get(path, headers=headers)
        assert response.status_code == 401, path
        assert f'<html lang="{language}">' in response.text
        table = load_table(language)
        assert html.escape(table["error.no-token"]) in response.text
        assert f"<title>{table['common.app']}</title>" in response.text
    # what a program reads stays one machine-readable English answer
    api = client.get("/api/v1/jobs", headers=headers)
    assert api.status_code == 401
    assert api.json()["error"] == "no-token"
    assert "terminal" in api.json()["message"]


def test_an_unknown_key_names_itself() -> None:
    with pytest.raises(KeyError, match="nope"):
        strings("en").t("nope")
    with pytest.raises(KeyError, match="nope"):
        strings("de").t("nope", n=2)


def test_the_switch_is_on_settings_linked_from_every_page_and_marks_the_language(
    server_: tuple[FastAPI, Any],
) -> None:
    # D-673 (amends D-288): the switch moved from every page's header to Settings (#388)
    app, _ = server_
    client = client_in(server_, "de")
    for name, page in pages_of(client, app).items():
        rail = page.split('<nav class="rail"')[1].split("</nav>")[0]
        assert '<a href="/settings"' in rail, name
        assert 'action="/language"' not in rail, name
    page = client.get("/settings").text
    assert '<form method="get" action="/language" id="languages">' in page
    assert '<input type="hidden" name="back" value="/settings">' in page
    assert re.search(r'value="en" lang="en" aria-pressed="false">English</button>', page)
    assert re.search(r'value="de" lang="de" aria-pressed="true">Deutsch</button>', page)
    assert '<h2 id="language-head">Sprache der Oberfläche</h2>' in page


# --- every page in German ------------------------------------------------------------------


ENGLISH_SENTENCES = sorted(
    {text for key, text in EN.items() if DE[key] != text and len(text) > 12},
    key=len,
    reverse=True,
)


def english_left(page: str) -> list[str]:
    """English sentences of the table on a German page, outside the parts the app wrote."""
    page = re.sub(r'<script id="strings".*?</script>', "", page, flags=re.S)
    page = re.sub(r'<[^>]* lang="en"[^>]*>.*?</[a-z]+>', "", page, flags=re.S)
    page = re.sub(r'lang="en"[^>]*>English</button>', "", page)
    text = html.unescape(re.sub(r"<[^>]+>", " ", page))
    found = []
    for sentence in ENGLISH_SENTENCES:
        head = re.split(r"\{[a-z_]+\}", sentence)[0].strip()  # the part before a value
        if len(head) > 8 and head in text:
            found.append(sentence)
    return found


def pages_of(client: TestClient, app: FastAPI) -> dict[str, str]:
    doc = upload(client, paper_bytes(), "paper.pdf")
    before = client.get(f"/documents/{doc['id']}").text
    job = client.post(
        "/api/v1/jobs", json={"kind": "script", "document": doc["id"], "settings": {}}
    ).json()
    assert wait(client, job["id"])["state"] == "done"
    return {
        "start": client.get("/").text,
        "document before its analysis": before,
        "document": client.get(f"/documents/{doc['id']}").text,
        "script job": client.get(f"/jobs/{job['id']}").text,
        "voice": client.get("/voice").text,
        "privacy": client.get("/privacy").text,
        "settings": client.get("/settings").text,
        "not found": client.get("/jobs/nothing").text,
    }


def test_every_page_in_german(server_: tuple[FastAPI, Any]) -> None:
    app, _ = server_
    client = client_in(server_, "de")
    for name, page in pages_of(client, app).items():
        assert '<html lang="de">' in page, name
        assert english_left(page) == [], name
        block = re.search(r'<script id="strings" type="application/json">(.*?)</script>', page)
        assert block is not None
        script = json.loads(block[1])
        assert script["js.lost"] == DE["js.lost"], name
        assert script["common.decimal"] == ","


def test_every_page_in_english_is_unchanged_by_german(server_: tuple[FastAPI, Any]) -> None:
    app, _ = server_
    client = client_in(server_, None)
    for name, page in pages_of(client, app).items():
        assert '<html lang="en">' in page, name
        assert "Sprache" not in page, name


def test_the_browser_language_chooses_without_a_cookie(server_: tuple[FastAPI, Any]) -> None:
    client = client_in(server_, None)
    client.headers["Accept-Language"] = "de-DE,de;q=0.9,en;q=0.8"
    assert '<html lang="de">' in client.get("/").text
    client.headers["Accept-Language"] = "fr-FR"
    assert '<html lang="en">' in client.get("/").text


def test_the_documents_words_and_the_apps_words_are_marked(
    server_: tuple[FastAPI, Any],
) -> None:
    app, _ = server_
    page = pages_of(client_in(server_, "de"), app)["document"]
    # a reason, then page, chapter and status (#391)
    assert re.search(
        r'<td lang="en">[^<]+</td><td class="where">[^<]*</td><td lang="en">[^<]*</td>'
        r"<td>angewendet</td>",
        page,
    )
    # as printed, on one line as the report quotes it (#118)
    assert '<td class="text printed" lang="en">(Smith, 2020)</td>' in page
    assert '<td class="text read gone">nicht vorgelesen</td>' in page  # the interface's words
    assert re.search(r'<label for="chapter-0" class="ct" lang="en">', page)
    assert 'id="preview-text" name="text" lang="en"' in page or 'id="preview"' not in page


def test_a_failed_job_is_explained_in_german_with_the_apps_words(
    server_: tuple[FastAPI, Any],
) -> None:
    s = strings("de")
    shown = pages.failure(s, {"error": "busy", "message": "job x is working on this document"})
    assert shown == {"reason": DE["error.busy"], "details": "job x is working on this document"}
    unknown = pages.failure(s, {"error": "new-kind", "message": "words"})
    assert unknown == {"reason": "words", "details": ""}
    assert pages.failure(s, None) is None


# --- the privacy page: every point checked against the code (D-293) -------------------------


def test_the_privacy_page_is_linked_from_every_page_and_the_voice_consent(
    server_: tuple[FastAPI, Any],
) -> None:
    app, _ = server_
    for language in ("en", "de"):
        client = client_in(server_, language)
        for name, page in pages_of(client, app).items():
            rail = page.split('<nav class="rail"')[1].split("</nav>")[0]
            assert '<a href="/privacy"' in rail, (language, name)
        voice = client.get("/voice").text
        assert voice.index('href="/privacy"') < voice.index('id="voice-consent"')


def test_the_privacy_page_lists_the_hosts_and_folders_of_this_server(
    server_: tuple[FastAPI, Any],
) -> None:
    _, config = server_
    for language in ("en", "de"):
        page = client_in(server_, language).get("/privacy").text
        hosts = re.search(r'<ul aria-labelledby="privacy-hosts">(.*?)</ul>', page, re.S)
        assert hosts is not None
        listed = [html.unescape(host) for host in re.findall(r"<li>([^<]*)</li>", hosts[1])]
        plan = download_plan()
        expected = plan_hosts([file.url for file in plan.files])
        assert listed[: len(expected) - len(REDIRECTS)] == expected[: -len(REDIRECTS)]
        table = load_table(language)
        assert listed[-len(REDIRECTS) :] == [
            table[f"redirect.{host}"] for host in sorted(REDIRECTS)
        ]
        for folder in (
            config.work_root,
            config.output_folder,
            config.config_file,
            config.models_dir,
        ):
            assert f"<code>{folder}</code>" in page, folder
        assert 'href="/voice"' in page


# Modules that open connections, and calls that do so without importing one of them
NETWORK_MODULES = (
    "aiohttp",
    "ftplib",
    "http.client",
    "http.server",
    "httpx",
    "imaplib",
    "poplib",
    "requests",
    "smtplib",
    "socket",
    "socketserver",
    "ssl",
    "telnetlib",
    "urllib.request",
    "urllib3",
    "websocket",
    "websockets",
    "xmlrpc",
)
NETWORK_CALLS = frozenset(
    {"create_connection", "getaddrinfo", "open_connection", "start_server", "urlopen"}
)


def _network_module(name: str) -> bool:
    return any(name == m or name.startswith(m + ".") for m in NETWORK_MODULES)


def network_uses(source: str) -> list[str]:
    """Every import of a network module and every network call in `source`, found in its
    syntax tree: `from urllib import request`, `import json, requests`, an import inside a
    function and `importlib.import_module("requests")` count as much as a plain import."""
    found = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found += [a.name for a in node.names if _network_module(a.name)]
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            names = [node.module] + [f"{node.module}.{a.name}" for a in node.names]
            found += [name for name in names if _network_module(name)]
        elif isinstance(node, ast.Call):
            called = node.func
            name = called.attr if isinstance(called, ast.Attribute) else getattr(called, "id", "")
            if name in ("import_module", "__import__") and node.args:
                first = node.args[0]
                if isinstance(first, ast.Constant) and isinstance(first.value, str):
                    found += [first.value] if _network_module(first.value) else []
            elif name in NETWORK_CALLS:
                found.append(f"{name}()")
    return found


@pytest.mark.parametrize(
    "source",
    [
        "import requests",
        "import json, requests",
        "from urllib import request",
        "from http import client",
        "import ssl",
        "def f():\n    import socket",
        "import importlib\nimportlib.import_module('requests')",
        "__import__('httpx')",
        "import asyncio\nasyncio.open_connection('example.org', 80)",
        "from urllib.request import urlopen",
    ],
)
def test_the_network_guard_sees_every_way_in(source: str) -> None:
    assert network_uses(source), source


@pytest.mark.parametrize(
    "source",
    ["import json", "from urllib.parse import urlsplit", "import asyncio\nasyncio.sleep(1)"],
)
def test_the_network_guard_lets_the_rest_pass(source: str) -> None:
    assert network_uses(source) == []


def test_what_the_privacy_page_says_is_what_the_code_does(tmp_path: Path) -> None:
    """Point by point: if one of these fails, the code changed and the page must too."""
    # 1 and 2: the only network code is the voice download and the update check the person
    # turns on (tests/unit/test_*_network*, test_app_updates, the `offline` fixture
    # everywhere); the voice runs with Hugging Face offline
    from sci2audio.voices.runtime import ENVIRONMENT

    assert ENVIRONMENT["HF_HUB_OFFLINE"] == "1"
    package = Path(sci2audio.__file__).parent
    networked = {
        path.relative_to(package).as_posix()
        for path in package.rglob("*.py")
        if network_uses(path.read_text(encoding="utf-8"))
    }
    # launch opens the 127.0.0.1 socket; testing refuses connections in tests
    assert networked <= {
        "voices/download.py",
        "app/updates.py",
        "web/launch.py",
        "testing/text_steps.py",
    }
    # 2b: the update check is off until turned on, asks one host, sends two headers
    assert updates.UpdateState().enabled is False
    assert updates.RELEASES_URL.startswith("https://api.github.com/")
    assert updates.HEADERS == {"User-Agent": "sci2audio", "Accept": "application/vnd.github+json"}
    # 2c: text-step plugins are other people's code with the network open, not sandboxed;
    # --no-plugins keeps them out of a command-line job, uninstalling out of the interface
    from sci2audio import cli
    from sci2audio.textprep.plugins import PLUGIN_GROUP

    assert '"--no-plugins"' in Path(cli.__file__).read_text(encoding="utf-8")
    for table, network, sandbox, restart in (
        (EN, "network", "sandbox", "restart"),
        (DE, "Netz", "Sandbox", "neu starten"),
    ):
        point = table["privacy.plugins"]
        assert PLUGIN_GROUP in point
        assert "--no-plugins" in point
        assert network in point
        assert sandbox in point
        # plugins load once, when sci2audio starts (#696)
        assert restart in point
        assert "`" not in point  # the page shows no Markdown (#696)
    assert "started" in EN["privacy.plugins_installed"]
    assert "Start" in DE["privacy.plugins_installed"]
    # "without even loading them": --no-plugins gives a runner of the built-in steps (#689)
    import io

    from sci2audio.app import JobSettings
    from sci2audio.textprep import BUILT_IN_STEPS

    env = cli.CliEnv(io.StringIO(), io.StringIO(), input, interactive=False, live=False)
    assert list(env.job_runner(JobSettings(plugins=False)).steps) == list(BUILT_IN_STEPS)
    for table in (EN, DE):
        assert {"“sci2audio”", "„sci2audio“"} & set(
            re.findall(r"[“„]sci2audio[”“]", table["privacy.updates"])
        )
    # 3: FastAPI's telemetry is off in code (D-195; test_web_security proves nothing records)
    assert dict.fromkeys(server.TELEMETRY_OFF, False) == server.TELEMETRY_OFF
    assert set(server.TELEMETRY_OFF) >= {"tracing", "metrics", "logs", "auto_configure"}
    # 4: 127.0.0.1 only, no access log, nothing from outside (test_web_pages), no docs pages
    assert HOST == "127.0.0.1"
    assert uvicorn_config(FastAPI()).access_log is False
    # 6: the cookies: the start cookie is the port's; the Settings page's five cookies hold
    # a language, an appearance, the announcements, the keyboard shortcuts (#394) and the
    # capture sounds (#397), each one of its listed values (D-671)
    assert COOKIE == "sci2audio-language"
    assert set(LANGUAGES) == {"en", "de"}
    assert (i18n.THEME_COOKIE, i18n.THEMES) == ("sci2audio-theme", ("system", "light", "dark"))
    assert (i18n.ANNOUNCE_COOKIE, i18n.ANNOUNCE) == ("sci2audio-announce", ("off", "on"))
    assert (i18n.KEYS_COOKIE, i18n.KEYS) == ("sci2audio-keys", ("on", "off"))
    assert (i18n.SOUNDS_COOKIE, i18n.SOUNDS) == ("sci2audio-sounds", ("on", "off"))
    pages_source = Path(pages.__file__).read_text(encoding="utf-8")
    assert pages_source.count("response.set_cookie(") == 2  # the language's; Settings' loop
    assert "at most six cookies" in EN["privacy.cookies"]
    assert "höchstens sechs Cookies" in DE["privacy.cookies"]
    # 7: the working folder's small records for the library and the rail (#389): when each
    # document was last opened, what its file says about itself, where listening stopped;
    # each written into the document's own working folder and nowhere else
    assert (library.OPENED, library.ABOUT, player.POSITION) == (
        "opened.json",
        "about.json",
        "position.json",
    )
    work = tmp_path / "work" / "fedcba9876543210"
    work.mkdir(parents=True)
    library.write_opened(work, datetime(2026, 11, 16, tzinfo=UTC))
    library.write_about(work, library.About("A title", ("A. Writer",), 3))
    written = {p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*") if p.is_file()}
    assert written == {f"work/fedcba9876543210/{name}" for name in ("opened.json", "about.json")}
    sources = {
        name: (SOURCE / name).read_text(encoding="utf-8") for name in ("pages.py", "tasks.py")
    }
    assert sources["pages.py"].count("write_opened(found.folder,") == 1  # the document page
    assert sources["pages.py"].count("write_opened(found.work,") == 1  # Listen, not outside
    assert sources["tasks.py"].count("write_about(document.folder,") == 1  # after an analysis
    assert "".join(sources.values()).count("write_opened(") == 2
    assert "".join(sources.values()).count("write_about(") == 1
    for table in (EN, DE):
        for name in ("opened.json", "about.json", "position.json"):
            assert f"({name})" in table["privacy.work"], name
    # 8: the captures (#397): the server writes them to captures.json in the working folder,
    # and the v1.3 markers.json stays beside it (ADR-008 2.1 item 5); both are named
    from sci2audio.app.captures import CAPTURES, MARKERS

    assert (CAPTURES, MARKERS) == ("captures.json", "markers.json")
    for table in (EN, DE):
        assert f"({CAPTURES})" in table["privacy.work"]
        assert f"({MARKERS})" in table["privacy.work"]


def test_the_privacy_page_names_the_update_checks_host_from_the_code(
    server_: tuple[FastAPI, Any],
) -> None:
    host = updates.RELEASES_URL.split("/")[2]
    for language in ("en", "de"):
        page = client_in(server_, language).get("/privacy").text
        section = page[page.index('id="update-check"') :]
        assert f"<code>{host}</code>" in section.split("</p>", 2)[1], language


def test_launch_opens_only_a_loopback_socket() -> None:
    source = (SOURCE / "launch.py").read_text(encoding="utf-8")
    assert "HOST" in source
    assert "0.0.0.0" not in source  # noqa: S104 - the check that it never binds there
    assert "::" not in source


def test_the_privacy_page_names_the_installed_plugins(
    tmp_path: Path, server_: tuple[FastAPI, Any]
) -> None:
    """The page lists the plugins this server's runner loaded, or says there are none (#685)."""
    from web_helpers import make_config, plugin_steps

    from sci2audio.app import JobRunner
    from sci2audio.web import create_app

    for language in ("en", "de"):
        none = client_in(server_, language).get("/privacy").text
        assert html.escape(strings(language)("privacy.plugins_none")) in none
    config = make_config(tmp_path / "with")
    app = create_app(config, runner=JobRunner(plugin_steps()))
    for language in ("en", "de"):
        page = client_in((app, config), language).get("/privacy").text
        section = page[page.index('id="plugins"') :]
        assert "<code>ampersand-and</code> (sci2audio-example 0.1)" in section
        assert html.escape(strings(language)("privacy.plugins_none")) not in page
    # a plugin that failed to load is installed too, and its import ran (#696)
    from sci2audio.textprep import InstalledSteps
    from sci2audio.textprep.plugins import PluginProblem

    problem = PluginProblem("no-such", "sci2audio-broken", "could not be loaded: boom")
    config = make_config(tmp_path / "broken")
    broken = create_app(config, runner=JobRunner(InstalledSteps(BUILT_IN, (), (problem,))))
    for language in ("en", "de"):
        page = client_in((broken, config), language).get("/privacy").text
        section = page[page.index('id="plugins"') :]
        assert html.escape(strings(language)("privacy.plugins_none")) not in page
        assert html.escape(strings(language)("privacy.plugins_problems")) in section
        listed = "<code>no-such</code> (sci2audio-broken): "
        assert listed + '<span lang="en">could not be loaded: boom</span>' in section
