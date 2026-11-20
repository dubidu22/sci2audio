import subprocess, sys, pathlib
ROOT = pathlib.Path(sys.argv[1])
TESTS = ["tests/unit/test_installers.py"]
M = [
 ("bundle check skips ffmpeg", "scripts/build_installer.py", 'if not (internal / "ffmpeg" / ffmpeg_name(system)).is_file():', 'if False:'),
 ("bundle check skips imageio", "scripts/build_installer.py", 'if binaries.is_dir() and any(p.name.startswith("ffmpeg") for p in binaries.iterdir()):', 'if False:'),
 ("bundle check skips licences", "scripts/build_installer.py", '        if not (internal / "licenses" / name).is_file():', '        if False:'),
 ("bundle check skips programs", "scripts/build_installer.py", '        if not (folder / f"{program}{suffix}").is_file():', '        if False:'),
 ("refused list shorter", "scripts/build_installer.py", 'REFUSED = "Affero;AGPL;SSPL;Non-Commercial;NonCommercial;UNKNOWN"', 'REFUSED = "Affero;AGPL;SSPL"'),
 ("piplicenses no fail-on", "scripts/build_installer.py", '            "--partial-match", f"--fail-on={REFUSED}",', '            "--partial-match",'),
 ("source note no config", "scripts/build_installer.py", "    if configuration.exists():", "    if False:"),
 ("window report ignores origin", "scripts/installer_smoke.py", "    if not LOCAL.match(origin):", "    if False:"),
 ("window report ignores host", "scripts/installer_smoke.py", '    if page.get("host") != origin.removeprefix("http://"):', '    if False:'),
 ("window report ignores token", "scripts/installer_smoke.py", '    if "token" in json.dumps(report).lower():', '    if False:'),
 ("window report ignores rail", "scripts/installer_smoke.py", '    if page.get("rail") is not True:', '    if page.get("rail") is False:'),
 ("m4b size", "scripts/installer_smoke.py", "return path.stat().st_size > 10_000 and head[4:8] == b\"ftyp\"", "return head[4:8] == b\"ftyp\""),
 ("mp3 frame check", "scripts/installer_smoke.py", "frame = len(head) >= 2 and head[0] == 0xFF and head[1] & 0xE0 == 0xE0", "frame = True"),
 ("no_network always", "scripts/installer_smoke.py", "                return False\n        except OSError:", "                return True\n        except OSError:"),
 ("smoke window ignores exit code", "scripts/installer_smoke.py", '    check(done.returncode == 0, f"the app ended with {done.returncode}")\n    say("the window', '    say("the window'),
 ("smoke browser ignores quit status", "scripts/installer_smoke.py", '    check(found.get("quit") == 202, f"Quit answered {found.get(\'quit\')}")', '    pass'),
 ("visit keeps token", "scripts/installer_smoke.py", 'found: dict[str, Any] = {"start": start.split("?")[0]}', 'found: dict[str, Any] = {"start": start}'),
 ("cli version check", "scripts/installer_smoke.py", 'check(shown == f"sci2audio {version}", f"version {shown!r}, expected {version}")', 'pass'),
 ("cli no mp3 check", "scripts/installer_smoke.py", '        check(mp3s and all(is_mp3(p) for p in mp3s), f"no MP3 of the {language} text")', '        pass'),
 ("app.py no ffmpeg env", "packaging/app.py", '    os.environ["IMAGEIO_FFMPEG_EXE"]', '    os.environ["X_IMAGEIO_FFMPEG_EXE"]'),
 ("cli.py no ffmpeg env", "packaging/cli.py", '    os.environ["IMAGEIO_FFMPEG_EXE"]', '    os.environ["X_IMAGEIO_FFMPEG_EXE"]'),
 ("ffmpeg gpl", "packaging/ffmpeg/build.sh", "    --disable-everything --disable-autodetect --disable-network --disable-doc \\", "    --disable-everything --disable-autodetect --disable-network --disable-doc --enable-gpl \\"),
 ("ffmpeg network", "packaging/ffmpeg/build.sh", "--enable-protocol=file,pipe", "--enable-protocol=file,pipe,http"),
 ("archive skips hash", "packaging/ffmpeg/sources_archive.sh", 'same "$downloads/$espeak" "$ESPEAK_NG_SHA256"', 'true'),
 ("build.sh skips hash", "packaging/ffmpeg/build.sh", '  if [ "$found" != "$2" ]; then', '  if false; then'),
 ("iss admin", "packaging/windows/sci2audio.iss", "PrivilegesRequired=lowest", "PrivilegesRequired=admin"),
 ("iss deletes appdata", "packaging/windows/sci2audio.iss", 'Type: filesandordirs; Name: "{app}"', 'Type: filesandordirs; Name: "{app}"\nType: filesandordirs; Name: "{userdocs}\\sci2audio"'),
 ("release publish without installers", ".github/workflows/release.yml", "    needs: [build, smoke, installers]", "    needs: [build, smoke]"),
 ("release attests nothing", ".github/workflows/release.yml", "          subject-path: dist/*", "          subject-path: dist/*.whl"),
 ("installers smoke drops offline", ".github/workflows/installers.yml", "--offline\n", "\n"),
 ("installers fork guard", ".github/workflows/installers.yml", "      && github.event.pull_request.head.repo.full_name == github.repository\n      && (github.event.action != 'labeled' || github.event.label.name == 'ci:installers'))\n    runs-on: ${{ matrix.os }}\n    timeout-minutes: 90", "      && (github.event.action != 'labeled' || github.event.label.name == 'ci:installers'))\n    runs-on: ${{ matrix.os }}\n    timeout-minutes: 90"),
 ("uninstall check dropped", ".github/workflows/installers.yml", "          test ! -e \"$FOLDER\"\n", "\n"),
]
def run():
    r = subprocess.run([str(ROOT/".venv/bin/python"),"-m","pytest","-x","-q","-p","no:randomly","-p","no:cacheprovider",*TESTS], cwd=ROOT, capture_output=True, text=True, timeout=600)
    first = next((l for l in r.stdout.splitlines() if l.startswith("FAILED")), "")
    return r.returncode, first, r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr[-300:]
code, first, last = run(); print("BASELINE", code, last); assert code == 0
for name, f, a, b in M:
    p = ROOT / f; s = p.read_text()
    if s.count(a) != 1: print("SKIP", name, s.count(a)); continue
    p.write_text(s.replace(a, b))
    try: code, first, last = run()
    finally: p.write_text(s)
    print("KILLED" if code else "SURVIVED", name, "|", first[:140] if code else last)
