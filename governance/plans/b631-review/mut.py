import subprocess, sys, pathlib
ROOT = pathlib.Path(sys.argv[1])
TESTS = ["tests/unit/test_web_window.py", "tests/unit/test_web_launch.py", "tests/unit/test_web_pages.py", "tests/unit/test_web_server.py"]
TESTS = [t for t in TESTS if (ROOT / t).exists()]
M = [
 ("serve watch for every launch", "src/sci2audio/web/launch.py", 'if config.launched_as == "browser":\n        watch', 'if True:\n        watch'),
 ("watch ignores running job", "src/sci2audio/web/launch.py", 'elif self.state.board.current is None and self.clock()', 'elif self.clock()'),
 ("watch idle >= -> >", "src/sci2audio/web/launch.py", "self.state.seen >= self.idle", "self.state.seen > self.idle + 1"),
 ("no Seen stamp", "src/sci2audio/web/server.py", "self.state.seen = time.monotonic()", "pass"),
 ("quit post any launch", "src/sci2audio/web/pages.py", '    if state.config.launched_as != "browser":\n        s = strings_of(request)\n        return _not_found(request, state, s, s("quit.not_here"))\n    state.quit.set()', '    state.quit.set()'),
 ("closing never asks", "src/sci2audio/web/window.py", "if not self.server.running or self._checked.is_set():", "if True:"),
 ("running counts preview", "src/sci2audio/web/launch.py", "current is not None and current.kind is not JobKind.PREVIEW", "current is not None"),
 ("main skips engine_settings", "src/sci2audio/web/window.py", "    engine_settings(os.environ)\n", "\n"),
 ("links inside window", "src/sci2audio/web/window.py", 'settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = True', 'settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = False'),
 ("private mode", "src/sci2audio/web/window.py", "private_mode=False", "private_mode=True"),
 ("selftest takes /start", "src/sci2audio/web/window.py", 'if found.get("path") == "/start":', 'if False:'),
 ("stop without wind_down", "src/sci2audio/web/launch.py", "        self._sock.close()\n        _wind_down(self.state)", "        self._sock.close()"),
 ("stop without should_exit", "src/sci2audio/web/launch.py", "        self._server.should_exit = True\n        if self._thread", "        if self._thread"),
 ("window path ignores failed start", "src/sci2audio/web/window.py", "    if not server.start():", "    if not server.start() and False:"),
 ("fallback without browser", "src/sci2audio/web/window.py", "    return run_browser()", "    return 0"),
 ("smartscreen replaces switches", "src/sci2audio/web/window.py", 'environ[WEBVIEW2_ARGUMENTS] = " ".join([*present, NO_SMARTSCREEN])', 'environ[WEBVIEW2_ARGUMENTS] = NO_SMARTSCREEN'),
 ("log token", "src/sci2audio/web/window.py", 'log.info("running in a window on %s", config.origin)', 'log.info("running in a window on %s", config.start_url)'),
 ("quit item everywhere", "src/sci2audio/web/templates/base.html", "{%- if launched_as == 'browser' %}", "{%- if true %}"),
 ("quit page making ignores kind", "src/sci2audio/web/pages.py", "making = current is not None and current.kind is not JobKind.PREVIEW", "making = current is not None"),
]
def run():
    r = subprocess.run(["uv","run","--no-sync","pytest","-x","-q","-p","no:randomly","-p","no:cacheprovider",*TESTS], cwd=ROOT, capture_output=True, text=True, timeout=600)
    first = next((l for l in r.stdout.splitlines() if l.startswith("FAILED")), "")
    return r.returncode, first, r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr[-300:]
code, first, last = run(); print("BASELINE", code, last); assert code == 0
for name, f, a, b in M:
    p = ROOT / f; s = p.read_text()
    if s.count(a) != 1: print("SKIP", name, s.count(a)); continue
    p.write_text(s.replace(a, b))
    try: code, first, last = run()
    finally: p.write_text(s)
    print("KILLED" if code else "SURVIVED", name, "|", first[:150] if code else last)
