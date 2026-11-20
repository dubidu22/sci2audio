# Review of PR #148, round 1: EPUB extraction and cover images (#73, part 2)

Reviewed head ef06f7f (13 Nov 2026) against `plans/issue73-epub-plan.md` (q1–q16, D-304 to D-319).
Verdict: **changes requested**: four must-fix items (three tracebacks on hostile or damaged
files, one unbounded memory use), plus missing tests for eight rules that mutation testing shows
are unpinned. The design follows the plan closely and the golden file is right.

## What I checked, and what passed

- **Whole diff against the plan.** Parser (q2), lines and `br`/`pre` (q3), tag vocabulary (q4),
  HTML-default bold/italic (q5), `Page.order`, `Picture.ref`, `OutlineEntry.item` (q6–q8), nav over
  NCX with damage tolerated (q8), metadata table (q9), covers per format (q10), spine edge cases
  (q11), broken-file table (q12), made-up EPUBs built in the tests (q13), full-text golden (q14).
  All as decided.
- **Golden file against the printed text (D-60).** I re-derived every line of all 18 spine
  documents independently with `xml.etree` (not `html.parser`), one line per block element and
  `<br>`, folding ASCII white space: **368 of 368 lines identical**. No line has leading,
  trailing or double ASCII spaces. Bold/italic agree with the D-308 element lists on every run.
  `Page.order` lists exactly each page's items. Links resolve to `p10-l8` (the backlink to the
  noteref), `p16-l2` (the endnote) and `p18`. Note: the plan said the sample has no `<br>`; the
  colophon and the uncopyright verse do have them, and they are recorded as D-306 says (`br`
  tag on the continuing line).
- **Security probes that passed.** Billion laughs and external entities refused before
  ElementTree runs; 200,000-deep nesting in the OPF reads in 0.1 s; 100,000 nested and 100,000
  unclosed inline elements in XHTML read in under 1 s with tags capped; the 65 MB zip bomb stops
  at the streamed limit; zip paths are only used as keys into the archive, never on the file
  system, so `../` in an href cannot reach outside the zip; DRM and password cases as in the table.
- **Fast suite:** ruff, format, lint-imports (3 contracts kept), deptry clean; 2265 passed,
  55 snapshots. **Nightly Hypothesis profile** on the three new test files: 94 passed.
  **CI** on ef06f7f: ubuntu, macOS, Windows, browser, lint and layers, security, licences,
  CodeQL all green.
- **Nightly command-line cut** (the coordinator's note): that test is part of PR 3 (app
  wiring), not this PR. I will check there that the three documents still cover outline,
  pictures and a cover.

## Must fix

**M1. A malformed URL crashes or fails the book.** `_resolve` calls `urllib.parse.urlsplit`,
which raises `ValueError` for e.g. `http://[x` ("Invalid IPv6 URL").
- In a **manifest** `href`: `read_epub` raises a bare `ValueError` (traceback, not an
  `ExtractionError`), and `extract_epub_cover` raises it too, breaking its "never raises" contract
  (D-313: a failure means no cover).
- In a **chapter** `<a href>` or `<img src>`: the whole book fails with "the EPUB is damaged:
  OEBPS/c1.xhtml cannot be read", although D-307 says an href that does not resolve is recorded
  as `href:<as stored>`.
- Fix: treat a `ValueError` from `urlsplit` as a link that leaves the book (`(None, "")`), so the
  manifest item is skipped, the link becomes `href:<as stored>` and the picture's `ref` the
  stored source. Tests for all three places, and add such an href to the Hypothesis markup
  alphabet. A Hypothesis "any bytes / damaged sample never raises" property for
  `extract_epub_cover` would have found this one.

