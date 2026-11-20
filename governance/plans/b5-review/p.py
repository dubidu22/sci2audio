import sys
from sci2audio.testing.regression import _case, read_twice
for i, line in enumerate(l for l in open(sys.argv[1]).read().splitlines() if l.strip() and not l.startswith("#")):
    lang, text = line.split("|", 1)
    raw = dict(id=f"p{i}", audit=0, issue=1, goal="g", language=lang, expected=[""], blocks=[{"kind": "paragraph", "text": text}])
    try:
        a, b = read_twice(_case(raw))
    except Exception as e:
        print(f"{i} ERR {type(e).__name__}: {e}"); continue
    flag = "  <<< RUN2 DIFF" if a != b else ""
    print(f"{i} {lang}| {text}\n   -> {' / '.join(a)}{flag}" + (f"\n   run2 {' / '.join(b)}" if a != b else ""))
