"""PR 5 round 1 fix mutants (#436 review round 1: B1, B2, S1, N1): one guard each, on the
lines 8857802 changes. Run with mut3.py, ROOT = a clean worktree at 8857802."""
F, H, L, C = "footnotes.py", "furniture.py", "links.py", "citations.py"
M = [
    # N1: the quote is cut
    (H, "if len(shown) > QUOTED:", "if len(shown) > QUOTED + 20:"),
    (H, 'shown = shown[: QUOTED - 1].rstrip() + "\\u2026"', "shown = shown[:QUOTED]"),
    (H, 'shown = shown[: QUOTED - 1].rstrip() + "\\u2026"', 'shown = shown[: QUOTED - 1] + "\\u2026"'),
    # B1: links and citations read without the hidden runs
    (L, "hidden = hidden_removals(document, context)", "hidden = {}"),
    (C, "hidden = hidden_removals(document, context)", "hidden = {}"),
    (H, "    if HiddenRunStep.category in context.switched_off:\n        return {}\n", ""),
    (H, "return \"\".join(text[at] for at in kept), [*kept, len(text)]", "return \"\".join(text[at] for at in kept), [*kept, len(text) + 1]"),
    (H, "end = kept[span.end - 1] + 1 if span.end > span.start else start", "end = kept[span.end]"),
    (H, "end = kept[span.end - 1] + 1 if span.end > span.start else start", "end = kept[span.end - 1] + 1"),
    (H, "if at <= skip_start and skip_end <= end:", "if skip_end <= end:"),
    (H, "if at <= skip_start and skip_end <= end:", "if at <= skip_start:"),
    (H, "                if skip_start > at:\n", "                if True:\n"),
    (H, "if at < end or not pieces:", "if at < end:"),
    (H, "if at < end or not pieces:", "if not pieces:"),
    (H, "            if number == 0:\n", "            if True:\n"),
    (H, "                        EditKind.REMOVE,\n                        edit.reason,", "                        edit.kind,\n                        edit.reason,"),
    # B2 and S1: before an affiliation
    (F, '_AFFILIATION = re.compile(r" ?([^\\W\\d_]{2,})")', '_AFFILIATION = re.compile(r" ?([^\\W\\d_]{1,})")'),
    (F, '_AFFILIATION = re.compile(r" ?([^\\W\\d_]{2,})")', '_AFFILIATION = re.compile(r" ?([A-Z][^\\W\\d_]+)")'),
    (F, '_AFFILIATION = re.compile(r" ?([^\\W\\d_]{2,})")', '_AFFILIATION = re.compile(r"\\s*([^\\W\\d_]{2,})")'),
    (F, "and affiliation[1][0].isupper()", ""),
    (F, "at_start = not kept or line_start or kept[-1] in \",;\"", "at_start = not kept or kept[-1] in \",;\""),
    (F, "at_start = not kept or line_start or kept[-1] in \",;\"", "at_start = not kept or line_start or kept[-1] in \",\""),
    (F, "at_start = not kept or line_start or kept[-1] in \",;\"", "at_start = line_start or kept[-1] in \",;\""),
    (F, "at_start = not kept or line_start or kept[-1] in \",;\"", "at_start = True"),
    (F, "kept = before.rstrip()\n", "kept = before\n"),
    (F, "line_starts = {offset for _, offset, _ in _lines(items, block)}", "line_starts = set()"),
]
