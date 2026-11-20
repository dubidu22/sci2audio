import sys; sys.path.insert(0, "tests/unit")
from test_layout import LEFT, RIGHT, content, line
from sci2audio.core import BlockKind, Box, Drawing, TextLine, TextRun
from sci2audio.layout import build_document

def piece(name, text, size, x0, y0, x1, y1):
    b = Box(x0, y0, x1, y1)
    return TextLine(name, (TextRun(text, "Times", size, box=b),), b)

def page(lead, gap=0.0):
    top = 100.0
    lines = [line("This is the first line of the paragraph, set in ten point Times", LEFT, top, RIGHT)]
    y = top + lead  # row of the fraction line
    # stacked fraction at the start of the line: numerator above the axis, bar, denominator below
    axis = y + 5.5
    num = piece("num", "a", 7, LEFT + 1, axis - 7.2, LEFT + 5, axis - 0.6)
    den = piece("den", "b", 7, LEFT + 1, axis + 1.0 + gap, LEFT + 5, axis + 7.6 + gap)
    rest = piece("rest", "is the ratio we use throughout the rest of this short paper", 10, LEFT + 10, y, RIGHT, y + 10)
    nxt = line("and this third line goes on with the paragraph to its very end", LEFT, y + lead, RIGHT)
    last = line("which ends here.", LEFT, y + 2 * lead, LEFT + 80)
    bar = Drawing("bar", Box(LEFT, axis - 0.2, LEFT + 6, axis + 0.2))
    doc = build_document(content([lines[0], num, rest, den, nxt, last], drawings=(bar,)))
    return [b.text for b in doc.blocks if b.kind is BlockKind.PARAGRAPH]

for lead in (14, 12, 11, 10.5):
    print(lead, page(lead))
from sci2audio.layout import paragraphs as P, geometry as G
orig = P._over
def spy(bar, upper, lower, settings, size):
    r = orig(bar, upper, lower, settings, size)
    print("  _over", upper.line.id if upper.line else None, lower.line.id if lower.line else None, bar, r, "fb", G.fraction_bar(bar, upper.line, lower.line, size, settings.fraction_bar, settings.fraction_reach) if upper.line and lower.line else None)
    return r
P._over = spy
od = P._denominator
def spyd(group, element, edges, settings, size, bars):
    r = od(group, element, edges, settings, size, bars)
    print("  _denominator", [e.line.id if e.line else None for e in group], element.line.id if element.line else None, r, "bars", list(bars.meeting(P.union([e.box for e in group if e.line]))) if group else None)
    return r
P._denominator = spyd
print(page(12))
