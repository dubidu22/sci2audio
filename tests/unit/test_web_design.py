"""The Working Reader's foundation (#385), the rail (#387) and Settings (#388).

- The colour tokens are the design's: pinned here as literals from DESIGN.md and
  prototype/app/app.css of sci2audio-design b4a7523 (D-663), not read from that repository.
- Dark mode is written twice (chosen by the system, chosen in Settings); the two blocks
  must stay identical.
- Pages load nothing from the internet: no web address in any template, script or style,
  and every `url()` of the stylesheet is a bundled file.
- The bundled fonts are the files the licence table names, byte for byte, and ship with
  their OFL texts (D-670).
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

import pytest
from cli_helpers import Cli, small_pdf
from fastapi import FastAPI
from fastapi.testclient import TestClient
from web_helpers import ORIGIN, anonymous, app_and_config, browser

from sci2audio.app import JobSettings, load_settings, save_settings
from sci2audio.textprep import Category
from sci2audio.web import i18n, pages

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "src" / "sci2audio" / "web"
CSS = WEB / "static" / "app.css"
FONTS = WEB / "static" / "fonts"
LICENCES = ROOT / "THIRD_PARTY_LICENSES.md"

# DESIGN.md frontmatter `colors` (light)
LIGHT = {
    "cobalt": "#2340A8",
    "cobalt-deep": "#1A3087",
    "cobalt-line": "#3A56BE",
    "on-cobalt": "#FFFFFF",
    "on-cobalt-2": "#CCD5F4",
    "ink": "#16181D",
    "ink-2": "#3A3E46",
    "pencil": "#5A5E66",
    "paper": "#FFFFFF",
    "desk": "#EDEFF2",
    "desk-2": "#E3E6EA",
    "rule": "#D7DADF",
    "rule-strong": "#8C9199",
    "hl-read": "#FFE94A",
    "hl-note": "#7BE38A",
    "hl-quote": "#6CC4FF",
    "hl-card": "#FF8FC8",
    "hl-mark": "#FFB347",
    "error": "#B42318",
    "error-wash": "#FDECEA",
    "wait": "#7A4B00",
    "wait-wash": "#FFF3DC",
}
# prototype/app/app.css, the dark block (DESIGN.md "Dark mode re-tones every token")
DARK = {
    "cobalt": "#1C2E78",
    "cobalt-deep": "#15235E",
    "cobalt-line": "#2D41A0",
    "on-cobalt": "#FFFFFF",
    "on-cobalt-2": "#C3CCF0",
    "ink": "#E9EAED",
    "ink-2": "#C4C7CD",
    "pencil": "#A2A6AE",
    "paper": "#1C1F25",
    "desk": "#111317",
    "desk-2": "#181B20",
    "rule": "#30343C",
    "rule-strong": "#6E737C",
    "hl-read": "#F2DC3A",
    "hl-note": "#6CD27C",
    "hl-quote": "#5FB6F0",
    "hl-card": "#F07DB8",
    "hl-mark": "#F0A53C",
    "error": "#FF8A80",
    "error-wash": "#3A1A18",
    "wait": "#FFC870",
    "wait-wash": "#33280F",
}
HIGHLIGHTERS = ("hl-read", "hl-note", "hl-quote", "hl-card", "hl-mark")

ROOT_OPENS = re.compile(r"^:root \{", re.M)
LIGHT_BLOCK = re.compile(r"^:root \{(.*?)^\}", re.S | re.M)
SYSTEM_DARK = re.compile(
    r"@media \(prefers-color-scheme: dark\) \{\s*"
    r':root:not\(\[data-theme="light"\]\) \{(.*?)\}\s*\}',
    re.S,
)
CHOSEN_DARK = re.compile(r':root\[data-theme="dark"\] \{(.*?)\}', re.S)
DECLARATION = re.compile(r"(--[a-z0-9-]+|color-scheme)\s*:\s*([^;]+);")


def declarations(block: str) -> dict[str, str]:
    found: dict[str, str] = {}
    for name, value in DECLARATION.findall(block):
        assert name not in found, f"{name} twice in one block"
        found[name] = " ".join(value.split())
    return found


def blocks(css: str) -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
    light = LIGHT_BLOCK.search(css)
    system = SYSTEM_DARK.findall(css)
    chosen = CHOSEN_DARK.findall(css)
    assert light is not None
    assert len(system) == 1, "one dark block for the system's choice"
    assert len(chosen) == 1, "one dark block for the choice made in Settings"
    return declarations(light[1]), declarations(system[0]), declarations(chosen[0])


def check_tokens(css: str) -> None:
    assert len(ROOT_OPENS.findall(css)) == 1, "one :root block, the light tokens"
    light, system, chosen = blocks(css)
    rest = css
    for block in (LIGHT_BLOCK, SYSTEM_DARK, CHOSEN_DARK):
        rest = block.sub("", rest, count=1)
    stray = [token for token in LIGHT if re.search(rf"--{token}\s*:", rest)]
    assert stray == [], f"design tokens set outside their three blocks: {stray}"
    assert system == chosen, "the two dark blocks differ"
    for token, value in LIGHT.items():
        assert light.get(f"--{token}", "").upper() == value, token
    for token, value in DARK.items():
        assert system.get(f"--{token}", "").upper() == value, token
    assert light["color-scheme"] == "light"
    assert system["color-scheme"] == "dark"


# --- tokens (#385) -----------------------------------------------------------------------


def test_the_tokens_are_the_designs_in_light_and_dark() -> None:
    check_tokens(CSS.read_text(encoding="utf-8"))


def test_the_check_finds_a_dark_block_that_drifted() -> None:
    # one changed line in one of the two dark blocks is a failure
    css = CSS.read_text(encoding="utf-8")
    start = css.index(':root[data-theme="dark"]')
    drifted = css[:start] + css[start:].replace("--paper: #1C1F25", "--paper: #1C1F26", 1)
    with pytest.raises(AssertionError, match="dark blocks differ"):
        check_tokens(drifted)


@pytest.mark.parametrize(
    ("added", "message"),
    [
        (":root { --cobalt: #000000; }", "one :root block"),
        (':root[data-theme="dark"] .rail { --cobalt: #000000; }', "outside their three blocks"),
        (".rail { --paper: #000000; }", "outside their three blocks"),
    ],
)
def test_the_check_finds_a_token_set_again_after_its_blocks(added: str, message: str) -> None:
    # the two mutants of PR #409 review S2, and a token set again on a part of the page
    css = CSS.read_text(encoding="utf-8")
    with pytest.raises(AssertionError, match=message):
        check_tokens(css + "\n" + added + "\n")


def test_every_number_is_set_in_tabular_figures() -> None:
    css = CSS.read_text(encoding="utf-8")
    body = re.search(r"^body \{(.*?)^\}", css, re.S | re.M)
    assert body is not None
    assert "font-variant-numeric: tabular-nums lining-nums" in body[1]


# --- the mark of the sentence being read (D-709, D-711, #452) ----------------------------

# the stylesheet the server serves, as the imported package holds it
SERVED_CSS = Path(i18n.__file__).parent / "static" / "app.css"
HEX = re.compile(r"#([0-9A-Fa-f]{6})")
MIX = re.compile(r"color-mix\(in srgb, (.+?) (\d+)%, (?:transparent|var\(--paper\))\)")


def rgb(value: str, tokens: dict[str, str]) -> tuple[float, ...]:
    """A token's colour as 0..1 channels; a var() is looked up in the same block."""
    value = value.strip()
    if value.startswith("var(--"):
        return rgb(tokens[value[4:-1]], tokens)
    found = HEX.fullmatch(value)
    assert found is not None, value
    return tuple(int(found[1][i : i + 2], 16) / 255 for i in (0, 2, 4))


