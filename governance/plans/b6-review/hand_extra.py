"""Hand mutants of utterances.py: each applied alone to a clean worktree, the cutter's tests run
(-x), the file restored. Baseline must pass first. Usage: hand.py WORKTREE"""
import subprocess, sys, pathlib
wt = pathlib.Path(sys.argv[1]); f = wt / "src/sci2audio/textprep/utterances.py"
orig = f.read_text(encoding="utf-8")
TESTS = ["tests/unit/test_textprep_utterances.py", "tests/unit/test_textprep_regression.py",
         "tests/unit/test_textprep_regression_german.py", "tests/unit/test_sentence_boundaries.py"]
M = {
 "E2 word-before window 8": ("before = _WORD_BEFORE.search(text, max(0, start - 32), start)\n    after = _NEXT_WORD", "before = _WORD_BEFORE.search(text, max(0, start - 8), start)\n    after = _NEXT_WORD"),
 "E3 no left word bound": ('return re.compile(rf"(?<!\\w)(?:{', 'return re.compile(rf"(?:{'),
 "E4 no right word bound": ("{'|'.join(alternatives)})(?!\\w)\"", "{'|'.join(alternatives)})\""),
 "E5 range from match start": ("for k in range(match.start() + 1, min(match.end(), last + 1))", "for k in range(match.start(), min(match.end(), last + 1))"),
 "E7 up to last only": ("for k in range(match.start() + 1, min(match.end(), last + 1))", "for k in range(match.start() + 1, min(match.end(), last))"),
 "E10 alternatives unsorted": ("alternatives = sorted(phrases, key=len, reverse=True)", "alternatives = sorted(phrases)"),
 "E11 operators swapped": ("operators = OPERATORS_DE if german else OPERATORS", "operators = OPERATORS if german else OPERATORS_DE"),
 "E12 no before_year": ("for reading in (entry.reads, entry.before_year, entry.after_paragraph)", "for reading in (entry.reads, entry.after_paragraph)"),
 "E13 no after_paragraph": ("for reading in (entry.reads, entry.before_year, entry.after_paragraph)", "for reading in (entry.reads, entry.before_year)"),
 "E14 only plural unit": ("for name in (unit.singular, unit.plural) if", "for name in (unit.plural,) if"),
 "E15 only squared": ('for key in ("squared", "cubed") if key in words', 'for key in ("squared",) if key in words'),
 "E16 only square": ('for key in ("square", "cubic") if key in words', 'for key in ("square",) if key in words'),
 "E17 power of only minus": ('["to the power of minus", "to the power of"]', '["to the power of minus"]'),
}
def run():
    return subprocess.run([sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", "-m", "not slow and not benchmark and not browser", *TESTS],
                          cwd=wt, capture_output=True, text=True, env={"PYTHONPATH": str(wt / "src"), "PATH": "/usr/bin:/bin", "HYPOTHESIS_PROFILE": "ci", "HOME": "/root"})
b = run(); print("baseline", "PASS" if b.returncode == 0 else "FAIL\n" + b.stdout[-2000:]); sys.stdout.flush()
if b.returncode: sys.exit(1)
for name, (a, c) in M.items():
    assert orig.count(a) == 1, (name, orig.count(a))
    f.write_text(orig.replace(a, c), encoding="utf-8")
    try:
        r = run()
    finally:
        f.write_text(orig, encoding="utf-8")
    killer = next((l for l in r.stdout.splitlines() if l.startswith("FAILED")), "")
    print(f"{name}: {'killed ' + killer[7:120] if r.returncode else 'SURVIVED'}"); sys.stdout.flush()
