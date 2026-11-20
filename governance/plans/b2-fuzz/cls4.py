import json, sys
from collections import Counter
norm=lambda xs:[" ".join(x.split()) for x in xs]
for f in sys.argv[1:]:
    r=json.load(open(f)); n=0; pre=0
    for x in r:
        if str(x[2]).startswith("CRASH"): print("CRASH", x[2]); continue
        if norm(x[4])!=norm(x[5]): pre+=1; continue
        a=Counter(tuple(t) for t in x[6] if t[1]); b=Counter(tuple(t) for t in x[7] if t[1])
        if a!=b:
            n+=1
            if "-v" in sys.argv[0:1] or len(sys.argv)>0 and n<=int(__import__('os').environ.get('SHOW','0')):
                print("  ", x[0], dict(a-b), dict(b-a), x[1][:300])
    print(f, "texts", len(r), "no-run unstable", pre, "four-step replacements differ", n)