def on_paper(value: str, tokens: dict[str, str]) -> tuple[float, ...]:
    """A colour as it shows on the paper: a see-through tint is laid over the paper."""
    paper = rgb(tokens["--paper"], tokens)
    mix = MIX.fullmatch(value.strip())
    if mix is None:
        return rgb(value, tokens)
    share = int(mix[2]) / 100
    colour = rgb(mix[1], tokens)
    return tuple(c * share + p * (1 - share) for c, p in zip(colour, paper, strict=True))


def luminance(colour: tuple[float, ...]) -> float:
    """WCAG 2 relative luminance."""
    r, g, b = (c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in colour)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(one: tuple[float, ...], two: tuple[float, ...]) -> float:
    high, low = sorted((luminance(one), luminance(two)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def mark_contrasts(css: str) -> dict[str, dict[str, float]]:
    light, system, _chosen = blocks(css)
    found = {}
    for theme, block in (("light", light), ("dark", system)):
        tokens = {**light, **block}  # a dark block re-tones; what it leaves keeps the light value
        fill = on_paper(tokens["--now"], tokens)
        bar = rgb(tokens["--now-bar"], tokens)
        found[theme] = {
            "bar on paper": contrast(bar, rgb(tokens["--paper"], tokens)),
            "bar on desk": contrast(bar, rgb(tokens["--desk"], tokens)),  # Focus stands on it
            "bar on fill": contrast(bar, fill),
            "text": contrast(fill, rgb(tokens["--on-now"], tokens)),
        }
    return found


def test_the_bar_stands_out_and_the_text_on_the_mark_reads_well() -> None:
    """D-724 (amends D-711 for the mark): the fill may be pale; the bar beside it stands out
    at least 3:1 from the paper, the desk Focus stands on and the fill, in both themes, and
    the text on the fill keeps at least 4.5:1."""
    for theme, measured in mark_contrasts(SERVED_CSS.read_text(encoding="utf-8")).items():
        assert measured["bar on paper"] >= 3, (theme, measured)
        assert measured["bar on desk"] >= 3, (theme, measured)
        assert measured["bar on fill"] >= 3, (theme, measured)
        assert measured["text"] >= 4.5, (theme, measured)


def test_the_contrast_check_finds_a_bar_in_the_reading_yellow_on_white() -> None:
    # a bar in the reading yellow on white paper: 1.2:1
    css = SERVED_CSS.read_text(encoding="utf-8").replace(
        "--now-bar: #9A7400", "--now-bar: var(--hl-read)", 1
    )
    light = mark_contrasts(css)["light"]
    assert light["bar on paper"] < 1.3


def marker_contrasts(css: str) -> dict[str, dict[str, float]]:
    """#474, D-727: the marker's flag and tick, in both themes."""
    light, system, _chosen = blocks(css)
    found = {}
    for theme, block in (("light", light), ("dark", system)):
        tokens = {**light, **block}
        edge = rgb(tokens["--marker-edge"], tokens)
        body = rgb(tokens["--marker"], tokens)
        found[theme] = {
            "edge on paper": contrast(edge, rgb(tokens["--paper"], tokens)),  # sheet, dock
            "edge on desk": contrast(edge, rgb(tokens["--desk"], tokens)),  # above the dock
            "icon on body": contrast(rgb(tokens["--on-hl"], tokens), body),
        }
    return found


def test_the_markers_flag_and_tick_stand_out() -> None:
    """D-727 for the marker (#474): the flag's and the tick's edge stand out at least 3:1
    from every background they sit on (the sheet's padding and the dock are paper; the tick
    stands above the track, half on the desk), and the icon from the flag's body."""
    for theme, measured in marker_contrasts(SERVED_CSS.read_text(encoding="utf-8")).items():
        for name, value in measured.items():
            assert value >= 3, (theme, name, measured)


def test_the_contrast_check_finds_a_marker_edge_in_the_mark_orange_on_white() -> None:
    css = SERVED_CSS.read_text(encoding="utf-8").replace(
        "--marker-edge: #9A5800", "--marker-edge: var(--hl-mark)", 1
    )
    assert marker_contrasts(css)["light"]["edge on paper"] < 2


def test_one_mark_for_the_sheet_and_focus() -> None:
    """D-720: the mark's tokens are set only in the three token blocks, and only the sheet's
    mark, Focus's mark and the bar use them."""
    css = re.sub(r"/\*.*?\*/", "", SERVED_CSS.read_text(encoding="utf-8"), flags=re.S)
    users = {
        rule.split("{")[0].strip()
        for rule in re.findall(r"[^{}]+\{[^{}]*var\(--(?:now|on-now|now-bar)\)[^{}]*\}", css)
    }
    assert users == {".read-along .s.now", ".focus-stage #focus-now", ".now-bar"}, users
    assert ".s.done" not in css
    assert "--held" not in css


def test_nothing_moves_under_reduced_motion() -> None:
    css = CSS.read_text(encoding="utf-8")
    block = css[css.index("@media (prefers-reduced-motion: reduce)") :]
    assert "animation: none !important" in block
    assert "transition: none !important" in block


# --- nothing from the internet (#385) ------------------------------------------------------

WEB_ADDRESS = re.compile(r"(?i)\b(?:https?|ftp|wss?):")
PROTOCOL_RELATIVE = re.compile(
    r"""(?i)(?:url\(\s*['"]?|(?:src|href|action)\s*=\s*['"]?|@import\s+['"])\s*//"""
)
SLASHES = re.compile(r"//")
QUOTED_SLASHES = re.compile(r"""["'`]\s*//""")
CSS_URL = re.compile(r"""url\(\s*['"]?([^'")]+)""")
PAGE_FILES = (".html", ".css", ".js", ".svg", ".json")


def page_files() -> dict[str, str]:
    """Every file a page can load or is built from (licence texts are not loaded)."""
    found = {}
    for folder in ("templates", "static"):
        for path in sorted((WEB / folder).rglob("*")):
            if path.is_file() and path.suffix in PAGE_FILES:
                found[path.relative_to(WEB).as_posix()] = path.read_text(encoding="utf-8")
    return found


def outside_addresses(name: str, text: str) -> list[str]:
    found = [m[0] for m in WEB_ADDRESS.finditer(text)]
    if name.endswith((".html", ".css", ".svg")):
        # No page, style sheet or picture needs "//" at all (comments in CSS are /* */), so
        # every one is reported: an address without its scheme can sit in any attribute or
        # CSS function (srcset, poster, a refresh <meta>, image-set()), not just src and
        # url() (PR #409 review B1).
        found += [
            f"// on line {text.count(chr(10), 0, m.start()) + 1}" for m in SLASHES.finditer(text)
        ]
    else:
        found += [m[0] for m in PROTOCOL_RELATIVE.finditer(text)]
    if name.endswith(".js"):
        # a script's comments start with //, its strings may not: the same rule as the paths
        # a script asks for in test_web_pages.py::test_no_page_loads_anything_from_outside
        found += [m[0] for m in QUOTED_SLASHES.finditer(text)]
    if name.endswith(".css"):
        for url in CSS_URL.findall(text):
            if url.startswith("data:"):
                continue
            if not (CSS.parent / url).resolve().is_file():
                found.append(f"url({url}) is no bundled file")
    return found


def test_no_page_refers_to_an_address_outside_this_server() -> None:
    files = page_files()
    assert {"templates/base.html", "templates/_icons.html", "static/app.css"} <= set(files)
    for name, text in files.items():
        assert outside_addresses(name, text) == [], name


@pytest.mark.parametrize(
    ("name", "line"),
    [
        ("static/app.css", '@import url("https://fonts.googleapis.com/css2?family=Literata");'),
        ("static/app.css", "src: url(//fonts.gstatic.com/s/literata.woff2);"),
        ("static/app.css", "src: url(fonts/literata-cyrillic-wght-normal.woff2);"),
        ("templates/base.html", '<link rel="stylesheet" href="http://127.0.0.1:9/x.css">'),
        ("templates/base.html", '<script src="//cdn.example/x.js"></script>'),
        # the four the review found passing (PR #409 B1): an IP number, no scheme
        ("templates/base.html", '<img srcset="//192.168.1.9/x.png 1x" alt="">'),
        ("static/app.css", '.x { background-image: image-set("//192.168.1.9/x.png" 1x); }'),
        ("templates/base.html", '<meta http-equiv="refresh" content="0;url=//192.168.1.9/">'),
        ("templates/_icons.html", '<video poster="//192.168.1.9/p.png"></video>'),
        ("static/app.js", 'fetch("//192.168.1.9/x");'),
    ],
)
def test_the_check_finds_one_added_line(name: str, line: str) -> None:
    files = page_files()
    assert outside_addresses(name, files[name]) == []
    assert outside_addresses(name, files[name] + "\n" + line) != []


# --- the bundled fonts and their licences (#385, D-670) -------------------------------------

ROW = re.compile(r"^\| `([a-z0-9-]+\.woff2)` \|.*\| `([0-9a-f]{64})` \|$", re.M)


def test_every_font_is_the_licence_tables_file_byte_for_byte() -> None:
    table = dict(ROW.findall(LICENCES.read_text(encoding="utf-8")))
    shipped = {path.name for path in FONTS.glob("*.woff2")}
    assert len(shipped) == 12
    assert set(table) == shipped
    for name, digest in table.items():
        assert hashlib.sha256((FONTS / name).read_bytes()).hexdigest() == digest, name
    used = set(re.findall(r"url\(fonts/([a-z0-9-]+\.woff2)\)", CSS.read_text(encoding="utf-8")))
    assert used == shipped


def test_both_ofl_texts_ship_beside_the_fonts() -> None:
    for family, holder in (
        ("atkinson", "Braille Institute of America"),
        ("literata", "The Literata Project Authors"),
    ):
        text = (FONTS / f"OFL-{family}.txt").read_text(encoding="utf-8")
        assert "SIL OPEN FONT LICENSE Version 1.1" in text
        assert holder in text
        assert "Reserved Font Name" not in text.split("\n\n")[0]  # none is reserved


def server(tmp_path: Path) -> tuple[FastAPI, Any]:
    return app_and_config(tmp_path)


def client_of(app_config: tuple[FastAPI, Any]) -> TestClient:
    client = browser(*app_config)
    client.headers["Origin"] = ORIGIN
    return client


def test_the_fonts_are_served_as_fonts_behind_the_token(tmp_path: Path) -> None:
    app_config = server(tmp_path)
    client = client_of(app_config)
    response = client.get("/static/fonts/literata-latin-wght-normal.woff2")
    assert response.status_code == 200
    assert response.headers["content-type"] == "font/woff2"
    assert "default-src 'self'" in response.headers["content-security-policy"]
    assert anonymous(app_config[0]).get("/static/fonts/OFL-literata.txt").status_code == 401


# --- the icon sprite (#385) ----------------------------------------------------------------


def test_every_icon_used_is_in_the_sprite() -> None:
    sprite = (WEB / "templates" / "_icons.html").read_text(encoding="utf-8")
    symbols = set(re.findall(r'<symbol id="i-([a-z]+)"', sprite))
    assert len(symbols) == 33
    templates = "".join(p.read_text(encoding="utf-8") for p in (WEB / "templates").glob("*.html"))
    used = set(re.findall(r"""\bicon\(\s*'([a-z]+)'""", templates))
    assert used
    assert used <= symbols


# --- the rail (#387) ----------------------------------------------------------------------


def rail_of(page: str) -> str:
    return page.split('<nav class="rail"')[1].split("</nav>")[0]


@pytest.mark.parametrize(
    ("path", "current"),
    [
        ("/", "/"),
        ("/voice", "/voice"),
        ("/settings", "/settings"),
        ("/privacy", "/privacy"),
        ("/jobs/nothing", None),
        ("/documents/0123456789abcdef", None),
    ],
)
def test_the_rail_marks_the_current_page(tmp_path: Path, path: str, current: str | None) -> None:
    rail = rail_of(client_of(server(tmp_path)).get(path).text)
    for item in ('href="/"', 'href="/#open-file"', 'href="/voice"', 'href="/settings"'):
        assert item in rail
    assert 'href="/privacy"' in rail
    assert "/captures" not in rail  # waits for the study layer (#397)
    # the shortcuts sheet's item (#394): a button, drawn disabled until app.js wires it
    assert re.search(r'<button type="button" id="keys-open" aria-haspopup="dialog" disabled>', rail)
    assert "<span>Keyboard shortcuts</span>" in rail
    marked = re.findall(r'<a href="([^"]+)"[^>]*aria-current="page"', rail)
    assert marked == ([] if current is None else [current])
    assert "Reading and recent" not in rail  # nothing on the shelf without a job


@pytest.mark.parametrize("path", ["/", "/voice", "/settings", "/privacy", "/jobs/nothing"])
def test_every_page_has_the_shortcuts_sheet(tmp_path: Path, path: str) -> None:
    """#394: a closed dialog, its Close drawn disabled until app.js wires it; the keys of
    Listen and Focus with their names for screen readers; M sets a marker (#474); N, Q and
    C wait for #397."""
    page = client_of(server(tmp_path)).get(path).text
    sheet = page.split('<dialog id="keys"')[1].split("</dialog>")[0]
    assert ' aria-labelledby="keys-title">' in sheet.split("\n")[0]
    assert " open" not in sheet.split(">")[0]
    assert '<h2 id="keys-title">Keyboard shortcuts</h2>' in sheet
    assert re.search(
        r'<button type="button" class="icon-btn" id="keys-close" [^>]*disabled>', sheet
    )
    terms = re.findall(r"<dt>([^<]*)</dt>", sheet)
    assert terms == [
        "Play or pause",
        "Previous / next sentence",
        "Previous / next chapter",
        "Slower / faster",
        "Set or remove a marker on the sentence being read",
        "Focus listening",
        "Show or hide the side panel",
        "This list",
        "Close, cancel or leave focus",
    ]
    assert "<kbd>Space</kbd>" in sheet
    left = '<span aria-hidden="true">←</span><span class="visually-hidden">Left arrow</span>'
    assert left in sheet
    assert '<span class="visually-hidden">Shift</span>' in sheet
    assert "<kbd>M</kbd>" in sheet
    for later in ("<kbd>N</kbd>", "<kbd>Q</kbd>", "<kbd>C</kbd>"):
        assert later not in sheet
    german_client = client_of(server(tmp_path))
    german_client.cookies.set("sci2audio-language", "de")
    german = german_client.get(path).text
    assert "<kbd>Leertaste</kbd>" in german
    assert "Pfeil nach links" in german


def test_the_library_counts_its_documents_in_words_too(tmp_path: Path) -> None:
    from web_helpers import paper_bytes, upload

    client = client_of(server(tmp_path))
    assert 'aria-label="Library, 0 documents"' in rail_of(client.get("/voice").text)
    upload(client, paper_bytes(), "paper.pdf")
    rail = rail_of(client.get("/voice").text)
    assert '<span class="count" aria-hidden="true">1</span>' in rail
    assert 'aria-label="Library, 1 document"' in rail


@pytest.mark.parametrize(
    ("progress", "expected"),
    [
        (None, None),
        ({}, None),
        ({"phase": "reading", "page": 3, "pages": 12}, 0.25),
        ({"phase": "speaking", "chunks_done": 30, "chunks_total": 120}, 0.25),
        ({"phase": "downloading", "bytes_done": 50, "bytes_total": 200}, 0.25),
        ({"phase": "speaking", "chunks_done": 5, "chunks_total": 0}, None),
        ({"phase": "speaking", "chunks_done": 9, "chunks_total": 3}, 1.0),
    ],
)
def test_how_far_a_job_is_as_the_job_page_counts_it(
    progress: dict[str, Any] | None, expected: float | None
) -> None:
    assert pages.progress_fraction(progress) == expected


# --- Settings: appearance and announcements as cookies (#388, D-671) -----------------------


def test_settings_marks_the_appearance_and_the_html_carries_a_chosen_one(tmp_path: Path) -> None:
    client = client_of(server(tmp_path))
    page = client.get("/settings").text
    assert "data-theme" not in page.split("<html ")[1].split(">")[0]  # as the system
    assert 'value="system" aria-pressed="true"' in page
    client.cookies.set(i18n.THEME_COOKIE, "dark")
    page = client.get("/settings").text
    assert '<html lang="en" data-theme="dark">' in page
    assert 'value="dark" aria-pressed="true"' in page
    assert '<meta name="color-scheme" content="dark">' in page
    client.cookies.set(i18n.THEME_COOKIE, '"><script>')  # a forged value counts as none
    page = client.get("/privacy").text
    assert '<html lang="en">' in page
    assert "<script>" not in page.split("</title>")[0]


@pytest.mark.parametrize(
    ("query", "cookies"),
    [
        ("theme=dark", {i18n.THEME_COOKIE: "dark"}),
        ("theme=light", {i18n.THEME_COOKIE: "light"}),
        ("theme=system", {i18n.THEME_COOKIE: "system"}),
        ("theme=blue", {}),
        ("theme=DARK", {}),
        ("announce=on", {i18n.ANNOUNCE_COOKIE: "on"}),
        ("announce=off", {i18n.ANNOUNCE_COOKIE: "off"}),
        ("announce=off&announce=on", {i18n.ANNOUNCE_COOKIE: "on"}),  # the box ticked
        ("announce=yes", {}),
        ("keys=off", {i18n.KEYS_COOKIE: "off"}),
        ("keys=on", {i18n.KEYS_COOKIE: "on"}),
        ("keys=off&keys=on", {i18n.KEYS_COOKIE: "on"}),  # the box ticked
        ("keys=no", {}),
        ("", {}),
    ],
)
def test_the_appearance_route_keeps_only_known_choices(
    tmp_path: Path, query: str, cookies: dict[str, str]
) -> None:
    client = client_of(server(tmp_path))
    response = client.get(f"/appearance?back=/settings&{query}", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/settings"
    set_cookies = response.headers.get_list("set-cookie")
    assert {c.split("=")[0]: c.split("=")[1].split(";")[0] for c in set_cookies} == cookies
    for cookie in set_cookies:
        assert "HttpOnly" in cookie
        assert "SameSite=strict" in cookie
        assert "Max-Age=31536000" in cookie
        assert "Path=/" in cookie


@pytest.mark.parametrize("back", ["https://example.com/", "//example.com", "/\\x", None])
def test_the_appearance_route_goes_back_only_to_this_server(
    tmp_path: Path, back: str | None
) -> None:
    client = client_of(server(tmp_path))
    params = {"theme": "dark"} if back is None else {"theme": "dark", "back": back}
    response = client.get("/appearance", params=params, follow_redirects=False)
    assert response.headers["location"] == "/"


def test_the_appearance_route_is_guarded_and_its_cookies_grant_nothing(tmp_path: Path) -> None:
    app, _ = server(tmp_path)
    outsider = anonymous(app)
    assert outsider.get("/appearance?theme=dark", follow_redirects=False).status_code == 401
    outsider.cookies.set(i18n.THEME_COOKIE, "dark")
    outsider.cookies.set(i18n.ANNOUNCE_COOKIE, "on")
    assert outsider.get("/settings").status_code == 401
    assert outsider.get("/api/v1/settings").status_code == 401
    client = client_of((app, _))
    cross = client.get(
        "/appearance?theme=dark", headers={"Sec-Fetch-Site": "cross-site"}, follow_redirects=False
    )
    assert cross.status_code == 403
    elsewhere = client.get(
        "/appearance?theme=dark", headers={"Origin": "http://evil.example"}, follow_redirects=False
    )
    assert elsewhere.status_code == 403  # the same guards as /language (D-288, D-321)
    assert "set-cookie" not in cross.headers
    assert "set-cookie" not in elsewhere.headers


def test_the_announce_switch_shows_the_cookie(tmp_path: Path) -> None:
    client = client_of(server(tmp_path))
    page = client.get("/settings").text
    box = re.search(r'<input type="checkbox" role="switch"[^>]*id="settings-announce"[^>]*>', page)
    assert box is not None
    assert "checked" not in box[0]
    # the hidden "off" comes before the box, so a ticked box wins
    assert page.index('name="announce" value="off"') < page.index('id="settings-announce"')
    client.cookies.set(i18n.ANNOUNCE_COOKIE, "on")
    page = client.get("/settings").text
    assert re.search(r'id="settings-announce"[^>]* checked>', page)


def test_the_keys_switch_is_on_by_default_and_the_html_carries_it_off(tmp_path: Path) -> None:
    """#394 review S3: the page-wide single keys work unless switched off in Settings; the
    choice reaches the scripts as data-keys on every page."""
    client = client_of(server(tmp_path))
    page = client.get("/settings").text
    box = re.search(r'<input type="checkbox" role="switch"[^>]*id="settings-keys"[^>]*>', page)
    assert box is not None
    assert box[0].endswith(" checked>")
    assert page.index('name="keys" value="off"') < page.index('id="settings-keys"')
    assert "data-keys" not in page.split("<html ")[1].split(">")[0]
    client.cookies.set(i18n.KEYS_COOKIE, "off")
    for path in ("/settings", "/", "/privacy"):
        page = client.get(path).text
        assert '<html lang="en" data-keys="off">' in page, path
    page = client.get("/settings").text
    box = re.search(r'<input type="checkbox" role="switch"[^>]*id="settings-keys"[^>]*>', page)
    assert box is not None
    assert "checked" not in box[0]
    client.cookies.set(i18n.KEYS_COOKIE, '"><script>')  # a forged value counts as none: on
    page = client.get("/settings").text
    assert '<html lang="en">' in page
    assert re.search(r'id="settings-keys"[^>]* checked>', page)


# --- Settings: the defaults for new audiobooks (#388) --------------------------------------


def test_settings_shows_the_saved_defaults_and_showing_writes_nothing(tmp_path: Path) -> None:
    app, config = server(tmp_path)
    client = client_of((app, config))
    page = client.get("/settings").text
    assert f'value="{config.output_folder}"' in page
    assert 'id="settings-speed" name="speed" min="0.50" max="2.00" step="0.01" value="1.00"' in page
    assert not config.config_file.exists()
    folder = tmp_path / "Audiobooks"
    save_settings(JobSettings(output_folder=folder, speed=1.25), config.config_file)
    before = config.config_file.read_bytes()
    page = client.get("/settings").text
    assert f'value="{folder}"' in page
    assert 'value="1.25"' in page
    assert "1.25 times" in page
    assert config.config_file.read_bytes() == before


def test_saving_the_defaults_as_the_page_does_keeps_every_other_setting(tmp_path: Path) -> None:
    app, config = server(tmp_path)
    client = client_of((app, config))
    kept = JobSettings(
        switched_off=frozenset({Category.CITATIONS}), letter_pace="slower", subtitles=True
    )
    save_settings(kept, config.config_file)
    # what app.js does: read the settings fresh, change two fields, write them all back
    saved = client.get("/api/v1/settings").json()["settings"]
    saved["output_folder"] = str(tmp_path / "Books")
    saved["speed"] = 0.85
    assert client.put("/api/v1/settings", json=saved).status_code == 200
    now, warnings = load_settings(config.config_file)
    assert warnings == []
    assert now.output_folder == tmp_path / "Books"
    assert now.speed == 0.85
    assert now.switched_off == kept.switched_off
    assert now.letter_pace == "slower"
    assert now.subtitles is True


def test_a_broken_settings_file_is_named_on_the_page(tmp_path: Path) -> None:
    app, config = server(tmp_path)
    config.config_file.parent.mkdir(parents=True, exist_ok=True)
    config.config_file.write_text('{"version": 1, "speed": "fast"}', encoding="utf-8")
    page = client_of((app, config)).get("/settings").text
    assert 'id="settings-warning"' in page


def test_the_command_line_reads_the_defaults_and_never_writes_them(tmp_path: Path) -> None:
    cli = Cli(tmp_path / "cli")
    save_settings(JobSettings(output_folder=tmp_path / "saved", speed=1.25), cli.config)
    before = cli.config.read_bytes()
    source = small_pdf(tmp_path / "in", ["A short note about the defaults."])
    result = cli("script", source)
    assert result.code == 0, result.err
    assert (tmp_path / "saved" / "note.script.txt").is_file()  # the saved folder was read
    assert cli.config.read_bytes() == before
    cli_source = (ROOT / "src" / "sci2audio" / "cli.py").read_text(encoding="utf-8")
    assert "save_settings" not in cli_source


DOWNLOAD_LINK = re.compile(r"<a\b[^>]*\?download=true[^>]*>", re.S)


def test_every_download_link_saves_without_leaving_the_page() -> None:
    """#435: a `?download=true` link without the `download` attribute is a navigation; a
    click on it while the page loads stops the load, and app.js never runs."""
    links = [
        (template.name, link)
        for template in sorted((Path(pages.__file__).parent / "templates").glob("*.html"))
        for link in DOWNLOAD_LINK.findall(template.read_text(encoding="utf-8"))
    ]
    assert len(links) >= 4  # the side column's three and the job card's files
    missing = [(name, link) for name, link in links if not re.search(r"\sdownload[\s>]", link)]
    assert missing == []
