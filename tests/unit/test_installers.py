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
import shutil
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
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


@pytest.mark.parametrize(
    ("stem", "hashed"),
    [
        ("ESPEAK_NG", "ESPEAK_NG_SHA256"),
        ("APPIMAGE_RUNTIME", "APPIMAGE_RUNTIME_SOURCE_SHA256"),  # tools.env pins its binary
        ("SQUASHFUSE", "SQUASHFUSE_SHA256"),
    ],
)
def test_each_source_from_git_is_a_pinned_commit_and_hash(stem: str, hashed: str) -> None:
    found = pins(PACKAGING / "ffmpeg" / "sources.env")
    assert found[f"{stem}_GIT"].startswith("https://github.com/"), stem
    assert re.fullmatch(r"[0-9a-f]{40}", found[f"{stem}_COMMIT"]), stem
    assert re.fullmatch(r"[0-9a-f]{64}", found[hashed]), stem


def test_the_sources_name_the_runtime_the_appimage_uses(tmp_path: Path) -> None:
    """The type-2 runtime's source is the release tools.env downloads the runtime of, and
    libfuse 3 and squashfuse come with it (#635 F3)."""
    sources = pins(PACKAGING / "ffmpeg" / "sources.env")
    tools = pins(PACKAGING / "tools.env")
    assert sources["APPIMAGE_RUNTIME_VERSION"] in tools["APPIMAGE_RUNTIME_URL"]
    assert sources["LIBFUSE_URL"].endswith(f"fuse-{sources['LIBFUSE_VERSION']}.tar.xz")
    note = build.source_note("1.4.0", tmp_path)
    for named in ("type-2 runtime", "libfuse 3", "squashfuse", "LGPL-2.1", "BSD-2-Clause"):
        assert named in note
    third = (ROOT / "THIRD_PARTY_LICENSES.md").read_text(encoding="utf-8")
    assert "libfuse/libfuse) 3.15.0" in third
    assert "vasi/squashfuse) 0.5.2" in third


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


def test_the_mac_app_asks_for_the_macos_its_libraries_were_built_for() -> None:
    """torch and onnxruntime publish macosx_14_0_arm64 wheels only (minos 14.0)."""
    spec = (PACKAGING / "sci2audio.spec").read_text(encoding="utf-8")
    assert '"LSMinimumSystemVersion": "14.0"' in spec
    for doc in ("CHANGELOG.md", "docs/installing.md"):
        assert "macOS 14 (Sonoma) or newer" in (ROOT / doc).read_text(encoding="utf-8"), doc


def test_the_spec_leaves_imageio_ffmpegs_program_out_and_brings_its_own() -> None:
    spec = (PACKAGING / "sci2audio.spec").read_text(encoding="utf-8")
    assert 'DROPPED = "imageio_ffmpeg/binaries"' in spec
    assert spec.count("without_imageio_ffmpeg(found.") == 2  # binaries and datas
    assert 'binaries.append((str(FFMPEG), "ffmpeg"))' in spec
    assert 'datas.append((str(LICENSES), "licenses"))' in spec


# ---- the archives are checked by their SHA-256 ----------------------------------------------

SOURCES = ("ffmpeg", "lame", "espeak", "runtime", "fuse", "squashfuse")
BASH = shutil.which("bash")
needs_bash = pytest.mark.skipif(
    sys.platform == "win32" or BASH is None, reason="the scripts run in bash"
)


def bash(script: Path, *args: Path | str) -> subprocess.CompletedProcess[str]:
    command = [str(BASH), str(script), *(str(a) for a in args)]
    return subprocess.run(command, capture_output=True, text=True, check=False)


