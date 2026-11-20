import sys
from misaki.espeak import EspeakG2P
g = EspeakG2P("de")
for l in [l.rstrip("\n") for l in open(sys.argv[1], encoding="utf-8") if l.strip()]:
    out = g(l)
    print(f"{l!r:45} -> {out[0] if isinstance(out, tuple) else out}")
