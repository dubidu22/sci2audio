import sys
sys.path.insert(0, "tests/unit")
from test_layout_code import TextLine, TextRun, Box, prose, code, PITCH, build_document, content
from sci2audio.core import BlockKind
import itertools
ids = itertools.count()
L1, R1, L2, R2 = 70.0, 290.0, 306.0, 526.0
def tl(runs, y, x0, x1): return TextLine(f"q{next(ids)}", runs, Box(x0, y, x1, y + 10))
lines = []
for k in range(20):
    lines.append(tl(prose(f"Left column running text line {k} here."), 100 + PITCH*k, L1, R1 if k < 19 else 200))
# listing A in col 1 at foot, caption below
lines += [tl(code("import a"), 420, L1, L1+48), tl(code("a.run()"), 434, L1, L1+42)]
lines.append(tl(prose(sys.argv[1] if len(sys.argv) > 1 else "Listing 1: First."), 460, L1, L1+120))
# col 2: listing B at top, caption below, then prose
lines += [tl(code("import b"), 100, L2, L2+48), tl(code("b.run()"), 114, L2, L2+42)]
lines.append(tl(prose("Listing 2: Second."), 140, L2, L2+120))
for k in range(20):
    lines.append(tl(prose(f"Right column running text line {k} here."), 170 + PITCH*k, L2, R2 if k < 19 else 400))
doc = build_document(content(lines))
for i, b in enumerate(doc.blocks):
    print(i, b.kind.value, repr(b.text[:30]), b.label, b.describes)
