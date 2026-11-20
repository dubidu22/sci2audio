import sys,ctypes,io,collections,struct,time
sys.path.insert(0,sys.argv[0].rsplit('/',1)[0]); from shape import *
from fontTools.ttLib.standardGlyphOrder import standardGlyphOrder as MAC
from fontTools.agl import toUnicode
doc=pdfium.PdfDocument(sys.argv[1]); name=ctypes.create_string_buffer(256); flags=ctypes.c_int()
fonts={}; used=collections.defaultdict(collections.Counter); stream=[]
for p in range(len(doc)):
    tp=doc[p].get_textpage(); h=tp.raw
    for i in range(tp.count_chars()):
        code=raw.FPDFText_GetUnicode(h,i); raw.FPDFText_GetFontInfo(h,i,name,256,ctypes.byref(flags)); fn=name.value.decode()
        stream.append((fn,code))
        if code in (10,13,32): continue
        used[fn][code]+=1
        if fn not in fonts:
            t=raw.FPDFText_GetTextObject(h,i); f=raw.FPDFTextObj_GetFont(t); size=ctypes.c_size_t()
            raw.FPDFFont_GetFontData(f,None,0,ctypes.byref(size)); buf=(ctypes.c_ubyte*size.value)(); raw.FPDFFont_GetFontData(f,buf,size.value,ctypes.byref(size)); fonts[fn]=bytes(buf)
F='/usr/share/fonts/truetype/'
fams={}
t0=time.time()
for fam,path in [('LibSerif','liberation/LiberationSerif-%s.ttf'),('LibSans','liberation/LiberationSans-%s.ttf'),('Carlito','crosextra/Carlito-%s.ttf')]:
    for st in ('Regular','Bold','Italic','BoldItalic'):
        fams[fam+'-'+st]=refs([F+path%st],chars)
print('refs',round(time.time()-t0,1),'s', sum(len(v) for v in fams.values()),'glyphs')
def rank(ch):
    o=ord(ch); return 0 if o<0x80 else 0.01 if o<0x100 or 0x2010<=o<=0x2030 else 0.03 if o<0x180 else 0.05
