import itertools
from sci2audio.testing.regression import _case, read_twice
shapes = ["1:1","3:2","13:30","1/2","3/4","5","5 %","5%","2,5","2.5","1.5","3–5","3-5","1.000","1,000","10⁻³","2019","3. Mai","3.","18 Jahre","18 years","1st","3rd","½","0,05","p","x","(1)","[2]","−1","1e5","5 °C","5°C","100 m","2²","1–1","1:2:3","12.03.2019","3.4.","IV","§ 3","Nr. 5"]
arrows = ["←−","−→","←−→","←−−","−−→"]
bad = 0
for lang in ("de","en"):
    for a, s, sep in itertools.product(arrows, shapes, ["", " "]):
        for pre in ("x ", "x"):
            t = f"Es gilt {pre}{a}{sep}{s} hier." if lang=="de" else f"It is {pre}{a}{sep}{s} here."
            raw = dict(id="g", audit=0, issue=1, goal="g", language=lang, expected=[""], blocks=[{"kind":"paragraph","text":t}])
            r1, r2 = read_twice(_case(raw))
            if r1 != r2:
                bad += 1; print(lang, repr(t), "|", r1[0], "|", r2[0])
print("unstable:", bad)
