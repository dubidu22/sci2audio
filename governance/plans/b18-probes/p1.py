import sys, ctypes, io, collections
import pypdfium2 as pdfium, pypdfium2.raw as raw
from fontTools.ttLib import TTFont
from fontTools.ttLib.standardGlyphOrder import standardGlyphOrder as MAC
from fontTools.agl import toUnicode
doc = pdfium.PdfDocument(sys.argv[1])
fonts = {}; used = collections.defaultdict(collections.Counter); seq = collections.defaultdict(list)
name = ctypes.create_string_buffer(256); flags = ctypes.c_int()
for p in range(len(doc)):
    tp = doc[p].get_textpage(); h = tp.raw
    for i in range(tp.count_chars()):
        code = raw.FPDFText_GetUnicode(h, i)
        n = raw.FPDFText_GetFontInfo(h, i, name, 256, ctypes.byref(flags))
        fn = name.value.decode()
        used[fn][code] += 1
        seq[(fn,p)].append(code)
        if fn not in fonts:
            t = raw.FPDFText_GetTextObject(h, i); f = raw.FPDFTextObj_GetFont(t)
            size = ctypes.c_size_t(); raw.FPDFFont_GetFontData(f, None, 0, ctypes.byref(size))
            buf = (ctypes.c_ubyte*size.value)(); raw.FPDFFont_GetFontData(f, buf, size.value, ctypes.byref(size))
            fonts[fn] = bytes(buf)
for fn, data in fonts.items():
    tt = TTFont(io.BytesIO(data))
    g = tt['glyf']; order = tt.getGlyphOrder()
    nonempty = sum(1 for gn in order if g[gn].numberOfContours != 0)
    codes = used[fn]
    print(f"== {fn}: tables {sorted(tt.keys())} numGlyphs {tt['maxp'].numGlyphs} nonempty {nonempty} distinct used {len(codes)} chars {sum(codes.values())} max code {max(codes)}")
    dec = ''.join(chr(toUnicode(MAC[c])[0]) if c < 258 and toUnicode(MAC[c]) else '¿' for c in range(0))
    # decode sample per page via Mac order
    for (f2,p), s in seq.items():
        if f2 != fn: continue
        out = []
        for c in s[:300]:
            if c in (13,10,32): out.append(chr(c) if c!=13 else ' '); continue
            if c < 258:
                u = toUnicode(MAC[c]); out.append(u if u else '¿')
            else: out.append('¿')
        print(f"  p{p+1}:", ''.join(out)[:300].replace('\n',' '))
