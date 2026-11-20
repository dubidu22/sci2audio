"""Counterexample search for the #533 mutants: the whole cutter, mutant vs original, on seeded
random sentences. Usage: search.py SOURCE_FILE SEED N"""
import random, sys, types
from sci2audio.core import BlockKind
from sci2audio.testing import make_document
from sci2audio.textprep import StepContext, run_steps

SRC = open(sys.argv[1], encoding="utf-8").read()
MUTANTS = {
    1: ("width = 2 * max_chars + 2", "width = max_chars + 1"),
    2: ("if counts[-1] > max_chars or stop == end", "if counts[-1] >= max_chars or stop == end"),
    3: ("left = max(0, left - counts[min(cut - start, len(counts) - 1)] - 1)", "left = max(0, left - counts[min(cut - start, len(counts) - 1)])"),
    4: ("key=lambda i: (abs(counts[i] - target), -i))", "key=lambda i: (abs(counts[i] - target), i))"),
    5: ("    if after - start < len(counts) and counts[after - start] <= max_chars:\n        return after", "    if False:\n        return after"),
    6: ("MIN_PIECE = 40", "MIN_PIECE = 30"),
    7: ("MIN_PIECE = 40", "MIN_PIECE = 50"),
}
def load(src, name):
    m = types.ModuleType(name); sys.modules[name] = m
    exec(compile(src, name, "exec"), m.__dict__); return m
flat = lambda us: [(u.text, u.span, u.pause, u.continues) for u in us]
orig = load(SRC, "orig")
muts = {}
for k, (a, b) in MUTANTS.items():
    assert SRC.count(a) == 1, (k, SRC.count(a))
    muts[k] = load(SRC.replace(a, b), f"m{k}")
rng = random.Random(int(sys.argv[2]))
WORDS = {"en": ["the", "listeners", "heard", "every", "part", "of", "recording", "in", "a", "quiet", "room", "but", "which", "and", "e.g.", "3.5 %", "No. 5", "(see p. 12)", "“we hear,", "what we read”", "–", ";", ",", ":", "x", "supercalifragilistic"*2],
         "de": ["die", "Hörer", "hörten", "jeden", "Teil", "der", "Aufnahme", "im", "stillen", "Raum", "aber", "dass", "weil", "z. B.", "3,5 %", "u. a.", "(siehe S. 12)", "„wir hören,", "was wir lesen“", "–", ";", ",", ":", "Donaudampfschifffahrt"*2]}
found = {k: None for k in MUTANTS}
tries = 0
for n in range(int(sys.argv[3])):
    lang = rng.choice(["en", "de"])
    text = " ".join(rng.choice(WORDS[lang]) for _ in range(rng.randint(5, 160))).replace(" ,", ",").replace(" ;", ";").replace(" :", ":")
    text = text[0].upper() + text[1:] + "."
    if rng.random() < 0.2:
        text = text.replace(" ", "  ", rng.randint(0, 20))
    doc = make_document([(BlockKind.PARAGRAPH, text)], lang)
    run = run_steps(doc, StepContext(lang), strict=True)
    pieces = run.script()
    mc = rng.choice([20, 40, 60, 80, 100, 150, 200, 300, 400])
    want = flat(orig.cut_utterances(run.document, pieces, max_chars=mc))
    tries += 1
    for k, m in muts.items():
        if found[k] is None and flat(m.cut_utterances(run.document, pieces, max_chars=mc)) != want:
            found[k] = (mc, text)
for k, v in found.items():
    print(k, "SURVIVES" if v is None else f"differs at max_chars={v[0]}: {v[1][:300]!r}")
print("tries", tries)
