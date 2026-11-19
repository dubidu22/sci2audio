"""The installers' build and smoke scripts and their pins (#215, #13, D-797, D-798). The
installers themselves are built and tested on three systems by installers.yml; these tests
keep the parts a reader of that workflow can miss."""

from __future__ import annotations

import importlib
import importlib.util
import json
import os
import re
import runpy
import sys
from pathlib import Path
from types import ModuleType

import pytest

import sci2audio

ROOT = Path(__file__).resolve().parents[2]
PACKAGING = ROOT / "packaging"
WORKFLOWS = ROOT / ".github" / "workflows"
INSTALLERS = (WORKFLOWS / "installers.yml").read_text(encoding="utf-8")
RELEASE = (WORKFLOWS / "release.yml").read_text(encoding="utf-8")


def load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        f"sci2audio_{name}", ROOT / "scripts" / f"{name}.py"
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


build = load("build_installer")
smoke = load("installer_smoke")


def pins(path: Path) -> dict[str, str]:
    found = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#"):
            key, _, value = line.partition("=")
            found[key] = value
    return found


# ---- pins and the FFmpeg build ------------------------------------------------------------


@pytest.mark.parametrize("name", ["ffmpeg/sources.env", "tools.env"])
def test_every_download_is_pinned_by_its_sha256(name: str) -> None:
    found = pins(PACKAGING / name)
    urls = {key.removesuffix("_URL") for key in found if key.endswith("_URL")}
    assert urls
    for stem in urls:
        assert found[f"{stem}_URL"].startswith("https://"), stem
        assert re.fullmatch(r"[0-9a-f]{64}", found[f"{stem}_SHA256"]), stem


def test_espeak_ngs_source_is_a_pinned_commit() -> None:
    found = pins(PACKAGING / "ffmpeg" / "sources.env")
    assert re.fullmatch(r"[0-9a-f]{40}", found["ESPEAK_NG_COMMIT"])
    assert re.fullmatch(r"[0-9a-f]{64}", found["ESPEAK_NG_SHA256"])


def test_the_bundled_ffmpeg_is_lgpl_audio_only_and_reaches_no_network() -> None:
    script = (PACKAGING / "ffmpeg" / "build.sh").read_text(encoding="utf-8")
    configure = script[script.index('cd "$work/ffmpeg-$FFMPEG_VERSION"') :]
    configure = configure[: configure.index("make -j")]
    for refused in ("--enable-gpl", "--enable-nonfree", "--enable-version3"):
        assert refused not in configure
    for needed in ("--disable-everything", "--disable-autodetect", "--disable-network"):
        assert needed in configure
    assert re.findall(r"--enable-protocol=(\S+)", configure) == ["file,pipe"]
    assert "--enable-libmp3lame" in configure
    # sci2audio's own formats (output/write.py, app/audio.py)
    encoders = ",".join(re.findall(r"--enable-encoder=(\S+)", configure)).split(",")
    muxers = ",".join(re.findall(r"--enable-muxer=(\S+)", configure)).split(",")
    assert {"libmp3lame", "aac", "wrapped_avframe"} <= set(encoders)
    assert {"mp3", "ipod", "null"} <= set(muxers)


def test_the_spec_leaves_imageio_ffmpegs_program_out_and_brings_its_own() -> None:
    spec = (PACKAGING / "sci2audio.spec").read_text(encoding="utf-8")
    assert 'DROPPED = "imageio_ffmpeg/binaries"' in spec
    assert spec.count("without_imageio_ffmpeg(found.") == 2  # binaries and datas
    assert 'binaries.append((str(FFMPEG), "ffmpeg"))' in spec
    assert 'datas.append((str(LICENSES), "licenses"))' in spec


