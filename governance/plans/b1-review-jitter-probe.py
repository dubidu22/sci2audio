import sys, math; sys.path.insert(0,"tests/unit")
from pdf_maker import one_page_pdf, turned
from sci2audio.extraction import read_pdf
def word(x, y, deg, s):
    c, si = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return b"BT /F1 12 Tf %.6f %.6f %.6f %.6f %g %g Tm (%s) Tj ET\n" % (c, si, -si, c, x, y, s)
content = word(72, 700, 0.2, b"Alpha") + word(110, 700, -0.2, b"Beta") + word(140, 700, 0.2, b"Gamma")
up = one_page_pdf(content)
for name, data in (("upright", up), ("turned90", turned(up, 90)), ("turned270", turned(up, 270))):
    p = read_pdf(data, "j.pdf").pages[0]
    print(name, [l.text for l in p.lines])
