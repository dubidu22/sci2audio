# Review PR #598, round 1 (app batch B16: #186, #207)

Reviewed head 215842e (base c155d8c). Non-critical. Verdict: **changes requested, one fix**.

## Checked
- C3 holds: no change to web/static/app.js, web/player.py, web/api.py, tests/unit/test_web_outside.py or layout/.
- Goldens and snapshots unchanged: tests/unit + tests/regression locally 7614 passed, 8 skipped (benchmark run apart: passed); test_cli_golden snapshot passes. Not critical.
- Strings: document.picture_pages.one/.other in en.toml and de.toml, placeholders match ({pages}; {n} and {pages}). German reads well.
- Picture-only detection: a page with text and a figure is never named (needs no text line at all); blank page not named; white-space lines count as no text; drawings do not count; PDF only; invisible OCR text counts as text.
- #207: Cf category covers ZWSP, soft hyphen, BOM, direction marks; "\n" cases unchanged (existing tests pass); JSON `original` stays raw; `_md` does not escape ⟨ ⟩ or +.
- CHANGELOG: one Added, one Fixed line under Unreleased (D-768).
- No closing keywords in the commit message.
- CI on 215842e: every required check green. Reported-only Firefox 2/2 red in tests/browser/test_keyboard.py::test_the_main_flow_by_keyboard (focus on the result heading), which this diff does not touch; I re-ran that job once (D-731).

## Hand mutants (tests/unit/test_app_{report,readability,job}.py, test_web_pages.py, test_cli_script.py; clean run passed first)
- drop `.strip()` in picture_pages: killed (test_a_line_of_white_space_only_is_no_text)
- drop `page.pictures and`: killed
- `_visible` left out of the "\n" branch: killed
- Cf test replaced by "​­" only: killed
- picture warning put before the unreadable warning: **survived**
- picture warning appended at the end (after language and encoding): **survived**

## Fix list (one fix commit)
1. Pin the warning order of `build_report` (plan: unreadable first, then the picture warning, then the language and encoding warnings). Add one test whose report has the unreadable warning, the picture warning and at least one later warning (language or encoding), and assert the exact order of `report.warnings`. It must fail under both surviving mutants above. No code change expected.

## Deferred
- #605: a page with only a small picture (a logo on a blank back page) is named as a scanned page; a size share using Picture.box could skip it.
