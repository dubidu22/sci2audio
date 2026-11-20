import json, sys
main = json.load(open(sys.argv[1])); pr = json.load(open(sys.argv[2]))
crash = [p for p in pr if str(p[2]).startswith("CRASH")]
only = [(m, p) for m, p in zip(main, pr) if p[2] != p[3] and m[2] == m[3]]
both = sum(1 for m, p in zip(main, pr) if p[2] != p[3] and m[2] != m[3])
changed = sum(1 for m, p in zip(main, pr) if p[2] != m[2])
print(f"texts {len(pr)} crashes {len(crash)} pr-only second-run diffs {len(only)} on both {both} first-run readings changed {changed}")
for m, p in only[:15]: print(repr(p[1]), p[0], "\n   1:", p[2], "\n   2:", p[3])
