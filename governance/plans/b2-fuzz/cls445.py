import json, sys
r = json.load(open(sys.argv[1]))
norm = lambda xs: [" ".join(x.split()) for x in xs] if isinstance(xs, list) else xs
crash = [x for x in r if str(x[2]).startswith("CRASH")]
rows = [x for x in r if x not in crash]
pre = [x for x in rows if norm(x[4]) != norm(x[5])]
d1 = [x for x in rows if norm(x[2]) != norm(x[3]) and norm(x[4]) == norm(x[5])]
d2 = [x for x in rows if norm(x[2]) != norm(x[4]) and norm(x[4]) == norm(x[5])]
f4 = [x for x in rows if x[6] != x[7] and x not in pre]
print("four-step replacements differ from no-run text (no-run stable):", len(f4))
print(f"texts {len(rows)} crashes {len(crash)} | no-run text unstable (pre-existing) {len(pre)} | hidden-only second-run diffs {len(d1)} | first run differs from no-run text {len(d2)}")
show = int(sys.argv[2]) if len(sys.argv) > 2 else 0
for x in crash[:3]: print("CRASH", x[1], x[2])
for x in (f4 if len(sys.argv)>3 else d2)[:show]:
    print(x[0], x[1])
    for a, b, c in zip(norm(x[2]), norm(x[3]), norm(x[4])):
        if a != c or a != b: print("   r1:", a, "\n   r2:", b, "\n   n1:", c)
