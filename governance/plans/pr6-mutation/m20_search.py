import itertools
from sci2audio.core import Block, BlockKind
from sci2audio.testing import make_document
from sci2audio.textprep import StepContext, run_steps, read_over, wording_for
from sci2audio.textprep.registry import BUILT_IN_STEPS
from sci2audio.textprep.steps import Stage
inline=[s for s in BUILT_IN_STEPS if s.stage is Stage.INLINE]
labels=["3.2","16a","1","2,5","3x","3×","10⁶","1–3","1-3","1/2","IV","A.1","2.10","S1","3a.1","12","1.2.3","2'","3*","5 %","3 km","1e5","(2)","½","3/4","0.5","1,000","2nd","II.3","7b","3.2a","4–5a"]
diff=0;n=0
for lang in ["en","de"]:
    w=wording_for(lang)
    for lab in labels:
        name=w.formula.format(lab)
        for text in [w.skipped([name], BlockKind.FORMULA), name]:
            pass
        out=[]
        for text in [w.skipped([name], BlockKind.FORMULA), name]:
            try: d=make_document([Block(BlockKind.PARAGRAPH,text)],lang)
            except ValueError as e: out.append("ERR");continue
            sc=run_steps(d,StepContext(lang),inline).script()
            s=text.find(name); r=read_over(text,sc,s,s+len(name)); out.append(r)
        n+=1
        if out[0]!=out[1]: diff+=1; print(lang,lab,out)
print(n,"labels",diff,"differ")
