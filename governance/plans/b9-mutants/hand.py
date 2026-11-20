"""Hand mutants of the B9 code (citations.py, links.py): each applied alone to a clean worktree,
the citation, link and regression tests run (-x), the file restored. Baseline must pass first.
Usage: hand.py WORKTREE"""
import subprocess, sys, pathlib
wt = pathlib.Path(sys.argv[1])
FILES = {"c": wt / "src/sci2audio/textprep/citations.py", "l": wt / "src/sci2audio/textprep/links.py"}
TESTS = ["tests/unit/test_textprep_pairs_pages_and_nests.py", "tests/unit/test_textprep_citations.py",
         "tests/unit/test_textprep_links.py", "tests/unit/test_textprep_links_in_brackets.py",
         "tests/unit/test_textprep_links_citations_de.py", "tests/unit/test_textprep_regression.py",
         "tests/unit/test_textprep_regression_german.py"]
# the linear-time tests run only for the mutants that can change time alone (415-u, the
# Windows fix); the rest skip them, which keeps a run under an hour
SLOW = ("415-u",)
KEEP = "not linear"
M = {
 # 414 list runs
 "414-a no list gap and-form": ("c", r'self.list_gap = re.compile(rf"\s*,\s*|(?:\s*,)?\s+(?P<join>{words.and_word})\s+")', r'self.list_gap = re.compile(rf"\s*,\s*(?P<join>(?!))?")'),
 "414-b no comma-only gap": ("c", r'self.list_gap = re.compile(rf"\s*,\s*|(?:\s*,)?\s+(?P<join>{words.and_word})\s+")', r'self.list_gap = re.compile(rf"(?:\s*,)?\s+(?P<join>{words.and_word})\s+")'),
 "414-c no Oxford comma": ("c", r'self.list_gap = re.compile(rf"\s*,\s*|(?:\s*,)?\s+(?P<join>{words.and_word})\s+")', r'self.list_gap = re.compile(rf"\s*,\s*|\s+(?P<join>{words.and_word})\s+")'),
 "414-d or joins too": ("c", r'self.list_gap = re.compile(rf"\s*,\s*|(?:\s*,)?\s+(?P<join>{words.and_word})\s+")', r'self.list_gap = re.compile(rf"\s*,\s*|(?:\s*,)?\s+(?P<join>{words.and_word}|{words.or_word})\s+")'),
 "414-e no or exclusion": ("c", "if last > first and not self.or_after.match(text, squares[last].close + 1):", "if last > first:"),
 "414-f kinds may mix": ("c", "or self._item_kind(text, ahead) != kind", "or self._item_kind(text, ahead) is None"),
 "414-g no glued-number check": ("c", "                    or _NUMBER_GLUED_AFTER.match(text, ahead.close + 1)\n", ""),
 "414-i list ends at its first and": ("c", "                self._following[squares[last].open] = ahead\n                last += 1\n", "                self._following[squares[last].open] = ahead\n                last += 1\n                if gap[\"join\"] is not None:\n                    break\n"),
 "414-i3 head kind any": ("c", "            kind = self._item_kind(text, head)\n", "            kind = self._item_kind(text, head) or \"numbers\"\n"),
 "414-j no decimal check": ("c", "        if self._decimal_interval(inside):\n            return None\n        if _keys(inside, self.keys) is not None:", "        if _keys(inside, self.keys) is not None:"),
 "414-l needed pair any length": ("c", "if len(listed) != 1 or self.words.and_word not in self.words.before:", "if self.words.and_word not in self.words.before:"),
 "414-m needed pair no and": ("c", 'return gap is not None and gap["join"] is not None', "return gap is not None"),
 "414-n subject at head end": ("c", ") and not self._is_subject(text, at, end):", ") and not self._is_subject(text, at, node.close + 1):"),
 "414-o ref word list end": ("c", "                    text, node.open, end, inside, start, start + len(previous)", "                    text, node.open, node.close + 1, inside, start, start + len(previous)"),
 "414-p printed head only": ("c", "        printed = _printed(text[node.open : end])\n        word =", "        printed = _printed(text[node.open : node.close + 1])\n        word ="),
 # 415 nests
 "415-a no join word in part": ("c", r'rf"\A\s*(?:(?:{words.and_word}|&)\s+)?(?:(?:{leads})\s+)*"', r'rf"\A\s*(?:(?:{leads})\s+)*"'),
 "415-b empty parts kept": ("c", "            if number and not text[start + 1 : end].strip():\n                continue", "            if False:\n                continue"),
 "415-c year shell needs two": ("c", "        if not node.children:\n            return False\n        return _SHELL_YEAR", "        if len(node.children) < 2:\n            return False\n        return _SHELL_YEAR"),
 "415-d no early path": ("c", "            self._only_items(text, node)\n        ):", "            False\n        ):"),
 "415-e early path ignores count": ("c", "            if len(listed) == len(inner):", "            if listed:"),
 "415-f only_items no lead": ("c", "        if gaps[0].strip() and not self._only_lead_left(gaps[0]):", "        if gaps[0].strip():"),
 "415-g only_items any lead": ("c", "        if gaps[0].strip() and not self._only_lead_left(gaps[0]):", "        if False:"),
 "415-h only_items no separator": ("c", "            not gap.strip() or self.item_separator.fullmatch(gap) is not None for gap in gaps[1:]", "            not gap.strip() for gap in gaps[1:]"),
 "415-i only_items any gap": ("c", "            not gap.strip() or self.item_separator.fullmatch(gap) is not None for gap in gaps[1:]", "            True for gap in gaps[1:]"),
 "415-j only_items no shell year": ("c", "        if self._year_shell(text, node):\n            last = node.children[-1].close + 1", "        if False:\n            last = node.children[-1].close + 1"),
 "415-l separator no join word": ("c", r'self.item_separator = re.compile(rf"\s*(?:[;,]\s*)+(?:(?:{words.and_word}|&)\s+)?")', r'self.item_separator = re.compile(rf"\s*(?:[;,]\s*)+")'),
 "415-m separator one mark": ("c", r'self.item_separator = re.compile(rf"\s*(?:[;,]\s*)+(?:(?:{words.and_word}|&)\s+)?")', r'self.item_separator = re.compile(rf"\s*[;,]\s*(?:(?:{words.and_word}|&)\s+)?")'),
 "415-n before no join word": ("c", r'self.item_before = re.compile(rf"[;,]\s*(?:(?:{words.and_word}|&)\s+)?\Z")', r'self.item_before = re.compile(rf"[;,]\s*\Z")'),
 "415-o ahead needs separator": ("c", "            ahead = self.item_after.match(after) is not None or not after.strip()", "            ahead = self.item_after.match(after) is not None"),
 "415-r no lead before first": ("c", "is not None or self._only_lead_left(before)", "is not None or not before.strip()"),
 "415-s keeps_text off": ("c", " or _keeps_text(nest, node):", ":"),
 "415-t keeps_text any": ("c", "    return bool(found) and not (\n        len(found) == 1 and found[0][0] <= node.open and node.close < found[0][1]\n    )", "    return bool(found)"),
 # 402 join before
 "415-u item may hold brackets": ("c", "            if child.children or not handled:", "            if not handled:"),
 "621-a M1 any decided item beside parts": ("c", "any_decided=False)", "any_decided=True)"),
 "621-b M1 no removed-whole check": ("c", "            if not any_decided and (len(handled) != 1", "            if False and (len(handled) != 1"),
 "621-c M2 no join word after leads": ("c", 'rf"(?:(?:{words.and_word}|&)\\s+)?(?P<authors>{_authors(words)})"', 'rf"(?P<authors>{_authors(words)})"'),
 "621-d M2 join part after any part": ("c", "previous or self.joined_part.match(text, part[0], part[1]) is None", "True"),
 "621-e M2 no join part first": ("c", "        previous = True  # the first part", "        previous = False  # the first part"),
 "621-f M3 no pair after a rejected head": ("c", "            pair = self._pair(text, node) if listed is None else None", "            pair = None"),
 "621-g M3 pair with Oxford comma": ("c", "        if self.pair_gap.fullmatch(text, node.close + 1, ahead.open) is None:", "        if self.list_gap.fullmatch(text, node.close + 1, ahead.open) is None:"),
 "621-i M3 no next of run": ("c", "                self._following[squares[last].open] = ahead\n", ""),
 "402-a no join before": ("l", "                    start, join = _join_before(text, start, end, claimed, words)\n", "                    pass\n"),
 "402-b also when a join went after": ("l", "                if bare and not join:\n                    start, join = _join_before", "                if bare:\n                    start, join = _join_before"),
 "402-c not only bare": ("l", "                if bare and not join:\n                    start, join = _join_before", "                if not join:\n                    start, join = _join_before"),
 "402-d any word before": ("l", "    if not left or not left.group(1)[0].isupper():", "    if not left:"),
 "402-e sentence start too": ("l", '    if _starts_sentence(text, window + left.start(1), -1, words.abbreviations):\n        return start, ""  #', '    if False:\n        return start, ""  #'),
 "402-g comma stays": ("l", r"(\s*,)?\s+({listed})\Z", r"\s+({listed})\Z"),
 "402-h window from 0": ("l", "    window = max(claimed, start - _LOOK_BACK)\n    left = re.search(\n        rf\"(?<!\\S)", "    window = max(0, start - _LOOK_BACK)\n    left = re.search(\n        rf\"(?<!\\S)"),
 "402-i no left bound": ("l", r'rf"(?<!\S)([^\W\d_][\w’' + "'" + r'-]*)', r'rf"([^\W\d_][\w’' + "'" + r'-]*)'),
}
def run():
    global KEEP
    return subprocess.run([sys.executable, "-m", "pytest", "-q", "-x", "-n", "4", "-p", "no:cacheprovider", "-p", "no:randomly", "-m", "not slow and not benchmark and not browser", "-k", KEEP, *TESTS],
                          cwd=wt, capture_output=True, text=True, env={"PYTHONPATH": str(wt / "src"), "PATH": "/usr/bin:/bin", "HYPOTHESIS_PROFILE": "ci", "HOME": "/root"})
origs = {k: f.read_text(encoding="utf-8") for k, f in FILES.items()}
for name, (k, a, c) in M.items():
    assert origs[k].count(a) == 1, (name, origs[k].count(a))
b = run(); print("baseline", "PASS" if b.returncode == 0 else "FAIL\n" + b.stdout[-2000:]); sys.stdout.flush()
if b.returncode: sys.exit(1)
only = sys.argv[2:]
KEEP = "not linear"
for name, (k, a, c) in M.items():
    if only and not any(name.startswith(o) for o in only):
        continue
    f = FILES[k]
    KEEP = "" if name.startswith(SLOW) else "not linear"
    f.write_text(origs[k].replace(a, c), encoding="utf-8")
    try:
        r = run()
    finally:
        f.write_text(origs[k], encoding="utf-8")
    killer = next((l for l in r.stdout.splitlines() if l.startswith("FAILED") or l.startswith("ERROR")), "")
    print(f"{name}: {'killed ' + killer[7:140] if r.returncode else 'SURVIVED'}"); sys.stdout.flush()
