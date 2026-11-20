import sys, os, re, glob, json
sys.path.insert(0, os.path.dirname(__file__))
from texts import SENTENCES
from faster_whisper import WhisperModel
import jiwer, soundfile as sf, numpy as np
from scipy.signal import resample_poly
from math import gcd
def load(f):
    a, sr = sf.read(f, dtype="float32")
    g = gcd(sr, 16000)
    return resample_poly(a, 16000//g, sr//g).astype("float32")
m = WhisperModel(sys.argv[1], device="cpu", compute_type="int8", cpu_threads=4)
NUM={"42":"zweiundvierzig","1998":"neunzehnhundertachtundneunzig","2020":"zweitausendzwanzig","300":"dreihundert","3":"drei"}
def norm(s):
    s=re.sub(r"\d+", lambda m: NUM.get(m.group(0), m.group(0)), s)
    return re.sub(r"[^\wäöüß ]", " ", s.lower()).split()
out = {}
for name in sys.argv[2:]:
    refs, hyps, errs = [], [], []
    for i, s in enumerate(SENTENCES):
        segs, _ = m.transcribe(load(f"/tmp/claude-0/gv/out/{name}_{i:02d}.wav"), language="de", beam_size=5, condition_on_previous_text=False)
        h = " ".join(x.text for x in segs).strip()
        r, hh = " ".join(norm(s)), " ".join(norm(h))
        refs.append(r); hyps.append(hh)
        if r != hh: errs.append((i, h))
    w = jiwer.wer(refs, hyps)
    out[name] = dict(wer=round(w, 4), wrong_sentences=len(errs))
    print(name, out[name], flush=True)
    for i, h in errs: print("   ", i, "|", h)
json.dump(out, open("/tmp/claude-0/gv/out/wer.json", "w"), indent=1)
