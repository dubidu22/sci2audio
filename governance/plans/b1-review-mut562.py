import subprocess, sys, shutil
ROOT="/home/user/sci2audio"
P="src/sci2audio/extraction/pdf.py"; L="src/sci2audio/extraction/legibility.py"; C="src/sci2audio/core/content.py"
M=[
 (P,"return sourceless and raw.FPDFText_HasUnicodeMapError(textpage, index) == 1","return sourceless"),
 (P,"return not {program[i : i + 4] for i in range(12, end, 16)} & _UNICODE_TABLES","return not {program[i : i + 4] for i in range(12, end, 16)} & {b\"cmap\"}"),
 (P,"if count == 0 or len(program) < end:","if len(program) < end:"),
 (P,"if not font or raw.FPDFFont_GetIsEmbedded(font) != 1:","if not font:"),
 (P,'_SFNT = (b"\\x00\\x01\\x00\\x00", b"true", b"OTTO")','_SFNT = (b"\\x00\\x01\\x00\\x00",)'),
 (P,"unmapped = bool(needed) and sourceless.has(handle, i, name.value)","unmapped = sourceless.has(handle, i, name.value)"),
 (L,"if self.characters and self.unmapped / self.characters > UNMAPPED_SHARE:","if self.characters and self.unmapped / self.characters >= UNMAPPED_SHARE:"),
 (L,"if self.pairs >= MIN_PAIRS and self.rare / self.pairs >= RARE_SHARE:","if self.pairs > MIN_PAIRS and self.rare / self.pairs >= RARE_SHARE:"),
 (L,"return char.isalpha() and (code < 0x180 or 0x370 <= code < 0x400)","return char.isalpha() and (code < 0x250 or 0x370 <= code < 0x400)"),
 (L,'return char == "�" or unicodedata.category(char) == "Co"','return char == "�"'),
 (L,"            if char.isalpha() or _broken(char):","            if char.isalpha():"),
 (C,"if self.unmapped and not 0 < self.unmapped <= self.characters:","if self.unmapped < 0:"),
 (C,"return sum(sum(not c.isspace() for c in line.text) for line in self.lines)","return sum(len(line.text) for line in self.lines)"),
]
T=["tests/unit/test_extraction_legibility.py","tests/unit/test_core_content.py"]
base=subprocess.run([".venv/bin/python","-m","pytest","-q","-x","-p","no:randomly",*T],cwd=ROOT,capture_output=True,text=True)
print("baseline", base.stdout.strip().splitlines()[-1]); 
if base.returncode: sys.exit(1)
for f,old,new in M:
    s=open(f"{ROOT}/{f}").read()
    if s.count(old)!=1: print("NOMATCH", old[:60]); continue
    open(f"{ROOT}/{f}","w").write(s.replace(old,new))
    r=subprocess.run([".venv/bin/python","-m","pytest","-q","-x","-p","no:randomly",*T],cwd=ROOT,capture_output=True,text=True)
    open(f"{ROOT}/{f}","w").write(s)
    first=[l for l in r.stdout.splitlines() if l.startswith("FAILED")][:1]
    print("KILLED" if r.returncode else "SURVIVED", f.split("/")[-1], old[:70], first)
