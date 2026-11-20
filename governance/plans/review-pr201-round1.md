# Review PR #201, round 1 (issue #199, outline-adds-only property)

Head ea70558 (main a37c18e merged in). This PR changes one test file only, and CI is green. Verdict: **one should-fix (S1), no must-fix.**

## The coordinator's check: does a dropped or relabelled heading still fail?

Yes. I ran mutations of `layout/tagged.py`, each active only when the content has an outline, against the PR's test under `HYPOTHESIS_PROFILE=nightly`:

| Mutation (with an outline only) | PR's test |
|---|---|
| drop: the first heading of each page becomes a PARAGRAPH | fails (at once) |
| relabel: a heading's label gets an "x" | fails (after ~35 s of examples) |
| rank: on a page an outline entry points at, every heading gets the base level, ranks ignored | **passes** |

## S1 (should-fix): keep the level check that D-407 allows

For content without positions, the PR drops the level check completely. #199's acceptance criterion and D-437 say that levels may *shift by the outline's base level*. Under D-407 a page's headings are `base + rank index`, so the outline moves all headings on a page by one amount. (The exception is a heading that an outline entry names by `item`, which takes the entry's level; `outlined()` never sets `item`.) With no level check at all, the "rank" mutation above survives: the outline flattens `h1`/`h2` on a page into one level, and nothing notices.

Suggested change (I tested it in a worktree):

```python
    else:
        assert {s.start for s in walk(without.sections)} <= {s.start for s in walk(doc.sections)}
        # the outline moves a page's headings by one amount, its base level (D-407)
        items = found.items()
        levels = {s.start: s.level for s in walk(doc.sections)}
        shifts: dict[int, set[int]] = {}
        for s in walk(without.sections):
            page = items[without.blocks[s.start].parts[0].item][0].number
            shifts.setdefault(page, set()).add(levels[s.start] - s.level)
        assert all(len(shift) == 1 for shift in shifts.values())
```

You may want to leave out headings an entry names by `item` (say so in the comment), or note that `outlined()` never sets `item`.

Add a second `@example` with two ranks on one page. The random generator rarely makes positionless pages with two heading ranks and an outline entry, so the property alone did not kill the mutation under nightly:

```python
@example(  # two ranks on one page: both move by the base level the outline sets (#199)
    Content(
        Source("0", SourceFormat.EPUB),
        (PdfPage(1, lines=(
            TextLine("i0", (TextRun("Part", tags=("h1",)),)),
            TextLine("i1", (TextRun("Chapter", tags=("h2",)),)),
            TextLine("i2", (TextRun("Text."),)),
        )),),
        Metadata(),
        outline=(OutlineEntry("0", 1, 1), OutlineEntry("0", 1, 1), OutlineEntry("Part", 2, 1)),
    )
)
```

Measured: without the outline the levels are Part 1, Chapter 2. With it they are Part 2, Chapter 3 (shift 1 on both). With the tightened check and this example, the PR code passes (nightly) and the "rank" mutation fails.

## Other checks

- **Fast suite and CI** on ea70558: green.
- **The tagged branch still checks every heading:** each heading found without the outline keeps its HEADING kind, its label and its section start. The PDF branch is unchanged.
- **Generator note (no action in this PR):** `core_strategies.contents()` gives every drawing a box, so positionless pages only come up when a page has no drawings and every line and picture has no box. The tagged path gets few random cases, which is why the explicit examples matter.
