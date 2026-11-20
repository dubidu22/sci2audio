import sys
ENDS = "sch,lich,ig,al,iv,iell,uell,rell,nell,mell,är".split(",")
INFL = ("e","en","er","es","em")
def b_ok(b): return any(b.endswith(e) and len(b)-len(e)>=3 for e in ENDS)
def a_ok(a): return any(a.endswith(e+i) and len(a)-len(e+i)>=4 for e in ENDS for i in INFL)
pairs = """deutsch-französischen sozial-emotionale rot-grüne technisch-organisatorischen rechtlich-ethischen
sozial-ökonomischen physikalisch-chemischen kognitiv-emotionalen qualitativ-empirische quantitativ-qualitativen
inhaltlich-methodischen juristisch-technischen wirtschaftlich-technische politisch-rechtlichen christlich-demokratische
sozial-liberale medizinisch-therapeutischen theoretisch-methodische empirisch-analytischen naturwissenschaftlich-technischen
deutsch-polnischen ethisch-moralischen räumlich-zeitlichen soziokulturell-historischen psychisch-sozialen
formal-logischen materiell-rechtlichen sprachlich-kulturellen ökologisch-nachhaltigen marxistisch-leninistischen
englisch-deutschen national-konservative digital-analoge schwarz-weiße süß-saure""".split()
hit=[p for p in pairs if b_ok(p.split("-")[0]) and a_ok(p.split("-")[1])]
miss=[p for p in pairs if p not in hit]
print(len(hit),"/",len(pairs)); print("missed:",miss)