def sha(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def fake_sources(tmp_path: Path) -> tuple[Path, Path, dict[str, Path]]:
    """The two scripts beside a sources.env that pins small stand-in archives (no network:
    every archive is already in the downloads folder)."""
    here = tmp_path / "ffmpeg"
    here.mkdir()
    for script in ("build.sh", "sources_archive.sh"):
        shutil.copy2(PACKAGING / "ffmpeg" / script, here / script)
    downloads = tmp_path / "downloads"
    downloads.mkdir()
    files = {
        "ffmpeg": downloads / "ffmpeg-1.tar.xz",
        "lame": downloads / "lame-2.tar.gz",
        "espeak": downloads / "espeak-ng-3.tar",
        "runtime": downloads / "type2-runtime-4.tar",
        "fuse": downloads / "fuse-5.tar.xz",
        "squashfuse": downloads / "squashfuse-6.tar",
    }
    for name, path in files.items():
        path.write_bytes(f"the {name} archive".encode())
    git = "https://example.invalid/never.git"
    commit = "0" * 40
    (here / "sources.env").write_text(
        "\n".join(
            [
                "FFMPEG_VERSION=1", "FFMPEG_URL=https://example.invalid/f",
                f"FFMPEG_SHA256={sha(files['ffmpeg'])}",
                "LAME_VERSION=2", "LAME_URL=https://example.invalid/l",
                f"LAME_SHA256={sha(files['lame'])}",
                "ESPEAK_NG_VERSION=3", f"ESPEAK_NG_GIT={git}", f"ESPEAK_NG_COMMIT={commit}",
                f"ESPEAK_NG_SHA256={sha(files['espeak'])}",
                "APPIMAGE_RUNTIME_VERSION=4", f"APPIMAGE_RUNTIME_GIT={git}",
                f"APPIMAGE_RUNTIME_COMMIT={commit}",
                f"APPIMAGE_RUNTIME_SOURCE_SHA256={sha(files['runtime'])}",
                "LIBFUSE_VERSION=5", "LIBFUSE_URL=https://example.invalid/u",
                f"LIBFUSE_SHA256={sha(files['fuse'])}",
                "SQUASHFUSE_VERSION=6", f"SQUASHFUSE_GIT={git}", f"SQUASHFUSE_COMMIT={commit}",
                f"SQUASHFUSE_SHA256={sha(files['squashfuse'])}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )  # fmt: skip
    return here, downloads, files


@needs_bash
def test_the_sources_archive_holds_every_pinned_archive(tmp_path: Path) -> None:
    here, downloads, files = fake_sources(tmp_path)
    done = bash(here / "sources_archive.sh", "1.4.0", downloads, tmp_path / "out")
    assert done.returncode == 0, done.stderr
    import tarfile

    with tarfile.open(tmp_path / "out" / "sci2audio-1.4.0-sources.tar") as archive:
        names = {Path(n).name for n in archive.getnames()}
        readme = archive.extractfile("sci2audio-1.4.0-sources/README.txt").read().decode()  # type: ignore[union-attr]
    assert {p.name for p in files.values()} | {"build.sh", "sources.env", "README.txt"} <= names
    for path in files.values():
        assert path.name in readme
    for named in ("type-2 runtime", "libfuse 5", "squashfuse 6", "LGPL-2.1-only", "BSD-2-Clause"):
        assert named in readme


@needs_bash
@pytest.mark.parametrize("tampered", SOURCES)
def test_the_sources_archive_refuses_an_archive_whose_hash_differs(
    tmp_path: Path, tampered: str
) -> None:
    here, downloads, files = fake_sources(tmp_path)
    files[tampered].write_bytes(b"something else")
    done = bash(here / "sources_archive.sh", "1.4.0", downloads, tmp_path / "out")
    assert done.returncode == 1
    assert re.search(
        rf"{re.escape(files[tampered].name)}: SHA-256 [0-9a-f]{{64}}, expected", done.stderr
    )
    assert not (tmp_path / "out" / "sci2audio-1.4.0-sources.tar").exists()


@needs_bash
@pytest.mark.parametrize("tampered", ["ffmpeg", "lame"])
def test_the_ffmpeg_build_refuses_an_archive_whose_hash_differs(
    tmp_path: Path, tampered: str
) -> None:
    here, downloads, files = fake_sources(tmp_path)
    files[tampered].write_bytes(b"something else")
    done = bash(here / "build.sh", downloads, tmp_path / "out")
    assert done.returncode == 1
    assert re.search(
        rf"{re.escape(files[tampered].name)}: SHA-256 [0-9a-f]{{64}}, expected", done.stderr
    )


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
    for name in (
        "LICENSE", "THIRD_PARTY_LICENSES.md", "SOURCE.txt", "python-packages.txt",
        *build.vendored_licences(system),
    ):  # fmt: skip
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


@pytest.mark.parametrize("system", ["macos", "windows", "linux"])
def test_torchs_test_programs_fail_the_build(tmp_path: Path, system: str) -> None:
    folder = frozen(tmp_path / "sci2audio", system)
    tools = folder / "_internal" / "torch" / "bin"
    tools.mkdir(parents=True)
    (tools / "torch_shm_manager").write_bytes(b"x")
    assert build.check_bundle(folder, system) == []
    (tools / "protoc").write_bytes(b"x")
    (tools / "test_api").write_bytes(b"x")
    assert build.check_bundle(folder, system) == [
        "torch/bin holds torch's test programs: protoc, test_api (#635 F2)"
    ]


@pytest.mark.parametrize(
    ("system", "needed"), [("linux", True), ("macos", True), ("windows", False)]
)
def test_torch_keeps_the_one_program_it_needs_at_import(
    tmp_path: Path, system: str, needed: bool
) -> None:
    folder = frozen(tmp_path / "sci2audio", system)
    (folder / "_internal" / "torch").mkdir()
    problem = "torch/bin/torch_shm_manager is missing: torch needs it at import"
    assert build.check_bundle(folder, system) == ([problem] if needed else [])


def test_a_large_file_twice_in_the_bundle_fails_the_build(tmp_path: Path) -> None:
    folder = frozen(tmp_path / "sci2audio", "linux")
    library = os.urandom(build.DUPLICATE_SIZE)
    (folder / "_internal" / "torch" / "lib").mkdir(parents=True)
    (folder / "_internal" / "torch" / "bin").mkdir()
    (folder / "_internal" / "torch" / "bin" / "torch_shm_manager").write_bytes(b"x")
    (folder / "_internal" / "torch" / "lib" / "libc10.so").write_bytes(library)
    (folder / "_internal" / "libc10.so").write_bytes(library)
    assert build.check_bundle(folder, "linux") == [
        "_internal/libc10.so and _internal/torch/lib/libc10.so are the same file of 1 MB (#635 F2)"
    ]


def test_only_large_files_with_the_same_bytes_are_duplicates(tmp_path: Path) -> None:
    same = os.urandom(2000)
    (tmp_path / "a").write_bytes(same)
    (tmp_path / "b").mkdir()
    (tmp_path / "b" / "a").write_bytes(same)
    (tmp_path / "c").write_bytes(os.urandom(2000))  # the same size, other bytes
    (tmp_path / "small").write_bytes(b"x" * 10)
    (tmp_path / "small2").write_bytes(b"x" * 10)  # the same bytes, too small to count
    assert build.duplicates(tmp_path, least=1000) == [(2000, ["a", "b/a"])]
    assert build.duplicates(tmp_path, least=2001) == []
    if sys.platform != "win32":
        (tmp_path / "link").symlink_to(tmp_path / "c")  # a link is not a second copy
        assert build.duplicates(tmp_path, least=1000) == [(2000, ["a", "b/a"])]


def spec_function(name: str) -> object:
    """A function of packaging/sci2audio.spec, run without PyInstaller."""
    import ast

    source = (PACKAGING / "sci2audio.spec").read_text(encoding="utf-8")
    tree = ast.parse(source)
    keep = [
        node
        for node in tree.body
        if (isinstance(node, ast.FunctionDef) and node.name in (name, "library_home"))
        or (
            isinstance(node, ast.Assign)
            and all(isinstance(t, ast.Name) and t.id.startswith("TORCH_") for t in node.targets)
        )
    ]
    space: dict[str, object] = {"os": os, "Path": Path, "sys": sys}
    exec(compile(ast.Module(body=keep, type_ignores=[]), "sci2audio.spec", "exec"), space)  # noqa: S102
    return space[name]


@pytest.mark.parametrize(
    ("dest", "home"),
    [
        ("torch/lib/libc10.so", True),
        ("numpy.libs/libscipy_openblas64_.dll", True),  # auditwheel, delvewheel
        ("sklearn/.dylibs/libomp.dylib", True),  # delocate
        ("libc10.so", False),
        ("torch/_C.so", False),
        ("numpy/core/_multiarray_umath.so", False),
    ],
)
def test_the_spec_knows_where_packages_keep_their_libraries(dest: str, home: bool) -> None:
    assert spec_function("library_home")(str(Path(dest))) is home  # type: ignore[operator]


def test_the_spec_keeps_one_copy_of_torchs_libraries_and_leaves_torch_bin_out(
    tmp_path: Path,
) -> None:
    lib = tmp_path / "torch" / "lib"
    lib.mkdir(parents=True)
    for name in ("libc10.so", "libtorch_cpu.so"):
        (lib / name).write_bytes(b"x")
    other = tmp_path / "libssl.so"
    other.write_bytes(b"x")
    blas = tmp_path / "numpy.libs" / "libscipy_openblas64_-ed4f.dll"
    blas.parent.mkdir()
    blas.write_bytes(b"x")
    binaries = [
        ("libc10.so", str(lib / "libc10.so"), "BINARY"),  # the analysis's copy at the top
        ("libssl.so", str(other), "BINARY"),  # in no package's library folder: stays
        (blas.name, str(blas), "BINARY"),  # numpy.libs's copy at the top (Windows)
        (str(Path("numpy.libs") / blas.name), str(blas), "BINARY"),
        (str(Path("torch/bin/protoc")), str(tmp_path / "protoc"), "BINARY"),
    ]
    datas = [
        (str(Path("torch/lib/libc10.so")), str(lib / "libc10.so"), "DATA"),
        (str(Path("torch/lib/libtorch_cpu.so")), str(lib / "libtorch_cpu.so"), "DATA"),
        (str(Path("torch/bin/test_api")), str(tmp_path / "test_api"), "DATA"),
        (str(Path("torch/bin/torch_shm_manager")), str(tmp_path / "shm"), "DATA"),
    ]
    one_copy = spec_function("one_copy")
    everything = binaries + datas
    assert one_copy(binaries, everything, top_level=True) == [binaries[1], binaries[3]]  # type: ignore[operator]
    # macOS: every binary's @rpath is the top of the folder; only torch/bin goes
    assert one_copy(binaries, everything, top_level=False) == binaries[:4]  # type: ignore[operator]
    assert one_copy(datas, everything, top_level=True) == [datas[0], datas[1], datas[3]]  # type: ignore[operator]
    spec = (PACKAGING / "sci2audio.spec").read_text(encoding="utf-8")
    assert "found.binaries = one_copy(without_imageio_ffmpeg(found.binaries), everything)" in spec
    assert "found.datas = one_copy(without_imageio_ffmpeg(found.datas), everything)" in spec


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


@pytest.mark.parametrize(
    ("system", "missing"),
    [
        ("linux", "espeakng-loader-LICENSE"),
        ("macos", "espeakng-loader-LICENSE"),
        ("windows", "espeakng-loader-LICENSE"),
        ("windows", "clr-loader-LICENSE"),
        ("windows", "winpthreads-COPYING"),
    ],
)
def test_a_bundle_without_a_vendored_licence_text_fails(
    tmp_path: Path, system: str, missing: str
) -> None:
    folder = frozen(tmp_path / "sci2audio", system)
    (folder / "_internal" / "licenses" / missing).unlink()
    assert build.check_bundle(folder, system) == [f"licenses/{missing} is missing"]


def test_the_windows_only_licence_texts_are_not_asked_for_elsewhere() -> None:
    assert build.vendored_licences("linux") == ["espeakng-loader-LICENSE"]
    assert build.vendored_licences("macos") == ["espeakng-loader-LICENSE"]
    assert set(build.vendored_licences("windows")) == {
        "espeakng-loader-LICENSE", "clr-loader-LICENSE", "winpthreads-COPYING",
    }  # fmt: skip


def test_the_vendored_licence_texts_are_the_projects_own() -> None:
    folder = PACKAGING / "licenses"
    readme = (folder / "README.md").read_text(encoding="utf-8")
    for name in build.vendored_licences("windows"):
        text = (folder / name).read_text(encoding="utf-8")
        assert "Permission is hereby granted, free of charge" in text, name  # MIT
        assert f"`{name}`" in readme  # with where it was taken from
    assert "Benedikt Reinartz" in (folder / "clr-loader-LICENSE").read_text(encoding="utf-8")
    assert "thewh1teagle" in (folder / "espeakng-loader-LICENSE").read_text(encoding="utf-8")
    winpthreads = (folder / "winpthreads-COPYING").read_text(encoding="utf-8")
    assert "mingw-w64 project" in winpthreads
    assert "Lockless Inc." in winpthreads  # the BSD-3-Clause part
    assert readme.count("https://github.com/") == 3


def test_the_licences_folder_holds_every_text_and_refuses_what_ci_refuses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ffmpeg = tmp_path / "ffmpeg"
    (ffmpeg / "licenses").mkdir(parents=True)
    (ffmpeg / "licenses" / "FFmpeg-COPYING.LGPLv2.1").write_text("LGPL", encoding="utf-8")
    python = tmp_path / "Python-LICENSE.txt"
    python.write_text("PSF", encoding="utf-8")
    monkeypatch.setattr(build, "python_licence", lambda: python)
    commands: list[list[str]] = []
    monkeypatch.setattr(build.subprocess, "run", lambda command, **kwargs: commands.append(command))
    dest = tmp_path / "licenses"
    build.licences(dest, ffmpeg, "1.4.0", "windows")
    names = {p.name for p in dest.iterdir()}
    assert {
        "LICENSE", "THIRD_PARTY_LICENSES.md", "Python-LICENSE.txt", "SOURCE.txt",
        "FFmpeg-COPYING.LGPLv2.1", *build.vendored_licences("windows"),
    } <= names  # fmt: skip
    [command] = commands
    assert command[1:3] == ["-m", "piplicenses"]
    assert f"--fail-on={build.REFUSED}" in command
    assert f"--output-file={dest / 'python-packages.txt'}" in command


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
    # never for all users, never elevated (#635 F1): no dialog that offers it
    assert "PrivilegesRequiredOverridesAllowed" not in script
    assert "DefaultDirName={autopf}\\sci2audio" in script
    # no folder page: a folder chosen by hand could be Documents\sci2audio, the
    # audiobooks' own folder, or a folder of the person's (#635 F1)
    assert re.search(r"^DisableDirPage=yes$", script, re.M)
    # the uninstaller removes what it installed; nothing is deleted by a wildcard, and
    # never the program folder as a whole or anything above it
    assert "[UninstallDelete]" not in script
    assert "filesandordirs" not in script
    assert "[InstallDelete]" not in script


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
        (
            {"page": {k: v for k, v in good_report()["page"].items() if k != "rail"}},  # type: ignore[union-attr]
            "the rail is not drawn",
        ),  # a report without it: the page could not be read
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


class Ran:
    def __init__(self, returncode: int) -> None:
        self.returncode = returncode


def test_the_window_check_fails_when_the_app_ends_badly_after_a_good_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    report = tmp_path / "report.json"

    def app(command: list[str], **kwargs: object) -> Ran:
        report.write_text(json.dumps(good_report()), encoding="utf-8")
        return Ran(returncode)

    monkeypatch.setattr(smoke.subprocess, "run", app)
    returncode = 0
    smoke.smoke_window(tmp_path / "sci2audio-app", report)
    returncode = 1
    with pytest.raises(smoke.Failed, match="the app ended with 1"):
        smoke.smoke_window(tmp_path / "sci2audio-app", report)


@pytest.mark.parametrize(("quit", "passes"), [(202, True), (404, False), (None, False)])
def test_the_browser_check_needs_quit_to_be_accepted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, quit: int | None, passes: bool
) -> None:
    report = tmp_path / "report.json"

    def app(command: list[str], **kwargs: object) -> Ran:
        found = {"start": "http://127.0.0.1:5/start", "library": "/", "quit_in_rail": True}
        if quit is not None:
            found["quit"] = quit  # type: ignore[assignment]
        report.write_text(json.dumps(found), encoding="utf-8")
        return Ran(0)

    monkeypatch.setattr(smoke.subprocess, "run", app)
    if passes:
        smoke.smoke_browser(tmp_path / "sci2audio-app", report)
    else:
        with pytest.raises(smoke.Failed, match=f"^Quit answered {quit}$"):
            smoke.smoke_browser(tmp_path / "sci2audio-app", report)


class App(BaseHTTPRequestHandler):
    """The app's start link, library and Quit, as the stand-in browser meets them."""

    def do_GET(self) -> None:
        if self.path.startswith("/start?token="):
            self.send_response(303)
            self.send_header("Location", "/")
            self.send_header("Set-Cookie", "session=s; Path=/; HttpOnly")
            self.end_headers()
            return
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'<nav><button id="quit">Quit</button></nav>')

    def do_POST(self) -> None:
        ok = self.path == "/quit" and "session=s" in self.headers.get("Cookie", "")
        self.send_response(202 if ok else 403)
        self.end_headers()

    def log_message(self, *args: object) -> None:
        return None


def test_the_stand_in_browser_presses_quit_and_never_writes_the_token(tmp_path: Path) -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), App)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        port = server.server_address[1]
        report = tmp_path / "report.json"
        smoke.visit(f"http://127.0.0.1:{port}/start?token=secret-start-token", report)
    finally:
        server.shutdown()
        server.server_close()
    text = report.read_text(encoding="utf-8")
    assert "secret-start-token" not in text
    assert "?" not in text
    assert json.loads(text) == {
        "start": f"http://127.0.0.1:{port}/start",
        "library": "/",
        "quit_in_rail": True,
        "quit_page": 200,
        "quit": 202,
    }


