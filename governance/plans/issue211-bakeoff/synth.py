import sys, time, json, os
import numpy as np, soundfile as sf, torch
sys.path.insert(0, os.path.dirname(__file__))
from texts import SENTENCES
torch.set_num_threads(4)
M = "/tmp/claude-0/gv/models"; O = "/tmp/claude-0/gv/out"
which = sys.argv[1]
res = {}
def run(name, load, synth, sr):
    t0 = time.time(); obj = load(); tl = time.time() - t0
    synth(obj, "Ein kurzer Satz zum Aufwärmen.")
    t0 = time.time(); parts = []
    for i, s in enumerate(SENTENCES):
        a = np.asarray(synth(obj, s), dtype="float32").reshape(-1)
        sf.write(f"{O}/{name}_{i:02d}.wav", a, sr); parts.append(a)
    ts = time.time() - t0
    full = np.concatenate(parts); sf.write(f"{O}/{name}_all.wav", full, sr)
    chars = sum(len(s) for s in SENTENCES)
    r = dict(load_s=round(tl,1), synth_s=round(ts,1), chars_per_s=round(chars/ts,1), rtf=round(ts/(len(full)/sr),3), audio_s=round(len(full)/sr,1))
    print(name, r, flush=True); res[name] = r

if which == "kokoro":
    from kokoro import KModel, KPipeline
    from misaki.espeak import EspeakG2P
    def load():
        m = KModel(repo_id="hexgrad/Kokoro-82M", config=f"{M}/thorsten/config.json", model=f"{M}/thorsten/model_legacy.pth").eval()
        g = EspeakG2P(language="de")
        pack = torch.load(f"{M}/thorsten/thorsten.pt", weights_only=True)
        return m, g, pack
    def synth(o, s):
        m, g, pack = o
        ps, _ = g(s); ps = ps.replace("ʏ", "y")
        with open(f"{O}/kokoro_phonemes.txt", "a") as f: f.write(ps + "\n")
        return KPipeline.infer(m, ps, pack, 1.0).audio.numpy()
    run("kokoro_thorsten", load, synth, 24000)
elif which.startswith("piper"):
    from piper import PiperVoice
    v = which.split(":")[1]
    def load(): return PiperVoice.load(f"{M}/piper/{v}.onnx")
    def synth(o, s):
        return np.concatenate([c.audio_float_array for c in o.synthesize(s)])
    run(f"piper_{v}", load, synth, 22050)
elif which.startswith("pocket"):
    from pocket_tts import TTSModel
    lang, voice = which.split(":")[1:3]
    def load():
        m = TTSModel.load_model(language=lang)
        return m, m.get_state_for_audio_prompt(voice)
    def synth(o, s):
        m, st = o
        return m.generate_audio(st, s).numpy()
    run(f"pocket_{lang}_{voice}", load, synth, 24000)
json.dump(res, open(f"{O}/timing_{which.replace(':','_')}.json","w"))
