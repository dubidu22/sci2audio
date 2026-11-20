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
M = {
 "533-1 window max+1": ("width = 2 * max_chars + 2", "width = max_chars + 1"),
 "533-2 >= in window": ("if counts[-1] > max_chars or stop == end", "if counts[-1] >= max_chars or stop == end"),
 "533-3 left without -1": ("left = max(0, left - counts[min(cut - start, len(counts) - 1)] - 1)", "left = max(0, left - counts[min(cut - start, len(counts) - 1)])"),
 "533-4 tie-break i": ("key=lambda i: (abs(counts[i] - target), -i))", "key=lambda i: (abs(counts[i] - target), i))"),
 "533-5 return after never": ("    if after - start < len(counts) and counts[after - start] <= max_chars:\n        return after", "    if False:\n        return after"),
 "533-6 MIN_PIECE 30": ("MIN_PIECE = 40", "MIN_PIECE = 30"),
 "533-7 MIN_PIECE 50": ("MIN_PIECE = 40", "MIN_PIECE = 50"),
 "479-a no label-again": ("            and not _label_again(text, match.start() - len(word) + 1, match.end())\n", ""),
 "479-b case-insensitive compare": ("before[1] == after[1]", "before[1].lower() == after[1].lower()"),
 "479-c next word without dot": ('_NEXT_WORD = re.compile(r"\\s+([^\\W\\d_]+\\.?)")', '_NEXT_WORD = re.compile(r"\\s+([^\\W\\d_]+)")'),
 "479-d word after anything": ("return before is not None and after is not None and before[1] == after[1]", "return before is not None and after is not None"),
 "482-a no reading rank": (ROW, "(rank + 6 * inside[i], i)"),
 "482-b bracket penalty 5": (ROW, "(rank + (i in joined) + 5 * inside[i], i)"),
 "482-c no digit after": ("            text[i].isdigit() or (word_end > 0 and text[word_end - 1].isdigit())", "            (word_end > 0 and text[word_end - 1].isdigit())"),
 "482-d no digit before": ("            text[i].isdigit() or (word_end > 0 and text[word_end - 1].isdigit())", "            text[i].isdigit()"),
 "482-e no readings": ("    readings = _readings(language.split(\"-\", 1)[0].lower())", "    readings = None"),
 "482-f no abbreviation readings": ("        for entry in entries or ()\n", "        for entry in ()\n"),
 "482-g no unit names": ("        phrases.update((unit.singular, unit.plural))", "        pass"),
 "482-h no per": ('        joins.append(rf"(?<=\\S)\\s+{re.escape(per)}\\s+(?=\\S)")', "        pass"),
 "482-i no square/cubic": ('for key in ("square", "cubic")', "for key in ()"),
 "482-j no squared/cubed": ('for key in ("squared", "cubed")', "for key in ()"),
 "482-k no operators": ("phrases.update(OPERATORS_DE.values() if german else OPERATORS.values())", "pass"),
 "482-l no powers": ('phrases.update(["hoch minus"] if german else ["to the power of minus", "to the power of"])', "pass"),
 "482-m no months": (MONTH_JOIN, "pass"),
 "482-n months any case": ("(?-i:{'|'.join(months)})", "(?:{'|'.join(months)})"),
 "482-o no look past last": ("readings.finditer(text, 0, min(len(text), last + _LONGEST_READING))", "readings.finditer(text, 0, min(len(text), last))"),
 "482-p joined_powers ignored": ("    if listed and not listed.joined_powers:", "    if listed:"),
 "E2 word-before window 8": ("before = _WORD_BEFORE.search(text, max(0, start - 32), start)\n    after = _NEXT_WORD", "before = _WORD_BEFORE.search(text, max(0, start - 8), start)\n    after = _NEXT_WORD"),
 "E3 no left word bound": (BOUNDED, BOUNDED.replace("(?<!\\w)", "", 1)),
 "E4 no right word bound": (BOUNDED, BOUNDED.replace(")(?!\\w)|", ")|", 1)),
 "E5 range from match start": (RANGE, RANGE.replace("match.start() + 1", "match.start()")),
 "E7 match end left out": (RANGE, RANGE.replace(") + 1)", "))")),
 "E10 alternatives unsorted": ("alternatives = sorted(whole, key=len, reverse=True)", "alternatives = sorted(whole)"),
 "E11 operators swapped": ("OPERATORS_DE.values() if german else OPERATORS.values()", "OPERATORS.values() if german else OPERATORS_DE.values()"),
 "E12 no before_year": ("for reading in (entry.reads, entry.before_year, entry.after_paragraph)", "for reading in (entry.reads, entry.after_paragraph)"),
 "E13 no after_paragraph": ("for reading in (entry.reads, entry.before_year, entry.after_paragraph)", "for reading in (entry.reads, entry.before_year)"),
 "E14 only plural unit": ("        phrases.update((unit.singular, unit.plural))", "        phrases.update((unit.plural,))"),
 "E15 only squared": ('for key in ("squared", "cubed")', 'for key in ("squared",)'),
 "E16 only square": ('for key in ("square", "cubic")', 'for key in ("square",)'),
 "E17 power of only minus": ('["to the power of minus", "to the power of"]', '["to the power of minus"]'),
 "R1 no unit chain": (CHAIN, "pass"),
 "R2 chain of two only": (CHAIN, CHAIN.replace("))+", "))", 1)),
 "R3 chain names plural only": ("                for name in (unit.singular, unit.plural)\n", "                for name in (unit.plural,)\n"),
 "R4 per-only units in the chain": ("                if not unit.per_only\n", "                if True\n"),
 "R5 no out of": (OUTOF, "pass"),
 "R6 out of anywhere": (OUTOF, "whole.append(re.escape(OUT_OF))"),
 "R7 no statistics symbols": (SYMBOLS, "pass"),
 "R8 symbols of the other language": (SYMBOLS, "phrases.update(SYMBOL_READINGS if german else SYMBOL_READINGS_DE)"),
 "R9 no fractions of one": (ONES, "pass"),
 "R10 month inside a word": (MONTH_JOIN, MONTH_JOIN.replace(")(?!\\w)", ")")),
 "R11 squared inside a word": ('rf"(?<=\\S)\\s+{re.escape(words[key])}(?!\\w)"', 'rf"(?<=\\S)\\s+{re.escape(words[key])}"'),
 "N1 guard back": (ROW, "(rank + (rank == 4 and i in joined) + 6 * inside[i], i)"),
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
if len(sys.argv) > 2 and sys.argv[2] == "shapes":
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
