import sys, time
from sci2audio.core import Box
from sci2audio.layout.order import touching
for h in (1e3, 1e5, 1e7, 1e9):
    boxes = [Box(0, -h, 10, h), Box(5, 0, 20, 10)] + [Box(30 + i, 0, 31 + i, 500) for i in range(0, 2000, 3)]
    t = time.process_time(); touching(boxes, 2.0); print(f"height ±{h:g}: {time.process_time()-t:.2f}s", flush=True)
