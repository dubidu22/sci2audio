import sys, time
from sci2audio.core import BlockKind, apply_edits
from sci2audio.testing.documents import make_document
from sci2audio.textprep.utterances import cut_utterances, DEFAULT_MAX_CHARS
def cut(text, lang="en", mx=DEFAULT_MAX_CHARS):
    d = make_document([(BlockKind.PARAGRAPH, text)], lang)
    return cut_utterances(d, apply_edits(d, []), lang, mx)
shapes = {
 "word": lambda n: "word " * n,
 "dash-a": lambda n: "-a" * n,
 "a-b-sp": lambda n: "a-b-c-d-e-f-g-h-i-j-k-l-m-n-o-p-q-r-s-t-u-v-w-x-y-z-a-b-c-d-e-f-g " * (n//32),
 "per": lambda n: "x per y " * (n//4),
 "digits": lambda n: "1 2 3 " * (n//3),
 "dots": lambda n: ".a" * n,
 "longtok": lambda n: ("-" + "a" * 2000 + " ") * (n // 1000),
}
for lang in ("en","de"):
  for name, f in shapes.items():
    for n in (20000, 80000):
        t = f(n); t0=time.perf_counter(); r = cut(t, lang); dt=time.perf_counter()-t0
        print(lang, name, len(t), f"{dt:.2f}s", len(r), flush=True)
