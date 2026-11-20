import importlib.util, random, sys, time
from sci2audio.core import Box, Drawing
from sci2audio.layout import order as new
spec = importlib.util.spec_from_file_location("oldorder", "/home/user/wt-bf/src/sci2audio/layout/order.py")
old = importlib.util.module_from_spec(spec); sys.modules["oldorder"] = old; spec.loader.exec_module(old)
def part(els):
    return sorted(sorted(g.id for g in e.graphics) for e in els)
rng = random.Random(int(sys.argv[1]) if len(sys.argv) > 1 else 1)
bad = 0
for trial in range(3000):
    n = rng.randint(1, 120)
    reach = rng.choice([0.0, 0.5, 2.0, 2.0, 3.7, 10.0])
    grid = rng.choice([None, 1.0, 2.0, 0.5, 16.0])
    span = rng.choice([30, 100, 600])
    gs = []
    for i in range(n):
        def c(lo, hi):
            v = rng.uniform(lo, hi)
            return round(v / grid) * grid if grid else v
        x0, y0 = c(-20, span), c(-20, span)
        w = c(0, rng.choice([2, 20, 200])); h = c(0, rng.choice([2, 20, 200, 1000]))
        gs.append(Drawing(f"d{i}", Box(x0, y0, x0 + abs(w), y0 + abs(h))))
    a, b = part(old.figures(gs, reach)), part(new.figures(gs, reach))
    if a != b:
        bad += 1
        if bad < 3: print("MISMATCH", trial, n, reach, grid)
    # order check
    oa = [tuple(g.id for g in e.graphics) for e in old.figures(gs, reach)]
    ob = [tuple(g.id for g in e.graphics) for e in new.figures(gs, reach)]
    if oa != ob:
        bad += 1
        if bad < 3: print("ORDER", trial)
print("mismatches", bad)
