"""Find simple texts that tell a mutant from the original. find.py SRC MUTANT"""
import sys, itertools
sys.argv += []
exec(open("/tmp/claude-0/b6/mut/search.py").read().split("rng = random.Random")[0].replace("SRC = open(sys.argv[1]", "SRC = open(sys.argv[1]"))
k = int(sys.argv[2])
m = muts[k]
from sci2audio.core import apply_edits
def run(mod, text, mc, lang="en"):
    doc = make_document([(BlockKind.PARAGRAPH, text)], lang)
    return [u.text for u in mod.cut_utterances(doc, apply_edits(doc, []), lang, mc)]
found = 0
for mc in (60, 80, 100):
    for a, b, c, d in itertools.product(range(5, 80, 3), range(1, 60, 3), range(1, 60, 4), range(1, 90, 7)):
        text = " ".join(["w" * 4] * (a // 5)) + "x, " + " ".join(["v" * 4] * (b // 5 + 1)) + "y, " + " ".join(["u" * 4] * (c // 5 + 1)) + "z, " + " ".join(["t" * 4] * (d // 5 + 1)) + "."
        o, mm = run(orig, text, mc), run(m, text, mc)
        if o != mm:
            print(mc, repr(text)); print(" orig", [len(p) for p in o], o); print(" mut ", [len(p) for p in mm]); found += 1
            if found >= 2: sys.exit()
print("none")
