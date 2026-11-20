import subprocess, os
from pathlib import Path
ROOT = Path("/home/user/probe/mut"); PY = "/home/user/sci2audio/.venv/bin/python"
J = ROOT / "src/sci2audio/web/static/player.js"
M = [("m13a no error handler", '    figure.addEventListener("error", hide);\n', ""),
     ("m13b no early hide", "    if (figure.complete && figure.naturalWidth === 0) hide(); // failed before this ran\n", ""),
     ("m13c hide every unloaded", "if (figure.complete && figure.naturalWidth === 0) hide();", "if (figure.naturalWidth === 0) hide();")]
env = dict(os.environ, PYTHONPATH=str(ROOT / "src"), PLAYWRIGHT_BROWSERS_PATH="/tmp/claude-0/-home-user/36cd8b32-83b6-5853-be04-47d9d5c9ca5a/scratchpad/pw")
def run():
    r = subprocess.run([PY, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-m", "browser", "tests/browser/test_player_figures.py"], cwd=ROOT, env=env, capture_output=True, text=True, timeout=900)
    return r.returncode, [l for l in r.stdout.splitlines() if l.startswith("FAILED")] or r.stdout.strip().splitlines()[-1:]
print("baseline", run(), flush=True)
for name, old, new in M:
    src = J.read_text(); assert src.count(old) == 1, name
    J.write_text(src.replace(old, new))
    try: print(name, run(), flush=True)
    finally: J.write_text(src)
