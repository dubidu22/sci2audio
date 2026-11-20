from pathlib import Path
from pdf_maker import Rect, Text, make_pdf
from playwright.sync_api import Page
from test_player import listen_to
from conftest import Live, at_rest

def pages():
    out = []
    for p in range(6):
        items = [Text(f"Section {p} text runs on and on here.", 72, 80 + 20 * k, size=11) for k in range(25)]
        out.append(items)
    out.append([Text("Late page words here.", 72, 80, size=11), Rect(100, 150, 400, 350),
                Text("Figure 9: A late chart.", 100, 370, size=9), Text("After it.", 72, 420, size=11)])
    return out

def test_probe_fold(signed_in: Page, live: Live, tmp_path: Path) -> None:
    page = signed_in
    listen_to(page, live, tmp_path / "late.pdf", make_pdf(*pages()))
    at_rest(page)
    fig = page.locator("#text .notice img.figure")
    print("count", fig.count())
    print("before", page.evaluate("() => [...document.querySelectorAll('img.figure')].map(i => [i.hidden, i.complete, i.naturalWidth, i.getBoundingClientRect().top])"))
    page.locator("#text .notice").first.scroll_into_view_if_needed()
    page.wait_for_timeout(3000)
    print("after", page.evaluate("() => [...document.querySelectorAll('img.figure')].map(i => [i.hidden, i.complete, i.naturalWidth, i.getBoundingClientRect().top])"))
