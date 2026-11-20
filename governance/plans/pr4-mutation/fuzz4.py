"""fuzz4.py <seed> <n> <out.json>: German/English texts of hyphen chains through the chain twice."""
import json, random, sys
from types import SimpleNamespace
from sci2audio.core import BlockKind
from sci2audio.testing import make_document
from sci2audio.testing.regression import read_twice
seed, n, out = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
rnd = random.Random(seed)
TOK = ["Datenschutz", "Grundverord", "nung", "Ende", "zu", "to", "the", "Peer", "peer", "deutsch",
       "französischen", "sozial", "emotionale", "technisch", "organisatorischen", "natür", "lich",
       "Wirtschaftlich", "keit", "E", "Mail", "basiertes", "Ad", "hoc", "Analyse", "PDF", "Daten",
       "bank", "und", "oder", "u.", "bis", "2019", "Fig.", "S.", "(Smith, 2019)", "[3]",
       "https://x.org", "Abb.", "§", "1", "m²", "materiell", "rechtlichen", "Kopf", "an", "für",
       "einzig", "artigen", "mittelal", "terlichen", "rot", "grüne", "self", "based", "x"]
GAP = ["-\n", "-\n", "-", " ", " ", "\n", ". ", ", ", "-\n-\n", "‐\n"]
res = []
for i in range(n):
    lang = rnd.choice(["de", "de", "en"])
    text = "".join(rnd.choice(TOK) + rnd.choice(GAP) for _ in range(rnd.randint(2, 9))).strip() or "x"
    doc = make_document([(BlockKind.PARAGRAPH, text)], language=lang)
    try:
        first, second = read_twice(SimpleNamespace(document=doc))
        res.append([lang, text, first, second])
    except Exception as e:
        res.append([lang, text, "CRASH " + repr(e), ""])
json.dump(res, open(out, "w"), ensure_ascii=False)
