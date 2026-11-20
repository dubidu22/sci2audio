import shutil, subprocess, sys, os
ROOT = "/home/user/w593"
MUTANTS = [
 ("arrow-single-minus-only-right", "src/sci2audio/textprep/notation.py", '_TWO_GLYPH_ARROW = re.compile("←\\u2212→|←\\u2212|\\u2212→")', '_TWO_GLYPH_ARROW = re.compile("←\\u2212→|\\u2212→")'),
 ("arrow-no-both", "src/sci2audio/textprep/notation.py", '_TWO_GLYPH_ARROW = re.compile("←\\u2212→|←\\u2212|\\u2212→")', '_TWO_GLYPH_ARROW = re.compile("←\\u2212|\\u2212→")'),
 ("arrows-not-in-en", "src/sci2audio/textprep/numbers.py", "            *arrows(text),\n", ""),
 ("arrows-not-in-de", "src/sci2audio/textprep/numbers_de.py", "            *arrows(text),\n", ""),
 ("minus-allows-paren", "src/sci2audio/textprep/numbers.py", r"(?<![\w.,)\]}←↔])", r"(?<![\w.,\]}←↔])"),
 ("minus-allows-bracket", "src/sci2audio/textprep/numbers.py", r"(?<![\w.,)\]}←↔])", r"(?<![\w.,)}←↔])"),
 ("minus-allows-brace", "src/sci2audio/textprep/numbers.py", r"(?<![\w.,)\]}←↔])", r"(?<![\w.,)\]←↔])"),
 ("minus-allows-arrows", "src/sci2audio/textprep/numbers.py", r"(?<![\w.,)\]}←↔])", r"(?<![\w.,)\]}])"),
 ("minus-allows-leftarrow", "src/sci2audio/textprep/numbers.py", r"(?<![\w.,)\]}←↔])", r"(?<![\w.,)\]}↔])"),
 ("fraction-old", "src/sci2audio/textprep/numbers.py", r"(?<![\w.,)\]}]\u2212)", r"(?<![\w.,]\u2212)"),
 ("fraction-no-bracket", "src/sci2audio/textprep/numbers.py", r"(?<![\w.,)\]}]\u2212)", r"(?<![\w.,)}]\u2212)"),
 ("fraction-no-brace", "src/sci2audio/textprep/numbers.py", r"(?<![\w.,)\]}]\u2212)", r"(?<![\w.,)\]]\u2212)"),
 ("uhr-old", "src/sci2audio/textprep/numbers_de.py", r'_AFTER_UHR = re.compile(r"(?<!\d[:.]\d\d )(?<!\d[:.]\d\d\n)\bUhr\s+\Z")', r'_AFTER_UHR = re.compile(r"\bUhr\s+\Z")'),
 ("uhr-no-nl", "src/sci2audio/textprep/numbers_de.py", r'(?<!\d[:.]\d\d\n)', ''),
 ("uhr-colon-only", "src/sci2audio/textprep/numbers_de.py", r'(?<!\d[:.]\d\d )', r'(?<!\d[:]\d\d )'),
 ("uhr-window-8", "src/sci2audio/textprep/numbers_de.py", "if _AFTER_UHR.search(text, max(0, match.start() - 16), match.start()):", "if _AFTER_UHR.search(text, max(0, match.start() - 8), match.start()):"),
 ("hundred-off", "src/sci2audio/textprep/numbers_de.py", "        if _AFTER_HUNDRED.search(text, max(0, match.start() - 16), match.start()):\n            continue", "        if False:\n            continue"),
 ("hundred-no-lookbehind", "src/sci2audio/textprep/numbers_de.py", r'_AFTER_HUNDRED = re.compile(r"(?<![\d.,])1[1-9] hundert \Z")', r'_AFTER_HUNDRED = re.compile(r"1[1-9] hundert \Z")'),
 ("hundred-any", "src/sci2audio/textprep/numbers_de.py", r'_AFTER_HUNDRED = re.compile(r"(?<![\d.,])1[1-9] hundert \Z")', r'_AFTER_HUNDRED = re.compile(r"(?<![\d.,])\d+ hundert \Z")'),
 ("period-off", "src/sci2audio/textprep/citations.py", "        if self._dated_period(text, part, piece, match):\n            return False\n", ""),
 ("period-no-lead", "src/sci2audio/textprep/citations.py", "            and not piece[: match.start(\"authors\")].strip()\n", ""),
 ("period-any-tail", "src/sci2audio/textprep/citations.py", "            and _PLAIN_YEAR.fullmatch(piece, match.end(\"authors\")) is not None\n", ""),
 ("period-no-open", "src/sci2audio/textprep/citations.py", "            and text[part[0] - 1 : part[0]] == \"(\"\n", ""),
 ("period-no-close", "src/sci2audio/textprep/citations.py", "            and text[part[1] : part[1] + 1] == \")\"\n", ""),
 ("period-year-letter", "src/sci2audio/textprep/citations.py", r'_PLAIN_YEAR = re.compile(r"\s+(?:1[5-9]\d\d|20\d\d)\s*")', r'_PLAIN_YEAR = re.compile(r"\s+(?:1[5-9]\d\d|20\d\d)\w?\s*")'),
 ("period-year-any", "src/sci2audio/textprep/citations.py", r'_PLAIN_YEAR = re.compile(r"\s+(?:1[5-9]\d\d|20\d\d)\s*")', r'_PLAIN_YEAR = re.compile(r"\s+.*")'),
 ("period-only-yearwords", "src/sci2audio/textprep/citations.py", "        periods=YEAR_WORDS | frozenset((", "        periods=YEAR_WORDS or frozenset(("),
]
TESTS = ["tests/unit/test_textprep_numbers.py", "tests/unit/test_textprep_numbers_statistics_de.py",
         "tests/unit/test_textprep_links_citations_de.py", "tests/unit/test_textprep_regression.py",
         "tests/unit/test_textprep_regression_german.py", "tests/unit/test_textprep_citations.py"]
only = sys.argv[1:]
for name, path, old, new in MUTANTS:
    if only and name not in only: continue
    work = f"/home/user/mut/w_{name}"
    shutil.rmtree(work, ignore_errors=True)
    shutil.copytree(f"{ROOT}/src", f"{work}/src")
    p = f"{work}/{path}"
    s = open(p, encoding="utf-8").read()
    if s.count(old) != 1:
        print(name, "PATTERN COUNT", s.count(old)); continue
    open(p, "w", encoding="utf-8").write(s.replace(old, new))
    env = dict(os.environ, PYTHONPATH=f"{work}/src", HYPOTHESIS_PROFILE="ci")
    r = subprocess.run(["/home/user/sci2audio/.venv/bin/python", "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", "-n", "4", *TESTS],
                       cwd=ROOT, env=env, capture_output=True, text=True)
    last = [l for l in r.stdout.splitlines() if "passed" in l or "failed" in l][-1:] 
    print(f"{name}: {'KILLED' if r.returncode else 'SURVIVED'} {last}", flush=True)
    shutil.rmtree(work, ignore_errors=True)
