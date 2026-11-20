"""Hand mutants of utterances.py: each applied alone to a clean worktree, the cutter's tests run
(-x), the file restored. Baseline must pass first. Usage: hand.py WORKTREE"""
import subprocess, sys, pathlib
wt = pathlib.Path(sys.argv[1]); f = wt / "src/sci2audio/textprep/utterances.py"
orig = f.read_text(encoding="utf-8")
TESTS = ["tests/unit/test_textprep_utterances.py", "tests/unit/test_textprep_regression.py",
         "tests/unit/test_textprep_regression_german.py", "tests/unit/test_sentence_boundaries.py"]
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
 "482-a no reading rank": ("(rank + (rank == 4 and i in joined) + 6 * inside[i], i)", "(rank + 6 * inside[i], i)"),
 "482-b bracket penalty 5": ("(rank + (rank == 4 and i in joined) + 6 * inside[i], i)", "(rank + (rank == 4 and i in joined) + 5 * inside[i], i)"),
 "482-c no digit after": ("            text[i].isdigit() or (word_end > 0 and text[word_end - 1].isdigit())", "            (word_end > 0 and text[word_end - 1].isdigit())"),
 "482-d no digit before": ("            text[i].isdigit() or (word_end > 0 and text[word_end - 1].isdigit())", "            text[i].isdigit()"),
 "482-e no readings": ("    readings = _readings(language.split(\"-\", 1)[0].lower())", "    readings = None"),
 "482-f no abbreviation readings": ("        if \" \" in reading.strip()\n    }", "        if False\n    }"),
 "482-g no unit names": ("    phrases.update(re.escape(name) for name in (unit.singular, unit.plural) if \" \" in name)", "    pass"),
 "482-h no per": ("        phrases.add(rf\"\\S+\\s+{re.escape(per)}\\s+\\S+\")", "        pass"),
 "482-i no square/cubic": ("for key in (\"square\", \"cubic\") if key in words", "for key in () if key in words"),
 "482-j no squared/cubed": ("for key in (\"squared\", \"cubed\") if key in words", "for key in () if key in words"),
 "482-k no operators": ("    phrases.update(re.escape(reading) for reading in operators.values() if \" \" in reading)", "    pass"),
 "482-l no powers": ("    phrases.update([\"hoch minus\"] if german else [\"to the power of minus\", \"to the power of\"])", "    pass"),
 "482-m no months": ("    phrases.add(rf\"\\S+\\s+(?-i:{'|'.join(months)})\")", "    pass"),
 "482-n months any case": ("(?-i:{'|'.join(months)})", "(?:{'|'.join(months)})"),
 "482-o no look past last": ("readings.finditer(text, 0, min(len(text), last + _LONGEST_READING))", "readings.finditer(text, 0, min(len(text), last))"),
 "482-p joined_powers ignored": ("    if listed and not listed.joined_powers:", "    if listed:"),
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
