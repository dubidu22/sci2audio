import re, sys, pyphen
from collections import Counter
dic = pyphen.Pyphen(lang="de_DE")
ENDS = sys.argv[1].split(",")      # before endings
INFL = ("e", "en", "er", "es", "em")
AFTER_ENDS = sys.argv[2].split(",") # adjective endings for the after word
STEM = int(sys.argv[3]); BSTEM = int(sys.argv[5])
def before_ok(b):
    return any(b.endswith(e) and len(b)-len(e) >= BSTEM for e in ENDS)
def after_ok(a):
    for e in AFTER_ENDS:
        for i in INFL:
            s = e + i
            if a.endswith(s) and len(a) - len(s) >= STEM:
                return True
    return False
words = []
for line in open(sys.argv[4], encoding="utf-8"):
    w, f = line.split()
    if re.fullmatch(r"[a-zäöüß]{4,}", w):
        words.append((w, int(f)))
tok = Counter(); typ = Counter(); ex = []
for w, f in words:
    for b, a in dic.iterate(w):
        typ["splits"] += 1; tok["splits"] += f
        if before_ok(b) and after_ok(a):
            typ["false_keep"] += 1; tok["false_keep"] += f
            ex.append((f, f"{b}-/{a}"))
print("types", dict(typ), "tokens", dict(tok))
for f, e in sorted(ex, reverse=True)[:60]: print(f, e)