def installed(version: str, *, mp3: bool) -> object:
    """A stand-in for the installed command line: prints `version`, writes a script and
    an M4B, and MP3s only when `mp3`."""

    def call(program: Path, *args: str | Path, timeout: float = 900) -> str:
        if args[0] == "--version":
            return f"sci2audio {version}\n"
        out = Path(args[args.index("-o") + 1])
        out.mkdir(parents=True, exist_ok=True)
        if args[0] == "script":
            stem = Path(args[1]).stem
            for suffix in ("script.txt", "report.json", "report.md"):
                (out / f"{stem}.{suffix}").write_text("x", encoding="utf-8")
        else:
            stem = Path(args[1]).stem
            (out / f"{stem}.m4b").write_bytes(b"\0\0\0\x20ftypM4A " + b"\0" * 20_000)
            if mp3:
                (out / f"{stem}-01.mp3").write_bytes(b"ID3" + b"\0" * 20_000)
        return ""

    return call


def test_the_command_line_check_passes_a_working_program(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(smoke, "call", installed("1.4.0", mp3=True))
    smoke.smoke_cli(tmp_path / "sci2audio", "1.4.0", tmp_path / "models", tmp_path / "w", False)


def test_the_command_line_check_fails_on_another_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(smoke, "call", installed("1.3.9", mp3=True))
    with pytest.raises(smoke.Failed, match=re.escape("version 'sci2audio 1.3.9', expected 1.4.0")):
        smoke.smoke_cli(tmp_path / "sci2audio", "1.4.0", tmp_path / "models", tmp_path / "w", False)


def test_the_command_line_check_fails_when_only_the_m4b_is_written(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(smoke, "call", installed("1.4.0", mp3=False))
    with pytest.raises(smoke.Failed, match="no MP3 of the en text"):
        smoke.smoke_cli(tmp_path / "sci2audio", "1.4.0", tmp_path / "models", tmp_path / "w", False)


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


def test_the_release_attests_every_file_it_publishes() -> None:
    attest = RELEASE[RELEASE.index("actions/attest-build-provenance") :]
    assert re.match(r"[^\n]+\n        with:\n          subject-path: dist/\*\n", attest)


def test_the_uninstall_check_keeps_every_part() -> None:
    step = INSTALLERS[INSTALLERS.index("The uninstaller keeps the person's files") :]
    step = step[: step.index('echo "Uninstalled')]
    for check in (
        '"$FOLDER/unins000.exe" //VERYSILENT',
        'test ! -e "$FOLDER"',  # the program folder is gone
        'test -n "$(ls -A "$MODELS")"',  # the voice files stay
        'test -s "$WORK/online/audio-en/en.m4b"',  # the audiobooks stay
        'test -s "$log"',  # the log stays
    ):
        assert check in step, check
