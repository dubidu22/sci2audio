"""fuzz445.py <seed> <n> <out.json>: fuzz5's FAMILY=hidden texts; each read twice, and the same
text without its hidden runs read twice. Rows: lang, doc, r1, r2, n1, n2."""
import json, random, sys
from types import SimpleNamespace
from sci2audio.core import Block, BlockKind
from sci2audio.testing import make_document
from sci2audio.testing.regression import read_twice, run_case
FOUR = {'statistics','numbers','units','abbreviations'}
def four(doc):
    run = run_case(SimpleNamespace(document=doc, switched_off=DEFAULT_SWITCHED_OFF))
    return sorted((e.step, e.replacement or '') for e in run.accepted if e.step in FOUR)
from sci2audio.textprep.steps import DEFAULT_SWITCHED_OFF, StepContext
from sci2audio.textprep.furniture import HiddenRunStep
seed, n, out = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
rnd = random.Random(seed)
TOK = ["Jane", "Roe", "Wasi", "Ahmed", "Zoë", "Lee", "x", "N", "and", "University", "of", "Example",
       "AI", "Lab", "the", "size", "small.", "results", "(Smith, 2019)", "[3]", "https://x.org", "e.g.",
       "u. a.", "5 mg", "2019", "Fig. 2", "z. B.", "Müller", "Abb.", "§", "m²", "37 °C", "p < .05",
       "5", "10", "kg", "°C", ".05", "<", "=", "e.", "g.", "z.", "B.", "1–3", "−4", "x²", "%", "km/h", "3:4"]
GAP = [" ", " ", ", ", "; ", ". ", "\n", "", " + "]
TAGS = [("span", "hidden"), ("span", "aria-hidden"), ("span", "epub:pagebreak"), ("span", "role:doc-pagebreak"), ("span", "lang:fr")]
HIDE = {"hidden", "aria-hidden", "epub:pagebreak", "role:doc-pagebreak"}

def runs(k):
    text, ranges = "", []
    for _ in range(k):
        word = rnd.choice(TOK)
        if rnd.random() < 0.35:
            tag = rnd.choice(TAGS)
            if "\n" not in word:
                ranges.append((len(text), len(text) + len(word), tag))
        text += word
        text += rnd.choice(GAP)
    t = text.rstrip("\n ") or "x"
    return t, [r for r in ranges if r[1] <= len(t)]

def without(blocks, tags, doc, lang):
    edits = HiddenRunStep().find(doc, StepContext(lang, switched_off=DEFAULT_SWITCHED_OFF))
    cut = {}
    for e in edits:
        cut.setdefault(e.span.block, []).append((e.span.start, e.span.end))
    nb, nt = [], {}
    for i, b in enumerate(blocks):
        kind, text = (b.kind, b.text) if isinstance(b, Block) else b
        spans = sorted(cut.get(i, []))
        keep = []  # map old -> new
        new, at, old2new = "", 0, {}
        for s, e in spans + [(len(text), len(text))]:
            piece = text[at:s]
            for j in range(at, s): old2new[j] = len(new) + (j - at)
            new += piece
            at = e
        rr = []
        for s, e, t in tags.get(i, []):
            if t[-1] in HIDE: continue
            m = [old2new.get(j) for j in range(s, e)]
            if all(x is not None for x in m) and m == list(range(m[0], m[0] + len(m))):
                rr.append((m[0], m[-1] + 1, t))
        nt[i] = rr
        nb.append(Block(kind, new, label=b.label) if isinstance(b, Block) else (kind, new))
    return nb, nt

res = []
for i in range(n):
    lang = rnd.choice(["en", "en", "de"])
    blocks, tags = [], {}
    for b in range(rnd.randint(1, 4)):
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
    if not any(t[-1] in HIDE for r in tags.values() for *_, t in r):
        continue
    try:
        r1, r2 = read_twice(SimpleNamespace(document=doc, switched_off=DEFAULT_SWITCHED_OFF))
        nb, nt = without(blocks, tags, doc, lang)
        n1, n2 = read_twice(SimpleNamespace(document=make_document(nb, lang, tags=nt), switched_off=DEFAULT_SWITCHED_OFF))
        nd = make_document(nb, lang, tags=nt)
        res.append([lang, repr(blocks) + " " + repr(tags), r1, r2, n1, n2, four(doc), four(nd)])
    except Exception as e:
        res.append([lang, repr(blocks) + " " + repr(tags), "CRASH " + repr(e), "", "", ""])
json.dump(res, open(out, "w"), ensure_ascii=False)
