import time, re
from sci2audio.textprep import utterances as U
p = U._readings("en")
for t in ("-a"*400, "word "*160):
    t0=time.perf_counter()
    for _ in range(200): list(p.finditer(t))
    a=(time.perf_counter()-t0)/200*1e3
    t0=time.perf_counter()
    for _ in range(200): U._joined(t, 400, None)
    print(repr(t[:6]), f"regex {a:.2f} ms  digit loop {(time.perf_counter()-t0)/200*1e3:.2f} ms")
