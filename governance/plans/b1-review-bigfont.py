import ctypes, io, sys
import pypdfium2 as pdfium, pypdfium2.raw as raw
font = open("/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf","rb").read()
doc = pdfium.PdfDocument.new()
buf = (ctypes.c_uint8 * len(font)).from_buffer_copy(font)
f = raw.FPDFText_LoadFont(doc.raw, buf, len(font), raw.FPDF_FONT_TRUETYPE, 1)
for n in range(int(sys.argv[2])):
    page = doc.new_page(612, 792)
    for k in range(40):
        t = raw.FPDFPageObj_CreateTextObj(doc.raw, f, 10)
        s = "Line %d of page %d with some words in it\0" % (k, n)
        raw.FPDFText_SetText(t, ctypes.create_unicode_buffer(s).value and (ctypes.c_ushort * len(s))(*s.encode("utf-16-le")[::2] and [ord(c) for c in s]))
        raw.FPDFPageObj_Transform(t, 1, 0, 0, 1, 72, 750 - 15 * k)
        raw.FPDFPage_InsertObject(page.raw, t)
    raw.FPDFPage_GenerateContent(page.raw)
b = io.BytesIO(); doc.save(b); open(sys.argv[1],"wb").write(b.getvalue()); print(len(b.getvalue()))
