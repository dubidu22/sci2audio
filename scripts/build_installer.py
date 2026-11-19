"""Builds sci2audio's installer for the system it runs on (#215, D-797, D-798).

    uv run --no-sync --with pip-licenses python scripts/build_installer.py \
        --ffmpeg FOLDER --out FOLDER [--iscc ISCC.exe] [--appimagetool TOOL --runtime FILE]

FOLDER of --ffmpeg is what packaging/ffmpeg/build.sh made: the audio-only FFmpeg and its
licences. The environment is the locked run-time one with the `window` extra and the
`installer` group (`uv sync --locked --no-dev --extra window --group installer`).

Steps: the licences folder (the bundle's `licenses/`; fails on a refused licence, as CI's
licences job does), PyInstaller (packaging/sci2audio.spec), a check of the frozen folder,
then the system's installer: a .dmg with the ad-hoc signed sci2audio.app (macOS), a per-user
setup.exe from Inno Setup (Windows) or an AppImage (Linux). Prints the file and its SHA-256.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "packaging" / "sci2audio.spec"
REPOSITORY = "https://github.com/dubidu22/sci2audio"
DUPLICATE_SIZE = 1_000_000  # two files this large with the same bytes fail the build (#635 F2)

# the same refusals as CI's licences job (.github/workflows/ci.yml); espeakng-loader and
# clr-loader (Windows) state no licence in their metadata and were checked by hand: their
# repositories' LICENSE files (THIRD_PARTY_LICENSES.md)
REFUSED = "Affero;AGPL;SSPL;Non-Commercial;NonCommercial;UNKNOWN"
NOT_CHECKED = (
    "sci2audio", "pip-licenses", "prettytable", "wcwidth", "espeakng-loader", "clr-loader",
)  # fmt: skip


def package_version(root: Path = ROOT) -> str:
    text = (root / "src" / "sci2audio" / "__init__.py").read_text(encoding="utf-8")
    found = re.search(r'^__version__ = "([^"]+)"$', text, re.M)
    if found is None:
        raise SystemExit("build_installer: no __version__ in src/sci2audio/__init__.py")
    return found.group(1)


def system_of(platform: str = sys.platform) -> str:
    for prefix, system in (("darwin", "macos"), ("win32", "windows"), ("linux", "linux")):
        if platform.startswith(prefix):
            return system
    raise SystemExit(f"build_installer: no installer for {platform}")


def installer_name(version: str, system: str) -> str:
    """The file a tester downloads; the release notes and the smoke tests use these names."""
    return {
        "macos": f"sci2audio-{version}-macos-arm64.dmg",
        "windows": f"sci2audio-{version}-windows-x64-setup.exe",
        "linux": f"sci2audio-{version}-linux-x86_64.AppImage",
    }[system]


def ffmpeg_name(system: str) -> str:
    return "ffmpeg.exe" if system == "windows" else "ffmpeg"


def source_note(version: str, ffmpeg_licenses: Path) -> str:
    """SOURCE.txt in the licences folder: where the complete source of every GPL or LGPL
    program in the bundle is (GPL-3.0 section 6, LGPL-2.1 section 6)."""
    configuration = ffmpeg_licenses / "FFmpeg-configuration.txt"
    lines = [
        f"sci2audio {version}: where the source is",
        "",
        "sci2audio is free software under the GNU General Public License, version 3 or later",
        "(LICENSE). This program bundles other free software; THIRD_PARTY_LICENSES.md lists",
        "each part and its licence, and python-packages.txt holds the licence texts of the",
        "Python packages.",
        "",
        "The complete corresponding source of this build is on its release page,",
        f"{REPOSITORY}/releases/tag/v{version}:",
        "",
        f"- sci2audio-{version}.tar.gz: sci2audio itself;",
        f"- sci2audio-{version}-sources.tar: FFmpeg and LAME (the audio-only ffmpeg program,",
        "  LGPL-2.1-or-later), espeak-ng (GPL-3.0-or-later, inside espeakng-loader), the",
        "  script that builds ffmpeg from them (packaging/ffmpeg/build.sh), and the Linux",
        "  AppImage's type-2 runtime (MIT) with the libfuse 3 (LGPL-2.1) and squashfuse",
        "  (BSD-2-Clause) it links statically.",
        "",
        "The Python packages are the versions named in the project's uv.lock at that tag,",
        "each available from the Python Package Index (pypi.org) with its source.",
    ]
    if configuration.exists():
        lines += ["", "ffmpeg was configured with:", ""]
        lines += configuration.read_text(encoding="utf-8").strip().splitlines()
    return "\n".join(lines) + "\n"


def python_licence(base: Path = Path(sys.base_prefix)) -> Path:
    """The PSF licence of the Python the bundle carries (Windows: next to python.exe;
    Linux and macOS: in the standard library's folder)."""
    short = f"python{sys.version_info[0]}.{sys.version_info[1]}"
    for candidate in (base / "LICENSE.txt", base / "lib" / short / "LICENSE.txt"):
        if candidate.is_file():
            return candidate
    raise SystemExit(f"build_installer: Python's LICENSE.txt is not in {base}")


def vendored_licences(system: str) -> list[str]:
    """Licence texts from packaging/licenses/ for parts whose packages ship none (#635 F4)."""
    names = ["espeakng-loader-LICENSE"]
    if system == "windows":
        names += ["clr-loader-LICENSE", "winpthreads-COPYING"]
    return names


def licences(dest: Path, ffmpeg: Path, version: str, system: str) -> None:
    """The bundle's `licenses/` folder; stops on a refused licence."""
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    shutil.copy2(ROOT / "LICENSE", dest / "LICENSE")
    shutil.copy2(ROOT / "THIRD_PARTY_LICENSES.md", dest / "THIRD_PARTY_LICENSES.md")
    shutil.copy2(python_licence(), dest / "Python-LICENSE.txt")
    for item in sorted((ffmpeg / "licenses").iterdir()):
        shutil.copy2(item, dest / item.name)
    for name in vendored_licences(system):
        shutil.copy2(ROOT / "packaging" / "licenses" / name, dest / name)
    (dest / "SOURCE.txt").write_text(source_note(version, ffmpeg / "licenses"), encoding="utf-8")
    subprocess.run(
        [
            sys.executable, "-m", "piplicenses",
            "--with-license-file", "--no-license-path", "--with-urls",
            "--format=plain-vertical",
            f"--output-file={dest / 'python-packages.txt'}",
            "--ignore-packages", *NOT_CHECKED,
            "--partial-match", f"--fail-on={REFUSED}",
        ],
        check=True,
    )  # fmt: skip


def check_bundle(folder: Path, system: str) -> list[str]:
    """What is wrong with the frozen folder (`dist/sci2audio`): empty when it is right."""
    internal = folder / "_internal" if (folder / "_internal").is_dir() else folder
    problems = []
    if not (internal / "ffmpeg" / ffmpeg_name(system)).is_file():
        problems.append("the audio-only ffmpeg is missing (ffmpeg/)")
    binaries = internal / "imageio_ffmpeg" / "binaries"
    if binaries.is_dir() and any(p.name.startswith("ffmpeg") for p in binaries.iterdir()):
        problems.append("imageio-ffmpeg's own ffmpeg is in the bundle (D-798)")
    for name in (
        "LICENSE", "THIRD_PARTY_LICENSES.md", "SOURCE.txt", "python-packages.txt",
        *vendored_licences(system),
    ):  # fmt: skip
        if not (internal / "licenses" / name).is_file():
            problems.append(f"licenses/{name} is missing")
    suffix = ".exe" if system == "windows" else ""
    for program in ("sci2audio", "sci2audio-app"):
        if not (folder / f"{program}{suffix}").is_file():
            problems.append(f"{program}{suffix} is missing")
    problems += torch_problems(internal / "torch", system)
    problems += [
        f"{' and '.join(names)} are the same file of {size // 1_000_000} MB (#635 F2)"
        for size, names in duplicates(folder)
    ]
    return problems


def torch_problems(torch: Path, system: str) -> list[str]:
    """torch/bin holds only torch_shm_manager, which torch looks for at import on Linux
    and macOS; the rest are torch's own test programs (#635 F2)."""
    if not torch.is_dir():
        return []
    problems = []
    tools = torch / "bin"
    extra = (
        sorted(p.name for p in tools.iterdir() if p.name != "torch_shm_manager")
        if tools.is_dir()
        else []
    )
    if extra:
        problems.append(f"torch/bin holds torch's test programs: {', '.join(extra)} (#635 F2)")
    if system != "windows" and not (tools / "torch_shm_manager").is_file():
        problems.append("torch/bin/torch_shm_manager is missing: torch needs it at import")
    return problems


def duplicates(folder: Path, least: int = DUPLICATE_SIZE) -> list[tuple[int, list[str]]]:
    """Files of `least` bytes or more that hold the same bytes, as paths in `folder`."""
    by_size: dict[int, list[Path]] = {}
    for path in folder.rglob("*"):
        if path.is_file() and not path.is_symlink():
            size = path.stat().st_size
            if size >= least:
                by_size.setdefault(size, []).append(path)
    found = []
    for size, paths in sorted(by_size.items()):
        if len(paths) < 2:
            continue
        by_hash: dict[str, list[str]] = {}
        for path in paths:
            by_hash.setdefault(sha256(path), []).append(path.relative_to(folder).as_posix())
        found += [(size, sorted(names)) for names in by_hash.values() if len(names) > 1]
    return found


def freeze(work: Path, ffmpeg: Path, version: str, system: str) -> Path:
    """PyInstaller: returns the frozen folder (on macOS the folder inside the .app)."""
    licences(work / "licenses", ffmpeg, version, system)
    env = {
        **os.environ,
        "SCI2AUDIO_VERSION": version,
        "SCI2AUDIO_FFMPEG": str(ffmpeg / ffmpeg_name(system)),
        "SCI2AUDIO_LICENSES": str(work / "licenses"),
    }
    subprocess.run(
        [
            sys.executable, "-m", "PyInstaller", str(SPEC), "--noconfirm", "--clean",
            "--distpath", str(work / "dist"), "--workpath", str(work / "build"),
        ],
        check=True, env=env,
    )  # fmt: skip
    folder = work / "dist" / "sci2audio"
    problems = check_bundle(folder, system)
    if problems:
        raise SystemExit("build_installer: " + "; ".join(problems))
    return folder


def run(*args: str | Path, env: dict[str, str] | None = None) -> None:
    print("+", " ".join(str(a) for a in args), flush=True)
    subprocess.run([str(a) for a in args], check=True, env=env)


def macos_dmg(work: Path, out: Path) -> None:
    app = work / "dist" / "sci2audio.app"
    # ad-hoc signature: Apple Silicon runs no unsigned code; not notarised (no paid account,
    # D-797 q4), so the first start goes through Privacy & Security, "Open Anyway"
    run("codesign", "--force", "--deep", "--sign", "-", app)
    run("codesign", "--verify", "--deep", "--strict", app)
    stage = work / "dmg"
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir()
    run("ditto", app, stage / "sci2audio.app")
    (stage / "Applications").symlink_to("/Applications")
    run(
        "hdiutil", "create", "-volname", "sci2audio", "-srcfolder", stage,
        "-fs", "HFS+", "-format", "ULFO", "-ov", out,
    )  # fmt: skip


def windows_setup(folder: Path, out: Path, version: str, iscc: Path) -> None:
    run(
        iscc,
        f"/DAppVersion={version}",
        f"/DSourceDir={folder}",
        f"/DRepoDir={ROOT}",
        f"/DOutputDir={out.parent}",
        f"/DOutputName={out.stem}",
        ROOT / "packaging" / "windows" / "sci2audio.iss",
    )


def appdir(folder: Path, dest: Path) -> Path:
    """The AppImage's folder: AppRun, the desktop file, the icon and the frozen program."""
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    shutil.copytree(folder, dest / "sci2audio", symlinks=True)
    linux = ROOT / "packaging" / "linux"
    shutil.copy2(linux / "AppRun", dest / "AppRun")
    (dest / "AppRun").chmod(0o755)
    shutil.copy2(linux / "sci2audio.desktop", dest / "sci2audio.desktop")
    shutil.copy2(ROOT / "packaging" / "icons" / "sci2audio.png", dest / "sci2audio.png")
    (dest / ".DirIcon").symlink_to("sci2audio.png")
    return dest


def linux_appimage(folder: Path, work: Path, out: Path, tool: Path, runtime: Path) -> None:
    app = appdir(folder, work / "AppDir")
    env = {**os.environ, "ARCH": "x86_64", "APPIMAGE_EXTRACT_AND_RUN": "1"}  # no FUSE needed
    run(tool, "--no-appstream", "--runtime-file", runtime, app, out, env=env)
    out.chmod(0o755)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--ffmpeg", type=Path, required=True, help="packaging/ffmpeg/build.sh's output"
    )
    parser.add_argument("--out", type=Path, required=True, help="where the installer goes")
    parser.add_argument("--work", type=Path, default=ROOT / "build" / "installer")
    parser.add_argument("--iscc", type=Path, help="Inno Setup's ISCC.exe (Windows)")
    parser.add_argument("--appimagetool", type=Path, help="appimagetool (Linux)")
    parser.add_argument("--runtime", type=Path, help="the AppImage type-2 runtime (Linux)")
    args = parser.parse_args(argv)
    system = system_of()
    version = package_version()
    work = args.work.resolve()
    out = args.out.resolve() / installer_name(version, system)
    out.parent.mkdir(parents=True, exist_ok=True)
    folder = freeze(work, args.ffmpeg.resolve(), version, system)
    if system == "macos":
        macos_dmg(work, out)
    elif system == "windows":
        if args.iscc is None:
            parser.error("--iscc is needed on Windows")
        windows_setup(folder, out, version, args.iscc)
    else:
        if args.appimagetool is None or args.runtime is None:
            parser.error("--appimagetool and --runtime are needed on Linux")
        linux_appimage(folder, work, out, args.appimagetool, args.runtime)
    digest = sha256(out)
    Path(f"{out}.sha256").write_text(f"{digest}  {out.name}\n", encoding="utf-8")
    print(f"{out.name}: {out.stat().st_size / 1e6:.0f} MB, SHA-256 {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