def adv(tt,gid):
    d=tt.reader['hmtx']; n=min(tt['hhea'].numberOfHMetrics,len(d)//4); k=min(gid,n-1)
    return struct.unpack('>H',d[4*k:4*k+2])[0]/tt['head'].unitsPerEm
tol=0.002; table={}; t0=time.time()
for fn,data in fonts.items():
    tt=TTFont(io.BytesIO(data)); order=tt.getGlyphOrder()
    gl={gid:raster(tt,order[gid],adv(tt,gid)) for gid in used[fn]}
    ink={g:v for g,v in gl.items() if v[0].sum()>0}
    NR={f:[(ch,src,rim,rw,norm(rim)) for ch,src,rim,rw in R] for f,R in fams.items()}
    def fscore(f):
        tot=0; hit=0
        for im,w in ink.values():
            c=[dist(im,rim,None,nr) for ch,src,rim,rw,nr in NR[f] if abs(rw-w)<=tol]
            if c: hit+=1; tot+=min(c)
            else: tot+=1
        return hit/max(1,len(ink)), -tot/max(1,len(ink))
    score={f:fscore(f) for f in fams}
    best=max(score,key=score.get); twin=score[best][0]>=0.9
    print(fn,'family',best,score[best],'twin' if twin else 'no twin')
    R=fams[best] if twin else [r for v in fams.values() for r in v]
    ds=[]; allc=[]
    for gid,(im,w) in gl.items():
        if im.sum()==0: table[(fn,gid)]=' '; continue
        c=sorted((dist(im,rim)+rank(ch),ch) for ch,src,rim,rw in R if (not twin or abs(rw-w)<=tol))
        if gid==70: print('   gid70',[(round(d,3),ch) for d,ch in c[:4]])
        allc+= [(d,gid,ch) for d,ch in c[:5]]
    taken=set(); done=set()
    for d,gid,ch in sorted(allc):
        if gid in done or ch in taken: continue
        table[(fn,gid)]=ch; done.add(gid); taken.add(ch); ds.append(d)
    for gid,(im,w) in gl.items():
        table.setdefault((fn,gid),'¿')
    print('   mean dist',round(sum(ds)/len(ds),3),'max',round(max(ds),3))
print('match',round(time.time()-t0,1),'s')
truth={g:(toUnicode(MAC[g])) for g in range(4,138)}; truth.update({3:' ',177:'–',179:'“',181:'‘',196:'„'})
tn=[k for k in table if 'Times' in k[0]]
bad=[(g,table[(f,g)],truth.get(g)) for f,g in tn if table[(f,g)]!=truth.get(g)]
cnt=used['KAMHII+TimesNewRoman']
print('TNR distinct',len(tn),'wrong',len(bad),bad,'chars wrong',sum(cnt[g] for g,_,_ in bad),'of',sum(cnt.values()))
out=''.join(' ' if c in (10,13,32) else table.get((f,c),'?') for f,c in stream)
import re; print(re.sub(' +',' ',out)[:900])
# language step: close calls (second-best within MARGIN) are settled by short common words
W=set("der die das und in den von zu mit sich des auf für ist im dem nicht ein eine als auch es an er hat aus bei sind noch nach wird einer um am sie über so zum war haben nur oder aber vor zur bis mehr durch man sein wurde sei werden wie the of and to a in is that for it as was with be by on not he this are or his from at which but have an they you were her she there their been has had one all would can more if no when who so its also into than".split())
import itertools
MARGIN=0.05
for fn,data in fonts.items():
    if 'Times' not in fn: continue
    tt=TTFont(io.BytesIO(data)); order=tt.getGlyphOrder()
    close=[]
    for gid in used[fn]:
        im,w=raster(tt,order[gid],adv(tt,gid))
        if im.sum()==0: continue
        c=sorted((dist(im,rim)+rank(ch),ch) for ch,src,rim,rw in fams['LibSerif-Regular'] if abs(rw-w)<=tol)
        if len(c)>1 and c[1][0]-c[0][0]<MARGIN: close.append((gid,c[0][1],c[1][1],round(c[1][0]-c[0][0],3)))
    print('close calls',close)
    def hits(tab):
        txt=''.join(' ' if c in (10,13,32) else tab.get((f,c),'?') for f,c in stream if f==fn)
        return sum(1 for wd in txt.lower().split() if wd.strip('.,;:„“"()') in W)
    groups=[(g,a,b) for g,a,b,_ in close]
    best=None
    for choice in itertools.product([0,1],repeat=len(groups)):
        tab=dict(table)
        for (g,a,b),k in zip(groups,choice): tab[(fn,g)]=a if k==0 else b
        h=hits(tab); 
        if best is None or h>best[0]: best=(h,choice,tab)
    print('words',best[0],'choice',best[1])
    table=best[2]
bad=[(g,table[(f,g)],truth.get(g)) for f,g in tn if table[(f,g)]!=truth.get(g)]
print('after language step: TNR wrong',len(bad),bad)
fn='KAMHII+TimesNewRoman'
# swap step: two glyphs of the same width whose candidates overlap may trade letters
gids=[g for f,g in tn]
improved=True
while improved:
    improved=False; base=hits(table)
    for a,b in itertools.combinations(gids,2):
        ca,cb=table[(fn,a)],table[(fn,b)]
        if ca==' ' or cb==' ': continue
        tab=dict(table); tab[(fn,a)],tab[(fn,b)]=cb,ca
        if hits(tab)>base+5: table=tab; improved=True; print('swap',a,b,ca,cb,'words',hits(tab)); break
bad=[(g,table[(f,g)],truth.get(g)) for f,g in tn if table[(f,g)]!=truth.get(g)]
print('after swap step: TNR wrong',len(bad),bad)
out=''.join(' ' if c in (10,13,32) else table.get((f,c),'?') for f,c in stream)
import re; print(re.sub(' +',' ',out)[:3000])
