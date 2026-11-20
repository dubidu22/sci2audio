"""fuzz5.py <seed> <n> <out.json>: title blocks with sup marks and text with hidden runs and
page-break markers, through the whole chain twice (read_twice). Same texts for any code."""
import json, os, random, sys
from types import SimpleNamespace
from sci2audio.core import Block, BlockKind
from sci2audio.testing import make_document
from sci2audio.testing.regression import read_twice
seed, n, out = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
rnd = random.Random(seed)
TOK = ["Jane", "Roe", "Wasi", "Ahmed", "Zoë", "Lee", "x", "N", "and", "University", "of", "Example",
       "AI", "Lab", "the", "size", "small.", "results", "(Smith, 2019)", "[3]", "https://x.org", "e.g.",
       "u. a.", "5 mg", "2019", "Fig. 2", "z. B.", "Müller", "Abb.", "§", "m²", "37 °C", "p < .05"]
GAP = [" ", " ", ", ", "; ", ". ", "\n", "", " + "]
MARKS = ["1", "2", "1,2", "3,", "∗", "*", "†", "12", "a", "1a", " 2 "]
TAGS = [("span", "hidden"), ("span", "aria-hidden"), ("span", "epub:pagebreak"), ("span", "role:doc-pagebreak"), ("span", "lang:fr"), ("sup",)]
# FAMILY=sup: only sup marks (affiliation step); FAMILY=hidden: only hidden/page-break runs
FAMILY = os.environ.get("FAMILY", "")
if FAMILY == "sup":
    TAGS = [("sup",)]

def runs(k):
    text, ranges = "", []
    for _ in range(k):
        word = rnd.choice(TOK)
        if rnd.random() < 0.35:
            tag = rnd.choice(TAGS) if rnd.random() < 0.5 or FAMILY == "hidden" else ("sup",)
            if FAMILY == "hidden" and tag == ("sup",):
                tag = TAGS[0]
            piece = rnd.choice(MARKS) if tag == ("sup",) else word
            if "\n" not in piece:
                ranges.append((len(text), len(text) + len(piece), tag))
            text += piece
        else:
            text += word
        text += rnd.choice(GAP)
    return text.rstrip("\n ") or "x", [r for r in ranges if r[1] <= len(text.rstrip("\n ") or "x")]

res = []
for i in range(n):
    lang = rnd.choice(["en", "en", "de"])
    blocks, tags = [], {}
    for b in range(rnd.randint(1, 5)):
        if rnd.random() < 0.15:
            blocks.append((BlockKind.HEADING, rnd.choice(["Abstract", "1 Introduction", "Zusammenfassung"])))
            continue
        kind = rnd.choice([BlockKind.PARAGRAPH] * 4 + [BlockKind.LIST_ITEM, BlockKind.FOOTNOTE])
        text, ranges = runs(rnd.randint(1, 8))
        if kind is BlockKind.FOOTNOTE:
            label = rnd.choice(["1", "2", "∗"])
            text = label + " " + text
            ranges = [(s + len(label) + 1, e + len(label) + 1, t) for s, e, t in ranges]
            blocks.append(Block(kind, text, label=label))
        else:
            blocks.append((kind, text))
        tags[len(blocks) - 1] = ranges
    try:
        doc = make_document(blocks, lang, tags=tags)
    except ValueError:
        continue
    try:
        first, second = read_twice(SimpleNamespace(document=doc))
        res.append([lang, repr(blocks) + " " + repr(tags), first, second])
    except Exception as e:
        res.append([lang, repr(blocks) + " " + repr(tags), "CRASH " + repr(e), ""])
json.dump(res, open(out, "w"), ensure_ascii=False)
