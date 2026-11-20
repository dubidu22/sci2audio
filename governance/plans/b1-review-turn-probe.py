import sys, math
sys.path.insert(0, "tests/unit")
from pathlib import Path
from pdf_maker import turned
from sci2audio.extraction import read_pdf
from sci2audio.core import to_data

def flat(x, out, path=""):
    if isinstance(x, dict):
        for k, v in x.items(): flat(v, out, path + "." + k)
    elif isinstance(x, (list, tuple)):
        for i, v in enumerate(x): flat(v, out, f"{path}[{i}]")
    else: out.append((path, x))
    return out

for pdf in sorted(Path("tests/corpus").rglob("*.pdf")):
    data = pdf.read_bytes()
    up = read_pdf(data, pdf.name)
    a = flat(to_data(up.pages), [])
    for turn in (90, 180, 270):
        t = read_pdf(turned(data, turn), pdf.name)
        b = flat(to_data(t.pages), [])
        if len(a) != len(b):
            print(pdf.name, turn, "LEN", len(a), len(b)); 
            # first differing text
            ta = [v for p, v in a if p.endswith(".text")]; tb = [v for p, v in b if p.endswith(".text")]
            for i,(x,y) in enumerate(zip(ta,tb)):
                if x!=y: print("  first text diff", i, repr(x)[:80], repr(y)[:80]); break
            continue
        bad = 0
        for (pa, va), (pb, vb) in zip(a, b):
            if pa != pb: print(pdf.name, turn, "PATH", pa, pb); bad += 1; break
            if isinstance(va, float) and isinstance(vb, float):
                if not math.isclose(va, vb, abs_tol=0.05):
                    bad += 1
                    if bad <= 3: print(pdf.name, turn, pa, va, vb)
            elif va != vb:
                bad += 1
                if bad <= 3: print(pdf.name, turn, pa, repr(va)[:60], repr(vb)[:60])
        print(pdf.name, turn, "diffs", bad, "of", len(a))
