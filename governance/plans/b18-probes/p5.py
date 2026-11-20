import sys,ctypes,io,struct,collections
import pypdfium2 as pdfium, pypdfium2.raw as raw
from fontTools.ttLib import TTFont
doc=pdfium.PdfDocument(sys.argv[1]); name=ctypes.create_string_buffer(256); flags=ctypes.c_int()
fonts={}; ratios=collections.defaultdict(list); rect=raw.FS_RECTF(); m=raw.FS_MATRIX()
def adv(tt,gid):
    d=tt.reader['hmtx']; n=min(tt['hhea'].numberOfHMetrics,len(d)//4); k=min(gid,n-1)
    return struct.unpack('>H',d[4*k:4*k+2])[0]/tt['head'].unitsPerEm
for p in range(len(doc)):
    tp=doc[p].get_textpage(); h=tp.raw
    for i in range(tp.count_chars()):
        code=raw.FPDFText_GetUnicode(h,i); raw.FPDFText_GetFontInfo(h,i,name,256,ctypes.byref(flags)); fn=name.value.decode()
        if fn not in fonts:
            t=raw.FPDFText_GetTextObject(h,i); f=raw.FPDFTextObj_GetFont(t); size=ctypes.c_size_t()
            raw.FPDFFont_GetFontData(f,None,0,ctypes.byref(size)); buf=(ctypes.c_ubyte*size.value)(); raw.FPDFFont_GetFontData(f,buf,size.value,ctypes.byref(size)); fonts[fn]=TTFont(io.BytesIO(bytes(buf)))
        if raw.FPDFText_IsGenerated(h,i)==1 or not raw.FPDFText_GetLooseCharBox(h,i,rect): continue
        fs=raw.FPDFText_GetFontSize(h,i); raw.FPDFText_GetMatrix(h,i,m)
        w=(rect.right-rect.left)/(fs*(m.a**2+m.b**2)**.5 or 1)
        a=adv(fonts[fn],code) if code < fonts[fn]['maxp'].numGlyphs else -1
        if a>0: ratios[fn].append(w/a)
for fn,r in ratios.items():
    r.sort(); n=len(r); ok=sum(abs(x-1)<0.02 for x in r)
    print(fn,n,'within 2%:',ok, 'median',round(r[n//2],3),'p5',round(r[n//20],3),'p95',round(r[-n//20-1],3))
