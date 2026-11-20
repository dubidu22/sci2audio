"""Round 2 hand mutants of utterances.py (PR #616 fix): the author's 27 and the reviewer's E2 to
E17 re-targeted at the new code, plus mutants of the round-1 fix. Each applied alone to a clean
worktree, the cutter's tests run (-x), the file restored; baseline first.
Usage: hand_r2.py WORKTREE [shapes]  ("shapes": each F1 part removed, only its long-sentence test)"""
import subprocess, sys, pathlib
wt = pathlib.Path(sys.argv[1]); f = wt / "src/sci2audio/textprep/utterances.py"
orig = f.read_text(encoding="utf-8")
TESTS = ["tests/unit/test_textprep_utterances.py", "tests/unit/test_textprep_regression.py",
         "tests/unit/test_textprep_regression_german.py", "tests/unit/test_sentence_boundaries.py"]
ROW = "(rank + (i in joined) + 6 * inside[i], i)"
BOUNDED = "rf\"(?<!\\w)(?:{'|'.join(alternatives)})(?!\\w)|{'|'.join(joins)}\""
RANGE = "range(match.start() + 1, min(match.end(), last, len(text) - 1) + 1)"
CHAIN = 'whole.append(rf"(?:{names})(?:\\s+(?:{names}))+")'
OUTOF = 'whole.append(rf"(?<=\\d\\s){re.escape(OUT_OF)}(?=\\s+\\d)")'
SYMBOLS = "phrases.update(SYMBOL_READINGS_DE if german else SYMBOL_READINGS)"
ONES = "phrases.update(FRACTIONS_OF_ONE if german else ())"
MONTH_JOIN = "joins.append(rf\"(?<=\\S)\\s+(?-i:{'|'.join(months)})(?!\\w)\")"
M = {  # round 2 (T2): the reviewer's mutmut survivors that a test should kill
 "12 word-before from 1": ("before = _WORD_BEFORE.search(text, max(0, start - 32), start)\n    after = _NEXT_WORD", "before = _WORD_BEFORE.search(text, max(1, start - 32), start)\n    after = _NEXT_WORD"),
 "37 finditer from 1": ("readings.finditer(text, 0, ", "readings.finditer(text, 1, "),
 "8 range from 2": ("for i in range(1, min(last, len(text) - 1) + 1):", "for i in range(2, min(last, len(text) - 1) + 1):"),
 "26 word_end > 1": ("(word_end > 0 and text[word_end - 1].isdigit())", "(word_end > 1 and text[word_end - 1].isdigit())"),
 "55 last dropped": ("min(match.end(), last, len(text) - 1) + 1", "min(match.end(), len(text) - 1) + 1"),
 "58 len - 2": ("min(match.end(), last, len(text) - 1) + 1", "min(match.end(), last, len(text) - 2) + 1"),
}
SHAPES = {  # each F1 part removed: its new long-sentence shape must fail on its own
 "R1 no unit chain": ("en-5 N m-5 newton metres",),
 "R5 no out of": ("en-12/20-12 out of 20",),
 "R7 no statistics symbols": ("en-95% CI-confidence interval", "de-\\u03b7p\\xb2-partielles Eta-Quadrat"),
 "R9 no fractions of one": ("de-1/2 der-ein halb der",),
}
NODE = "tests/unit/test_textprep_utterances.py::test_a_long_sentence_is_cut_outside_a_reading_on_both_runs"
def run(*args):
    return subprocess.run([sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", "-p", "no:randomly", "-m", "not slow and not benchmark and not browser", *args],
                          cwd=wt, capture_output=True, text=True, env={"PYTHONPATH": str(wt / "src"), "PATH": "/usr/bin:/bin", "HYPOTHESIS_PROFILE": "ci", "HOME": "/root"})
def mutate(a, c, *args):
    assert orig.count(a) == 1, (a, orig.count(a))
    f.write_text(orig.replace(a, c), encoding="utf-8")
    try:
        return run(*args)
    finally:
        f.write_text(orig, encoding="utf-8")
if False:
    for name, ids in SHAPES.items():
        for id_ in ids:
            node = f"{NODE}[{id_}]"
            base = run(node)
            r = mutate(*M[name], node)
            print(f"{name} / {id_}: baseline {'PASS' if base.returncode == 0 else 'FAIL'}, mutant {'FAIL (killed)' if r.returncode == 1 else 'PASS (survived)' if r.returncode == 0 else 'ERROR'}", flush=True)
    sys.exit()
if len(sys.argv) > 2:  # only the named mutants
    M = {name: M[name] for name in sys.argv[2:]}
b = run(*TESTS); print("baseline", "PASS" if b.returncode == 0 else "FAIL\n" + b.stdout[-2000:], flush=True)
if b.returncode: sys.exit(1)
for name, (a, c) in M.items():
    r = mutate(a, c, *TESTS)
    killer = next((l for l in r.stdout.splitlines() if l.startswith("FAILED")), "")
    print(f"{name}: {'killed ' + killer[7:140] if r.returncode else 'SURVIVED'}", flush=True)
