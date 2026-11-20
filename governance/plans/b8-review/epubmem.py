import os, sys, time, threading, resource, struct, zlib
sys.path.insert(0, "tests/unit")
from pathlib import Path
from epub_maker import Item, make_epub
from sci2audio.extraction.cover import png
from sci2audio.extraction import extract_epub_picture
S = Path("/tmp/claude-0/-home-user/36cd8b32-83b6-5853-be04-47d9d5c9ca5a/scratchpad")
head = png(1, 1, b"\x00\x00\x00", 3)
N = 30
items = [Item(f"i{k}", f"images/f{k}.png", "image/png", content=head + os.urandom(5_000_000), in_spine=False) for k in range(N)]
body = "".join(f'<figure><img src="images/f{k}.png" alt="f{k}"/></figure><p>t{k}.</p>' for k in range(N))
p = S / "big.epub"; p.write_bytes(make_epub("<h1>A</h1>" + body, items=items, metadata="<dc:title>T</dc:title><dc:language>en</dc:language>"))
del items
print("size MB", p.stat().st_size / 1e6)
base = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
t = time.monotonic(); r = extract_epub_picture(p, "OEBPS/images/f3.png"); print("one call s", round(time.monotonic() - t, 2), r is not None and len(r.data))
ths = [threading.Thread(target=extract_epub_picture, args=(p, f"OEBPS/images/f{k}.png")) for k in range(6)]
t = time.monotonic(); [x.start() for x in ths]; [x.join() for x in ths]
print("6 parallel s", round(time.monotonic() - t, 2), "peak RSS MB", round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024), "baseline", round(base))