@pytest.mark.parametrize(
    ("entry", "module"), [("app", "sci2audio.web.window"), ("cli", "sci2audio.cli")]
)
def test_a_frozen_program_uses_the_bundles_ffmpeg(
    entry: str, module: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = importlib.import_module(module)
    monkeypatch.setattr(target, "main", lambda: 0)
    monkeypatch.setenv("IMAGEIO_FFMPEG_EXE", "/somewhere/else/ffmpeg")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    with pytest.raises(SystemExit) as ended:
        runpy.run_path(str(PACKAGING / f"{entry}.py"), run_name="__main__")
    assert ended.value.code == 0
    program = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
    assert Path(os.environ["IMAGEIO_FFMPEG_EXE"]) == tmp_path / "ffmpeg" / program


def test_a_program_run_from_source_keeps_its_ffmpeg(monkeypatch: pytest.MonkeyPatch) -> None:
    from sci2audio import cli

    monkeypatch.setattr(cli, "main", lambda: 0)
    monkeypatch.setenv("IMAGEIO_FFMPEG_EXE", "/my/ffmpeg")
    monkeypatch.delattr(sys, "frozen", raising=False)
    with pytest.raises(SystemExit):
        runpy.run_path(str(PACKAGING / "cli.py"), run_name="__main__")
    assert os.environ["IMAGEIO_FFMPEG_EXE"] == "/my/ffmpeg"


# ---- build_installer ----------------------------------------------------------------------


def test_the_version_is_the_packages() -> None:
    assert build.package_version() == sci2audio.__version__


@pytest.mark.parametrize(
    ("platform", "name"),
    [
        ("darwin", "sci2audio-1.4.0-macos-arm64.dmg"),
        ("win32", "sci2audio-1.4.0-windows-x64-setup.exe"),
        ("linux", "sci2audio-1.4.0-linux-x86_64.AppImage"),
    ],
)
def test_each_system_gets_its_installers_name(platform: str, name: str) -> None:
    assert build.installer_name("1.4.0", build.system_of(platform)) == name
    assert name in RELEASE.replace("$version", "1.4.0")  # the release checks each is there


def test_no_installer_for_another_system() -> None:
    with pytest.raises(SystemExit):
        build.system_of("freebsd14")


def frozen(folder: Path, system: str, *, imageio: bool = False) -> Path:
    suffix = ".exe" if system == "windows" else ""
    internal = folder / "_internal"
    for program in ("sci2audio", "sci2audio-app"):
        (folder / f"{program}{suffix}").parent.mkdir(parents=True, exist_ok=True)
        (folder / f"{program}{suffix}").write_bytes(b"x")
    (internal / "ffmpeg").mkdir(parents=True)
    (internal / "ffmpeg" / build.ffmpeg_name(system)).write_bytes(b"x")
    (internal / "licenses").mkdir()
    for name in ("LICENSE", "THIRD_PARTY_LICENSES.md", "SOURCE.txt", "python-packages.txt"):
        (internal / "licenses" / name).write_text("x", encoding="utf-8")
    if imageio:
        (internal / "imageio_ffmpeg" / "binaries").mkdir(parents=True)
        (internal / "imageio_ffmpeg" / "binaries" / "ffmpeg-linux-x86_64-v9.0.2").write_bytes(b"x")
    return folder


@pytest.mark.parametrize("system", ["macos", "windows", "linux"])
def test_a_complete_frozen_folder_passes(tmp_path: Path, system: str) -> None:
    assert build.check_bundle(frozen(tmp_path / "sci2audio", system), system) == []


def test_imageio_ffmpegs_program_in_the_folder_fails_the_build(tmp_path: Path) -> None:
    folder = frozen(tmp_path / "sci2audio", "linux", imageio=True)
    assert build.check_bundle(folder, "linux") == [
        "imageio-ffmpeg's own ffmpeg is in the bundle (D-798)"
    ]


def test_a_missing_ffmpeg_licence_or_program_fails_the_build(tmp_path: Path) -> None:
    folder = frozen(tmp_path / "sci2audio", "windows")
    (folder / "_internal" / "ffmpeg" / "ffmpeg.exe").unlink()
    (folder / "_internal" / "licenses" / "SOURCE.txt").unlink()
    (folder / "sci2audio-app.exe").unlink()
    assert build.check_bundle(folder, "windows") == [
        "the audio-only ffmpeg is missing (ffmpeg/)",
        "licenses/SOURCE.txt is missing",
        "sci2audio-app.exe is missing",
    ]


def test_the_source_note_names_the_release_files_and_ffmpegs_configuration(tmp_path: Path) -> None:
    (tmp_path / "FFmpeg-configuration.txt").write_text("  --disable-network\n", encoding="utf-8")
    note = build.source_note("1.4.0", tmp_path)
    assert "https://github.com/dubidu22/sci2audio/releases/tag/v1.4.0" in note
    assert "sci2audio-1.4.0.tar.gz" in note
    assert "sci2audio-1.4.0-sources.tar" in note
    assert "LGPL-2.1-or-later" in note
    assert "GPL-3.0-or-later" in note
    assert note.rstrip().endswith("--disable-network")


def test_pythons_licence_is_found_or_the_build_stops(tmp_path: Path) -> None:
    short = f"python{sys.version_info[0]}.{sys.version_info[1]}"
    with pytest.raises(SystemExit):
        build.python_licence(tmp_path)
    (tmp_path / "lib" / short).mkdir(parents=True)
    (tmp_path / "lib" / short / "LICENSE.txt").write_text("PSF", encoding="utf-8")
    assert build.python_licence(tmp_path) == tmp_path / "lib" / short / "LICENSE.txt"
    (tmp_path / "LICENSE.txt").write_text("PSF", encoding="utf-8")  # Windows
    assert build.python_licence(tmp_path) == tmp_path / "LICENSE.txt"


@pytest.mark.skipif(sys.platform == "win32", reason="symbolic links and modes as on Linux")
def test_the_appimage_folder_holds_apprun_the_desktop_file_and_the_icon(tmp_path: Path) -> None:
    folder = frozen(tmp_path / "dist" / "sci2audio", "linux")
    app = build.appdir(folder, tmp_path / "AppDir")
    assert (app / "AppRun").stat().st_mode & 0o111
    assert (app / "sci2audio" / "sci2audio-app").is_file()
    assert (app / ".DirIcon").resolve() == (app / "sci2audio.png").resolve()
    desktop = (app / "sci2audio.desktop").read_text(encoding="utf-8")
    assert "Icon=sci2audio\n" in desktop
    assert "Terminal=false" in desktop
    run = (app / "AppRun").read_text(encoding="utf-8")
    assert 'exec "$here/sci2audio/sci2audio-app"' in run  # no arguments: the app
    assert 'exec "$here/sci2audio/sci2audio" "$@"' in run  # arguments: the command line


def test_the_windows_installer_is_per_user_and_its_uninstaller_keeps_the_persons_files() -> None:
    script = (PACKAGING / "windows" / "sci2audio.iss").read_text(encoding="utf-8")
    assert "PrivilegesRequired=lowest" in script
    assert "DefaultDirName={autopf}\\sci2audio" in script
    uninstall = script[script.index("[UninstallDelete]") :]
    deleted = re.findall(r'Name: "([^"]+)"', uninstall)
    assert deleted == ["{app}"]  # the program folder, nothing of the person's


def test_the_refusals_match_the_ci_licences_job() -> None:
    ci = (WORKFLOWS / "ci.yml").read_text(encoding="utf-8")
    assert f'--fail-on="{build.REFUSED}"' in ci
    for name in ("sci2audio", "pip-licenses", "prettytable", "wcwidth", "espeakng-loader"):
        assert name in build.NOT_CHECKED


# ---- installer_smoke ------------------------------------------------------------------------


def test_the_recording_stand_in_writes_the_start_link_down(tmp_path: Path) -> None:
    link = tmp_path / "start-url"
    assert smoke.main(["record", str(link), "http://127.0.0.1:5/start?token=t"]) == 0
    assert link.read_text(encoding="utf-8") == "http://127.0.0.1:5/start?token=t"


def good_report() -> dict[str, object]:
    return {
        "version": "1.4.0",
        "launched_as": "window",
        "origin": "http://127.0.0.1:50123",
        "page": {
            "title": "Library · sci2audio",
            "lang": "en",
            "rail": True,
            "host": "127.0.0.1:50123",
            "path": "/",
        },
    }


def test_the_window_report_of_a_working_app_passes() -> None:
    assert smoke.window_problems(good_report()) == []


@pytest.mark.parametrize(
    ("change", "problem"),
    [
        ({"launched_as": "browser"}, "launched as 'browser', not in a window"),
        (
            {
                "origin": "http://0.0.0.0:50123",
                "page": {**good_report()["page"], "host": "0.0.0.0:50123"},
            },  # type: ignore[dict-item]
            "the server is at 'http://0.0.0.0:50123', not on 127.0.0.1",
        ),
        (
            {"page": {**good_report()["page"], "host": "example.org"}},
            "the window shows 'example.org', not the app's server",
        ),  # type: ignore[dict-item]
        (
            {"page": {**good_report()["page"], "path": "/start"}},
            "the window shows '/start', not the library",
        ),  # type: ignore[dict-item]
        ({"page": {**good_report()["page"], "rail": False}}, "the rail is not drawn"),  # type: ignore[dict-item]
        ({"page": {**good_report()["page"], "lang": ""}}, "the page language is ''"),  # type: ignore[dict-item]
        ({"token": "abc"}, "the report names the start-up token"),
    ],
)
def test_each_wrong_thing_in_the_window_report_is_named(
    change: dict[str, object], problem: str
) -> None:
    assert smoke.window_problems({**good_report(), **change}) == [problem]


def test_the_report_written_by_the_app_passes_the_smoke_check(tmp_path: Path) -> None:
    from sci2audio.web.config import server_config
    from sci2audio.web.window import write_report

    config = server_config(50123, launched_as="window")
    write_report(tmp_path / "r.json", config, "window", good_report()["page"])  # type: ignore[arg-type]
    report = json.loads((tmp_path / "r.json").read_text(encoding="utf-8"))
    assert smoke.window_problems(report) == []


def test_audio_files_are_recognised_by_their_first_bytes(tmp_path: Path) -> None:
    m4b, mp3, frame, small = (tmp_path / n for n in ("a.m4b", "a.mp3", "b.mp3", "c.m4b"))
    m4b.write_bytes(b"\0\0\0\x20ftypM4A " + b"\0" * 20_000)
    mp3.write_bytes(b"ID3" + b"\0" * 20_000)
    frame.write_bytes(b"\xff\xfb\x90\x00" + b"\0" * 20_000)
    small.write_bytes(b"\0\0\0\x20ftypM4A ")
    assert smoke.is_m4b(m4b)
    assert smoke.is_mp3(mp3)
    assert smoke.is_mp3(frame)
    assert not smoke.is_m4b(small)  # no audio in it
    assert not smoke.is_m4b(mp3)
    assert not smoke.is_mp3(m4b)


def test_the_offline_check_fails_where_the_network_answers(monkeypatch: pytest.MonkeyPatch) -> None:
    class Open:
        def __enter__(self) -> Open:
            return self

        def __exit__(self, *exc: object) -> None:
            return None

    monkeypatch.setattr(smoke.socket, "create_connection", lambda *a, **k: Open())
    assert smoke.no_network() is False

    def refused(*args: object, **kwargs: object) -> None:
        raise OSError("Network is unreachable")

    monkeypatch.setattr(smoke.socket, "create_connection", refused)
    assert smoke.no_network() is True


# ---- the workflows ------------------------------------------------------------------------


def test_every_action_in_the_installers_workflow_is_pinned_to_a_commit() -> None:
    for text in (INSTALLERS, RELEASE):
        for used in re.findall(r"uses: (\S+)", text):
            if used.startswith("./"):
                continue
            assert re.fullmatch(r"[\w.-]+/[\w.-]+(/[\w./-]+)?@[0-9a-f]{40}", used), used


def test_nothing_is_published_unless_every_installer_passed() -> None:
    assert "needs: [build, smoke, installers]" in RELEASE  # publish to PyPI
    assert "needs: [publish, installers]" in RELEASE  # the GitHub release
    assert "uses: ./.github/workflows/installers.yml" in RELEASE
    assert "release: true" in RELEASE
    # the smoke job needs the build, the build needs the tested ffmpeg
    assert re.search(r"^  smoke:\n(    .*\n)*?    needs: build$", INSTALLERS, re.M)
    assert re.search(r"^  build:\n(    .*\n)*?    needs: ffmpeg$", INSTALLERS, re.M)


def test_a_release_build_reads_no_cache_of_the_ffmpeg_build() -> None:
    cache = INSTALLERS[INSTALLERS.index("A build of the same sources") :]
    cache = cache[: cache.index("      - name: Download")]
    assert "if: ${{ !inputs.release }}" in cache


def test_the_fast_tests_run_against_the_built_ffmpeg() -> None:
    job = INSTALLERS[INSTALLERS.index("  ffmpeg:") : INSTALLERS.index("  sources:")]
    assert 'export IMAGEIO_FFMPEG_EXE="$GITHUB_WORKSPACE/ffmpeg-out/$exe"' in job
    assert 'uv run pytest -m "not slow and not benchmark and not browser"' in job


def test_on_a_pr_the_installers_run_only_with_their_label() -> None:
    for job in ("ffmpeg", "sources"):
        part = INSTALLERS[INSTALLERS.index(f"  {job}:") :]
        assert "contains(github.event.pull_request.labels.*.name, 'ci:installers')" in part[:800]
        assert "github.event.pull_request.head.repo.full_name == github.repository" in part[:800]


def test_the_smoke_tests_cover_every_system_and_every_check() -> None:
    job = INSTALLERS[INSTALLERS.index("  smoke:") :]
    assert "os: [ubuntu-22.04, ubuntu-24.04, macos-latest, windows-latest]" in job
    for step in (
        "installer_smoke.py cli",
        "--offline",
        "unshare --net",
        "installer_smoke.py window",
        "installer_smoke.py browser",
        "tests/browser/test_installed_window.py",
        'installer_smoke.py\\" record',
        "SCI2AUDIO_APP_START",
        "unins000.exe",
    ):
        assert step in job, step
    # an elevated WebView2 ignores it on the hosted runners; the app never opens a port
    steps = "\n".join(line for line in job.splitlines() if not line.lstrip().startswith("#"))
    assert "WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS" not in steps
