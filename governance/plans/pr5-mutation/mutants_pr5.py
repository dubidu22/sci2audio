"""PR 5 mutants: (file under textprep/, exact old text, new text). One guard each.

First run on c8dea9e (mut_pr5_first.txt): 45/50 killed. Three survivors were equivalent
(max(start, taken) in hidden runs, run.text.strip() before _AFFILIATION_MARK, the look-behind
of _NAME_END): that code went in the next commit and the mutants are dropped here. Two got
tests (hidden-then-page-break reason; the rise over a small run).
"""
F, H, P, L = "footnotes.py", "furniture.py", "placeholders.py", "links.py"
M = [
    # hidden runs (#193)
    (H, 'HIDDEN_TAGS = frozenset({"hidden", "aria-hidden"})', 'HIDDEN_TAGS = frozenset({"hidden"})'),
    (H, 'PAGE_BREAK_TAGS = frozenset({"epub:pagebreak", "role:doc-pagebreak"})', 'PAGE_BREAK_TAGS = frozenset({"epub:pagebreak"})'),
    (H, 'PAGE_BREAK_TAGS = frozenset({"epub:pagebreak", "role:doc-pagebreak"})', 'PAGE_BREAK_TAGS = frozenset({"role:doc-pagebreak"})'),
    (H, 'if block.kind is BlockKind.FURNITURE or block.is_placeholder:', 'if block.kind is BlockKind.FURNITURE:'),
    (H, 'if block.kind is BlockKind.FURNITURE or block.is_placeholder:', 'if block.is_placeholder:'),
    (H, '                    continue  # never point at other text', '                    pass  # never point at other text'),
    (H, 'if (HIDDEN_TAGS | PAGE_BREAK_TAGS) & tags and run.text.strip():', 'if (HIDDEN_TAGS | PAGE_BREAK_TAGS) & tags:'),
    (H, 'if stretches and stretches[-1][1] == offset:', 'if False:'),
    (H, 'stretches.append((first, end, before or hidden))', 'stretches.append((first, end, hidden))'),
    (H, '    while start < end and text[start].isspace():\n        start += 1\n', ''),
    (H, '    while end > start and text[end - 1].isspace():\n        end -= 1\n', ''),
    (H, 'if end == len(text) or text[end] in _CLOSING:', 'if end == len(text):'),
    (H, 'if end == len(text) or text[end] in _CLOSING:', 'if end < len(text) and text[end] in _CLOSING:'),
    (H, '_CLOSING = frozenset(",;:.!?)]")', '_CLOSING = frozenset(".")'),
    (H, 'shown = " ".join(block.text[start:end].split())', 'shown = block.text[start:end]'),
    # affiliation marks (#93)
    (F, 'if page != first or block.kind is BlockKind.HEADING:', 'if block.kind is BlockKind.HEADING:'),
    (F, 'if page != first or block.kind is BlockKind.HEADING:', 'if page != first:'),
    (F, '        if block.kind is BlockKind.PARAGRAPH:\n            yield index', '        yield index'),
    (F, '        if not block.parts:\n            continue\n        page = items', '        if not block.parts:\n            return\n        page = items'),
    (F, '_AFFILIATION_MARK.fullmatch(run.text)', '_AFFILIATION_MARK.search(run.text)'),
    (F, '_AFFILIATION_MARK = re.compile(r"\\s*[0-9,\\u2217*\\u2020\\u2021\\u00a7\\u00b6]+\\s*")', '_AFFILIATION_MARK = re.compile(r"\\s*[0-9,]+\\s*")'),
    (F, '                and _set_small(run, main)\n                and _superscript', '                and _superscript'),
    (F, '                and _superscript(run, line, main)\n', ''),
    (F, '                and not any(s < end and offset < e for s, e in taken)\n', ''),
    (F, 'if open_mark and open_mark[1] == offset:', 'if False:'),
    (F, '        and not _set_small(other, main)\n        and run.box.y1', '        and run.box.y1'),
    (F, 'and run.box.y1 <= other.box.y1 - RISE * main\n        for other in line.runs', 'and run.box.y1 < other.box.y1\n        for other in line.runs'),
    (F, 'and run.box.y1 <= other.box.y1 - RISE * main\n        for other in line.runs', 'and run.box.y1 < other.box.y1 - RISE * main\n        for other in line.runs'),
    (F, 'if word and word[0][0].isupper() and _AFTER_NAME.match(after):', 'if word and _AFTER_NAME.match(after):'),
    (F, 'if word and word[0][0].isupper() and _AFTER_NAME.match(after):', 'if word and word[0][0].isupper():'),
    (F, '_NAME_END = re.compile(r"[^\\W\\d_]{2,}\\Z")', '_NAME_END = re.compile(r"[^\\W\\d_]{1,}\\Z")'),
    (F, '_AFTER_NAME = re.compile(r"\\Z|[\\s,;\\u2217*\\u2020\\u2021\\u00a7\\u00b6]")', '_AFTER_NAME = re.compile(r"\\Z|[\\s,]")'),
    (F, '_AFTER_NAME = re.compile(r"\\Z|[\\s,;\\u2217*\\u2020\\u2021\\u00a7\\u00b6]")', '_AFTER_NAME = re.compile(r"")'),
    (F, '_AFFILIATION = re.compile(r" ?[A-Z]")', '_AFFILIATION = re.compile(r"\\s*[A-Z]")'),
    (F, '_AFFILIATION = re.compile(r" ?[A-Z]")', '_AFFILIATION = re.compile(r" ?\\w")'),
    (F, 'at_start = not before.strip() or before[-1].isspace() or before[-1] == ","', 'at_start = True'),
    (F, 'at_start = not before.strip() or before[-1].isspace() or before[-1] == ","', 'at_start = not before.strip() or before[-1].isspace()'),
    (F, 'start, end = removed_span(block.text, start, end)\n                edits.append(', 'edits.append('),
    # figure alt text (#191)
    (P, 'if not names and block.kind is BlockKind.FIGURE and (alt := _alt_text(items, block)):', 'if block.kind is BlockKind.FIGURE and (alt := _alt_text(items, block)):'),
    (P, 'if not names and block.kind is BlockKind.FIGURE and (alt := _alt_text(items, block)):', 'if not names and (alt := _alt_text(items, block)):'),
    (P, 'shown = " with its alt text"', 'shown = ""'),
    (P, '(alt := " ".join(picture.alt.split()))', '(alt := picture.alt.strip())'),
    (P, '(alt := " ".join(picture.alt.split()))', '(alt := picture.alt)'),
    (P, 'joined = "; ".join(alts)', 'joined = ", ".join(alts)'),
    (P, 'joined[-1] in ".!?\\u2026"', 'joined[-1] in "."'),
    (P, 'joined[-1] in ".!?\\u2026"', 'joined[-1] in ".!?"'),
    # #428
    (L, 'for edit in LinkStep()._block_edits(0, text, kind, label, words, language)', 'for edit in LinkStep()._block_edits(0, text, kind, label, words, "en")'),
    # unread_marks (later steps read without hidden runs and affiliation marks)
    (F, "    if HiddenRunStep.category not in context.switched_off:\n        found += HiddenRunStep().find(document, context)\n", ""),
    (F, "    if AffiliationMarkStep.category not in context.switched_off:\n        found += AffiliationMarkStep().marks(document, marks)\n", ""),
    (F, "    if HiddenRunStep.category not in context.switched_off:\n", "    if True:\n"),
    (F, "    if AffiliationMarkStep.category not in context.switched_off:\n", "    if True:\n"),
    ("units.py", "from sci2audio.textprep.footnotes import unread_marks\n", "from sci2audio.textprep.footnotes import found_marks as unread_marks\n"),
    ("abbreviations.py", "from sci2audio.textprep.footnotes import unread_marks\n", "from sci2audio.textprep.footnotes import found_marks as unread_marks\n"),
    ("numbers.py", "from sci2audio.textprep.footnotes import unread_marks\n", "from sci2audio.textprep.footnotes import found_marks as unread_marks\n"),
    ("statistics.py", "from sci2audio.textprep.footnotes import unread_marks\n", "from sci2audio.textprep.footnotes import found_marks as unread_marks\n"),
]
