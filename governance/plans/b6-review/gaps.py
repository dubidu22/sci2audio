import sys
sys.path.insert(0, "tests/unit")
from test_textprep_utterances import _rebuilt_cuts
CASES = [
 ("en", "95% CI", "confidence interval"), ("en", "the OR", "odds ratio"), ("en", "5 N m", "newton metres"),
 ("en", "3 eV Å", ""), ("de", "1/2 der", "ein halb"), ("de", "1/3 der", "ein Drittel"),
 ("de", "das R²", "R Quadrat"), ("de", "das OR", "Odds Ratio"), ("de", "[MH17]", "Quelle MH17"),
 ("en", "[Knu84]", "Reference Knu84"), ("en", "12/20", "out of"), ("en", "x ≥ 3", "greater than or equal to"),
 ("de", "d. h.", "das heißt"), ("en", "i.e.", "that is"), ("de", "ηp²", "Eta-Quadrat"),
 ("en", "the R²", "R squared"), ("de", "ca. 20 min", "zirka 20 Minuten"),
]
for language, printed, read in CASES:
    filler = "die Hörer hörten jede Stelle" if language == "de" else "the people heard every word"
    words = filler.split() * 30
    bad = 0; split = 0; ex = None
    for before in range(20, 50):
        text = " ".join([*words[:before], printed, *words[: 75 - before]]) + "."
        first, second = _rebuilt_cuts(text, language)
        if first != second:
            bad += 1; ex = ex or (first[0][-50:], second[0][-50:])
    print(f"{language} {printed!r:14} differ {bad}/30", ex or "")
