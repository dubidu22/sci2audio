from sci2audio.textprep.numbers_de import _fractions
bad=[]
for d in range(0,100):
    t=f"Am 3.4. 1/{d} Tag."
    for c in _fractions(t):
        if not c.replacement.startswith("ein "): bad.append((t,c.replacement))
print(bad[:10], len(bad))
