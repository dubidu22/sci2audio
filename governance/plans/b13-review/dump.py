import sys, pickle, pathlib
from sci2audio.layout import build
from sci2audio.layout.build import build_document, columns_per_page
from sci2audio.layout.settings import LayoutSettings
from sci2audio.layout.furniture import find_furniture
import sci2audio.extraction as ex
out = {}
for p in sorted(pathlib.Path(sys.argv[1]).glob("*.pdf")):
    content = ex.extract_pdf(p)
    s = LayoutSettings()
    furn = find_furniture(content, s)
    doc = build_document(content, s)
    blocks = [(b.kind.name, b.text, tuple(x.item for x in b.parts), b.describes) for b in doc.blocks]
    out[p.stem] = dict(furn={k: v.name for k, v in furn.items()}, blocks=blocks, cols=columns_per_page(content, s))
pickle.dump(out, open(sys.argv[2], "wb"))
