M = [
    # removed_span: the white-space-after branch
    ("furniture.py", "text[end] in _CLOSING or text[end].isspace()", "text[end] in _CLOSING"),
    ("furniture.py", "text[end] in _CLOSING or text[end].isspace()", "text[end] in _CLOSING or text[end] == ' '"),
    # through_unread / _around
    ("notation.py", "found += _around(Candidate(start, end, c.replacement, c.reason), unread)", "found.append(Candidate(start, end, c.replacement, c.reason))"),
    ("notation.py", "candidate.replacement if n == 0 else \"\"", "candidate.replacement"),
    ("notation.py", "if at <= skip_start < skip_end <= candidate.end:", "if at <= skip_start < skip_end < candidate.end:"),
    ("notation.py", "if at <= skip_start < skip_end <= candidate.end:", "if at < skip_start < skip_end <= candidate.end:"),
    ("notation.py", "if at <= skip_start < skip_end <= candidate.end:", "if at <= skip_start <= skip_end <= candidate.end:"),
    ("notation.py", "if at <= skip_start < skip_end <= candidate.end:", "if skip_start < skip_end <= candidate.end:"),
    ("notation.py", "            if skip_start > at:\n                pieces.append((at, skip_start))", "            pieces.append((at, skip_start))"),
    ("notation.py", "    if at < candidate.end or not pieces:", "    if at < candidate.end:"),
    ("notation.py", "    if at < candidate.end or not pieces:", "    if not pieces:"),
    # numbers guard
    ("numbers.py", r'r"(?<![\w/])(?<!(?<!\^)\d\s)(?<![.,]\s)(?P<base>[^\W\d_"', r'r"(?<![\w/])(?<!(?<!\^)\d )(?<![.,]\s)(?P<base>[^\W\d_"'),
    # raised_numbers
    ("footnotes.py", '_MASS_NUMBER = re.compile(r"[0-9]{1,3}")', '_MASS_NUMBER = re.compile(r"[0-9]+")'),
    ("footnotes.py", '_MASS_NUMBER = re.compile(r"[0-9]{1,3}")', '_MASS_NUMBER = re.compile(r"[0-9]{1,2}")'),
    ("footnotes.py", "                    and _set_small(run, main)\n                    and _superscript(run, line, main)\n                ):\n                    found.setdefault", "                    and _set_small(run, main)\n                ):\n                    found.setdefault"),
    ("footnotes.py", "                    _MASS_NUMBER.fullmatch(run.text)\n                    and _set_small(run, main)\n                    and _superscript", "                    _MASS_NUMBER.fullmatch(run.text)\n                    and _superscript"),
    ("footnotes.py", "                offset = end\n    return found", "    return found"),
    # units
    ("units.py", "raised = raised_numbers(document) if table.words.magnitudes else {}", "raised = {}"),
    ("units.py", "if start is None or table.magnitude.fullmatch(letter) is None:", "if start is None:"),
    ("units.py", "replacement=digits.translate(_SUPERSCRIPT),", "replacement=digits,"),
    ("units.py", "ends = {end: start for start, end in raised}", "ends = {start: start for start, end in raised}"),
]
M += [
    # review round 1, F1: a raised run glued after a letter or a digit is no mass number
    ("units.py", "                or (start > 0 and text[start - 1].isalnum())\n", ""),
    ("units.py", "                or (start > 0 and text[start - 1].isalnum())\n", "                or (start > 0 and text[start - 1].isdigit())\n"),
]
M += [
    # review round 2, F3: the boundary of F1's condition
    ("units.py", "                or (start > 0 and text[start - 1].isalnum())\n", "                or text[start - 1].isalnum()\n"),
    ("units.py", "                or (start > 0 and text[start - 1].isalnum())\n", "                or (start > 1 and text[start - 1].isalnum())\n"),
]
