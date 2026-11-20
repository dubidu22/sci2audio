# prototype of the proposed guards, applied by monkeypatching, then the two probes + unit tests
import sci2audio.extraction.text as t
orig_tags = t.paragraph_tags
def paragraph_tags(paragraph):
    items = t._items(paragraph)
    # M1: a bullet opens an item only at the paragraph's start, after an item line, or after a line ending in ":"
    keep = {}
    for k, tags in sorted(items.items()):
        if tags[0] == "ul" and k and not (k - 1 in keep or paragraph[k-1].rstrip().endswith(":")):
            continue
        keep[k] = tags
    longest = max((len(x) for x in paragraph if " " in x.strip()), default=0) or max(map(len, paragraph))
    out, element = [], ("p",)
    for k, text in enumerate(paragraph):
        if k in keep:
            element = keep[k]; out.append(element)
        elif k and not t._title(paragraph[k-1], text, longest):
            out.append((*element, "br"))
        else:
            element = ("p",); out.append(element)
    return out
t.paragraph_tags = paragraph_tags
import runpy, sys
for p in sys.argv[1:]:
    runpy.run_path(p)
