"""Mutation check: ROOT holds src and tests; each mutant runs ROOT's textprep tests."""
import os, shutil, subprocess, sys, importlib.util
S = os.path.dirname(os.path.abspath(__file__))
ROOT = os.environ["ROOT"]
PY = "/home/user/sci2audio/.venv/bin/python"
spec = importlib.util.spec_from_file_location("m", sys.argv[1]); mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
tests = sorted("tests/unit/" + f for f in os.listdir(ROOT + "/tests/unit") if f.startswith("test_textprep_") and f.endswith(".py"))
d = os.path.join(S, os.environ.get("MUTDIR", "mut3"))
def run(src_dir):
    return subprocess.run([PY, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", "-n", "4", "-m", "not slow and not benchmark", *tests],
                          cwd=ROOT, env={**os.environ, "PYTHONPATH": src_dir, "HYPOTHESIS_PROFILE": "ci"}, capture_output=True, text=True)
base = run(ROOT + "/src")
print("BASELINE", "PASS" if base.returncode == 0 else "FAIL\n" + base.stdout[-2000:], flush=True)
if base.returncode: sys.exit(1)
only = os.environ.get("ONLY")
for i, (f, a, b) in enumerate(mod.M):
    if only and str(i) not in only.split(","): continue
    path = ROOT + "/src/sci2audio/textprep/" + f
    src = open(path).read()
    if src.count(a) != 1:
        print(i, "NOT FOUND", f, a[:60], flush=True); continue
    shutil.rmtree(d, ignore_errors=True); shutil.copytree(ROOT + "/src", d + "/src")
    open(d + "/src/sci2audio/textprep/" + f, "w").write(src.replace(a, b))
    r = run(d + "/src")
    failed = [l for l in r.stdout.splitlines() if l.startswith("FAILED")][:2]
    print(i, "KILLED" if r.returncode else "SURVIVED", f, a[:50].replace("\n", "\\n"), "->", b[:30].replace("\n", "\\n"), *failed, flush=True)
