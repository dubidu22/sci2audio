import sys, json, tomllib
from sci2audio.testing.regression import _case, read_twice
src = open(sys.argv[1]).read()
for i, line in enumerate(l for l in src.splitlines() if l.strip() and not l.startswith("#")):
    lang, blocks = line.split("|", 1)
    raw = tomllib.loads("blocks = " + blocks)
    raw.update(id=f"p{i}", audit=0, issue=1, goal="g", language=lang, expected=[""])
    try:
        a, b = read_twice(_case(raw))
    except Exception as e:
        print(f"{i} ERR {type(e).__name__}: {e}"); continue
    flag = "  <<< RUN2 DIFF" if a != b else ""
    print(f"{i} {a}{flag}" + (f"\n   run2 {b}" if a != b else ""))
