import sys, time, tempfile
from pathlib import Path
from sci2audio.extraction import read_pdf, extract_pdf_regions
from sci2audio.layout import build_document
from sci2audio.web.figures import Catalog
for p in sorted(Path("tests/corpus/papers").glob("*.pdf")):
    data = p.read_bytes()
    doc = build_document(read_pdf(data, p.name))
    cat = Catalog(doc)
    regions = [s.region for i in range(len(doc.blocks)) for s in cat.images(i) if s.region]
    t = time.monotonic()
    out = extract_pdf_regions(p, regions[:12])
    dt = time.monotonic() - t
    sizes = [len(x) if x else None for x in out]
    total = 0
    t2=time.monotonic(); allout = extract_pdf_regions(p, regions); dt2=time.monotonic()-t2
    print(f"{p.name[:40]:40} regions={len(regions)} batch12={dt:.2f}s all={dt2:.2f}s maxKB={max([s for s in sizes if s] or [0])//1024} totalMB={sum(len(x) for x in allout if x)/1e6:.1f} none={sum(1 for x in allout if x is None)}")
