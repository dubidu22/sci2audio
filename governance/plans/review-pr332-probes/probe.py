import sys
from sci2audio.core import BlockKind
from sci2audio.testing import make_document
from sci2audio.textprep import StepContext, run_steps, spoken_text

def read_all(text, lang):
    doc = make_document([(BlockKind.PARAGRAPH, text)], lang)
    return spoken_text(run_steps(doc, StepContext(lang), strict=True).script())

def _main():
    for line in open(sys.argv[1], encoding="utf-8"):
      line = line.rstrip("\n")
      if not line or line.startswith("#"):
          continue
      lang, text = line.split("|", 1)
      text = text.replace("\\n", "\n")
      try:
          one = read_all(text, lang)
          two = read_all(one, lang)
          flag = "" if one == two else "   <<< RUN2: " + repr(two)
          print(f"{lang}|{text!r} -> {one!r}{flag}")
      except Exception as e:
          print(f"{lang}|{text!r} -> ERROR {type(e).__name__}: {e}")

if __name__=='__main__':
    _main()
