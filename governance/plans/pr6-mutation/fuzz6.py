"""fuzz6.py <out.json>: figure/table/formula + caption label shapes, en and de, every
category switched off in turn; counts placeholders whose notice differs between the first
run and the second run (rebuilt_from_script). Code from PYTHONPATH."""
import itertools, json, sys
from sci2audio.core import Block, BlockKind
from sci2audio.testing import make_document, rebuilt_from_script
from sci2audio.textprep import StepContext, run_steps, spoken_text
from sci2audio.textprep.steps import Category
from sci2audio.textprep.steps import DEFAULT_SWITCHED_OFF

WORDS = {"en": ["Fig.", "Figs.", "Figure", "Table", "Tab.", "Tables"],
         "de": ["Abb.", "Abbildung", "Tab.", "Tabelle", "Abbn."]}
NUMS = ["1", "3.2", "1–3", "1-3", "2–4", "1/2", "3/4", "10⁶", "3x", "2,5", "S1", "IV", "2a", "1.2–1.4",
        "3 und 4", "5 %", "2 km", "1, 2", "10³", "½", "3×", "1e5", "A.1", "2.10"]
AFTER = [": Values.", ". Verlauf der Werte.", " shows x.", " zeigt den Verlauf.", ""]
OFF = sorted({frozenset(DEFAULT_SWITCHED_OFF), frozenset(), *(frozenset({c}) for c in Category), *(DEFAULT_SWITCHED_OFF | {c} for c in Category)}, key=sorted)
bad, total = [], 0
for lang, (kind, cap) in itertools.product(["en", "de"], [(BlockKind.FIGURE, True), (BlockKind.TABLE, True), (BlockKind.FORMULA, False)]):
    for word, num, after in itertools.product(WORDS[lang], NUMS, AFTER):
        if cap:
            label = f"{word} {num}"
            blocks = [Block(kind, "x y z"), Block(BlockKind.CAPTION, label + after, label=label, describes=0)]
        else:
            if after or word != WORDS[lang][0]:
                continue
            blocks = [Block(kind, f"a = b ({num})", label=num)]
        try:
            document = make_document(blocks, lang)
        except ValueError:
            continue
        for off in OFF:
            total += 1
            context = StepContext(lang)
            try:
                first = run_steps(document, context, switched_off=off, strict=True)
                second = run_steps(rebuilt_from_script(document, first.script()), context, switched_off=off, strict=True)
            except Exception as error:
                bad.append([lang, label if cap else num, sorted(off), "ERROR", repr(error)[:200]]); continue
            one = spoken_text([p for p in first.script() if p.span.block == 0])
            two = spoken_text([p for p in second.script() if p.span.block == 0])
            if one != two:
                bad.append([lang, blocks[-1].text, sorted(map(str, off)), one, two])
json.dump({"total": total, "bad": bad}, open(sys.argv[1], "w"), ensure_ascii=False, indent=1)
print(total, "cases,", len(bad), "differ")
