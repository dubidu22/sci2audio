M = [
    # the author-line flag
    ("footnotes.py", "        authors = False  # affiliations follow the authors (#448)", "        authors = True  # affiliations follow the authors (#448)"),
    ("footnotes.py", "                if noted and noted[0][0] < start:\n                    authors = True\n", ""),
    ("footnotes.py", "                if noted and noted[0][0] < start:", "                if noted:"),
    ("footnotes.py", "                if noted and noted[0][0] < start:", "                if noted and noted[0][0] > start:"),
    ("footnotes.py", "            authors = authors or bool(noted)\n", ""),
    ("footnotes.py", "                if _after_name(block.text, start, end):\n                    authors = True\n                elif", "                if _after_name(block.text, start, end):\n                    pass\n                elif"),
    ("footnotes.py", "                    authors and _before_affiliation(", "                    _before_affiliation("),
    ("footnotes.py", "                    authors and _before_affiliation(", "                    authors or _before_affiliation("),
    ("footnotes.py", "(start, end) for start, end in taken if _after_name(block.text, start, end)", "(start, end) for start, end in taken"),
    ("footnotes.py", "        authors = False  # affiliations follow the authors (#448)\n        for index in _title_block(document, items):\n", "        for index in _title_block(document, items):\n            authors = False\n"),
    # the split helpers
    ("footnotes.py", "    return bool(word and word[0][0].isupper() and _AFTER_NAME.match(text, end))", "    return bool(word and _AFTER_NAME.match(text, end))"),
    ("footnotes.py", "    return bool(word and word[0][0].isupper() and _AFTER_NAME.match(text, end))", "    return bool(word and word[0][0].isupper())"),
    ("footnotes.py", "    affiliation = _AFFILIATION.match(text, end)", "    affiliation = _AFFILIATION.search(text, end)"),
]
M += [
    # review round 1, F1: a comma glued before the mark belongs to the name (REVTeX)
    ("footnotes.py", '    if before.endswith(","):  # "Roe,¹ Ann Lee,²": the comma set before the mark (REVTeX)\n        before = before[:-1]\n', ""),
]