**M2. A declared non-text encoding crashes.** `_decode` looks the declared name up with
`codecs.lookup` and then calls `bytes.decode`. For `encoding="hex"`, `base64`, `rot13`, `zlib`
or `uu`, `decode` raises `LookupError` ("is not a text encoding"), which nothing catches:
traceback. For `idna` and `punycode` the decode raises `UnicodeError` and the book fails as
"cannot be read", although D-315/q12 say a wrong encoding is read with U+FFFD. Fix: fall back to
UTF-8 with `errors="replace"` when the declared codec cannot decode text (catch `LookupError`
and `ValueError` around the decode). Test with at least `hex` and `idna`.

**M3. A damaged nav crashes the extraction.** `_NavReader.handle_endtag`: in
`<li><a href="c1.xhtml">A</li></a>` the `</li>` pops `labelled`, then `</a>` runs
`self.labelled[-1] = True` on an empty list: `IndexError`, which `outline()` does not catch, so
the whole file fails with a traceback. D-311 says a damaged outline never fails the file. Fix the
guard, and add a Hypothesis test that feeds the existing random-markup strategy into
`nav_entries` and asserts `Content` comes back.

**M4. Tags are not bounded, so memory grows with tokens × descendants.** `MAX_TAGGED` caps
the nesting depth, but not the number of `epub:type` / `role` tokens per element, and every
descendant element builds its own copy of all its ancestors' tags (`parent.tags + own`).
Measured: one `<div>` with 100,000 `epub:type` tokens and 2,000 `<span>` children (about 230 KB of
XHTML, a few KB zipped) takes 4.8 s and **1.56 GB**; memory grows linearly with the children, so
a 64 MB document exhausts memory. The `_Reader` docstring's linear-time promise and the plan's
"bounds a hostile file" do not hold. Fix: cap tokens per attribute, or the total tags per
element, at a small number (a constant next to `MAX_TAGGED`), and test the case above with a
time and memory bound (`tracemalloc` peak).

## Should fix: rules no test pins (mutation testing)

I ran 49 hand-made mutants of `epub.py`, `cover.py` and the PDF cover against the three new test
files: 37 killed, 12 survived. One is equivalent (`flag_bits & 0x1` → `0x2`: zipfile itself
then raises for the encrypted entry, which is caught with the same message). The other eleven
need a test each:

1. `_fold` stripping only ASCII space: `.strip()` survives, so a title or metadata value that
   starts or ends with a no-break space is not pinned (q3 keeps U+00A0 as stored).
2. `MAX_TAGGED = 100` → `101` survives: assert the exact cap (100 tagged elements) in the
   deep-nesting test.
3. The line feed right after `<pre>` being dropped (HTML rule): removing it survives.
4. A declared UTF-16/UTF-32 encoding without a byte-order mark read as UTF-8: removing it
   survives.
5. The NCX walk stopping at level 15: removing it survives; without it a deeply nested NCX hits
   Python's recursion limit (`RecursionError`, uncaught). Test a 2,000-level NCX.
6. The JPEG signature's third byte: `b"\xff\xd8"` survives; test `\xff\xd8` followed by another
   byte as "not a JPEG".
7. `_clean` refusing `../`: removing it survives. Pin that a manifest or link path above the zip
   root is never read (e.g. a member stored as `../x.xhtml`).
8. Anchors after the last item of a page pointing at the whole page (`link:p<n>`): removing it
   survives.
9. to 11. The values of `MAX_TOTAL` (512 MB), `MAX_COVER` (20 MB) and `MAX_SPINE` (10,000):
   tests only monkeypatch them, so changing a D-315/D-313 limit tenfold passes. One test that
   asserts the decided values is enough.

## Notes, no change needed

- Tag order per element is `#id`, `epub:`, `role:`, as D-307 lists them; the plan's worked
  example had `role:` before `epub:`. The decision text wins.
- `extract_epub` reads the whole file into memory without a size check; the PDF extractor does
  the same, so this is consistent and not a finding for this PR.

## Next step

The author fixes M1–M4 and adds the tests above, then lists exactly what was fixed (and opens an
issue for anything deferred). Round 2 re-runs the probes, the mutants, the nightly profile and
CI, then merges.
