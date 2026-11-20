import sys, ctypes, io, collections, numpy as np
import pypdfium2 as pdfium, pypdfium2.raw as raw
from fontTools.ttLib import TTFont
from fontTools.pens.basePen import BasePen
import os
N=int(os.environ.get("N","24"))
class Poly(BasePen):
    def __init__(s, gs): super().__init__(gs); s.cs=[]; s.c=[]
    def _moveTo(s,p): s.c=[p]
    def _lineTo(s,p): s.c.append(p)
    def _curveToOne(s,a,b,p):
        p0=s.c[-1]
        for t in np.linspace(0,1,9)[1:]:
            u=1-t; s.c.append((u**3*p0[0]+3*u*u*t*a[0]+3*u*t*t*b[0]+t**3*p[0], u**3*p0[1]+3*u*u*t*a[1]+3*u*t*t*b[1]+t**3*p[1]))
    def _qCurveToOne(s,a,p):
        p0=s.c[-1]
        for t in np.linspace(0,1,7)[1:]:
            u=1-t; s.c.append((u*u*p0[0]+2*u*t*a[0]+t*t*p[0], u*u*p0[1]+2*u*t*a[1]+t*t*p[1]))
    def _closePath(s): s.cs.append(s.c); s.c=[]
    _endPath=_closePath
xs=(np.arange(N)+0.5)/N
def raster(tt, gname, adv=None):
    g=tt['glyf']
    class _G:
        def __init__(s,n): s.n=n
        def draw(s,pen): g[s.n].draw(pen,g)
    class _GS:
        def __getitem__(s,n): return _G(n)
    pen=Poly(_GS()); g[gname].draw(pen, g)
    upm=tt['head'].unitsPerEm
    adv = adv*upm if adv is not None else (tt['hmtx'][gname][0] or upm)
    img=np.zeros((N,N))
    X,Y=np.meshgrid(xs*max(adv,upm*0.3), 1.0*upm-(xs*1.3*upm))  # y from 1.0em down to -0.3em
    for c in pen.cs:
        if len(c)<2: continue
        P=np.array(c+[c[0]]); x0,y0,x1,y1=P[:-1,0],P[:-1,1],P[1:,0],P[1:,1]
        for a,b,cc,d in zip(x0,y0,x1,y1):
            up=(b<=Y)&(d>Y); dn=(b>Y)&(d<=Y)
            cross=(cc-a)*(Y-b)-(X-a)*(d-b)
            img+=np.where(up&(cross>0),1,0)-np.where(dn&(cross<0),1,0)
    return (img!=0).astype(float), adv/upm
def refs(paths, chars):
    out=[]
    for p in paths:
        tt=TTFont(p); cm=tt.getBestCmap()
        for ch in chars:
            g=cm.get(ord(ch))
            if g: im,w=raster(tt,g); out.append((ch,p.split('/')[-1],im,w))
    return out
chars=[chr(c) for c in list(range(0x21,0x7f))+list(range(0xa1,0x180))+[0x2013,0x2014,0x2018,0x2019,0x201a,0x201c,0x201d,0x201e,0x2022,0x2026,0x2020,0x2021,0x2030,0x2039,0x203a,0x20ac,0x2122,0x2212,0x2264,0x2265,0x221e,0x2248,0x2260,0x00b1]+list(range(0x391,0x3aa))+list(range(0x3b1,0x3ca))]
def match(tt, gname, R, wtol, adv=None):
    im,w=raster(tt,gname,adv)
    best=[]
    for ch,src,rim,rw in R:
        if wtol is not None and abs(rw-w)>wtol: continue
        d=np.abs(im-rim).sum()/max(1,(im+rim).clip(0,1).sum())
        best.append((d,ch,src))
    best.sort(); return best[:3], w
def norm(im, M=32):
    ys,xs_=np.nonzero(im)
    if len(ys)==0: return np.zeros((M,M))
    c=im[ys.min():ys.max()+1, xs_.min():xs_.max()+1]
    h,w=c.shape; s=max(h,w)
    pad=np.zeros((s,s)); pad[(s-h)//2:(s-h)//2+h,(s-w)//2:(s-w)//2+w]=c
    idx=(np.arange(M)*s/M).astype(int); return pad[np.ix_(idx,idx)]
def dist(a,b,na=None,nb=None):
    d1=np.abs(a-b).sum()/max(1,(a+b).clip(0,1).sum())
    na=norm(a) if na is None else na; nb=norm(b) if nb is None else nb
    d2=np.abs(na-nb).sum()/max(1,(na+nb).clip(0,1).sum())
    return 0.5*d1+0.5*d2
def blur(im, r=2):
    k=np.exp(-0.5*(np.arange(-2*r,2*r+1)/r)**2); k/=k.sum()
    out=np.apply_along_axis(lambda v: np.convolve(v,k,'same'),0,im)
    return np.apply_along_axis(lambda v: np.convolve(v,k,'same'),1,out)
def ncc(a,b):
    a=a-a.mean(); b=b-b.mean(); d=np.sqrt((a*a).sum()*(b*b).sum())
    return 1-(a*b).sum()/d if d else 1.0
def dist(a,b,na=None,nb=None):
    na=norm(a) if na is None else na; nb=norm(b) if nb is None else nb
    return 0.5*ncc(blur(a),blur(b))+0.5*ncc(blur(na,1),blur(nb,1))
def xor(a,b):
    return np.abs(a-b).sum()/max(1,(a+b).clip(0,1).sum())
def dist(a,b,na=None,nb=None):
    na=norm(a) if na is None else na; nb=norm(b) if nb is None else nb
    return 0.25*ncc(blur(a),blur(b))+0.25*ncc(blur(na,1),blur(nb,1))+0.25*xor(a,b)+0.25*xor(na,nb)
