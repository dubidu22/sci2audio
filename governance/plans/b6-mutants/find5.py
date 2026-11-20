import sys
exec(open("/tmp/claude-0/b6/mut/search.py").read().split("rng = random.Random")[0])
from sci2audio.core import apply_edits, Edit, EditKind, Span
m = muts[int(sys.argv[2])]
flatu = lambda us: [(u.text, u.span, u.continues) for u in us]
for rep in ["one two", "one two three", "one two three four", "aa bb cc dd ee ff"]:
    for rest in ["aaaa bbbb.", "aaaa bbbb cccc dddd.", "aaaa bbbb cccc dddd eeee ffff gggg."]:
        text = "x " + rest
        doc = make_document([(BlockKind.PARAGRAPH, text)])
        edit = Edit(Span(0, 0, 1), EditKind.REPLACE, "r", "x", replacement=rep)
        for mc in range(4, 40):
            p = apply_edits(doc, [edit])
            o, mm = flatu(orig.cut_utterances(doc, p, "en", mc)), flatu(m.cut_utterances(doc, p, "en", mc))
            if o != mm:
                print(repr(rep), repr(rest), mc); print(" orig", o); print(" mut ", mm); sys.exit()
print("none")
