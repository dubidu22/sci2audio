"""PR 5 round 2 fix mutants (#436 review round 2: B1 element symbols, S1 touching removals).
Run with mut3.py, ROOT = a clean worktree of the round 2 fix commit."""
F, H = "footnotes.py", "furniture.py"
M = [
    (H, "                if skip_start > at:\n", "                if True:\n"),  # round 2 S1
    (F, "if not at_start or affiliation is None or affiliation[1] in ELEMENTS:", "if not at_start or affiliation is None:"),
    (F, '"Rb", "Sr"', '"Sr"'),
    (F, '    "He", "Li",', '    "Li",'),
    (F, '    "He", "Li",', '    "He",'),
    (F, '"Yb", "Lu"', '"Lu"'),
    (F, "    return affiliation[1][0].isupper()\n", "    return True\n"),
]
