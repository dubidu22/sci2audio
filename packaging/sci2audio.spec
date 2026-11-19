# PyInstaller build of sci2audio for the installers (#215, D-797): one folder with two
# programs, `sci2audio-app` (the app; windowed on macOS and Windows) and `sci2audio` (the
# command line), sharing one copy of Python and the libraries. On macOS the folder becomes
# sci2audio.app. Run through scripts/build_installer.py, which sets the version, the
# minimal FFmpeg (SCI2AUDIO_FFMPEG, built by packaging/ffmpeg/build.sh, D-798) and the
# licences folder (SCI2AUDIO_LICENSES).
# ruff: noqa
import os
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, copy_metadata

ROOT = Path(SPECPATH).parent
VERSION = os.environ["SCI2AUDIO_VERSION"]
FFMPEG = Path(os.environ["SCI2AUDIO_FFMPEG"])  # the LGPL audio-only build, never imageio's
LICENSES = Path(os.environ["SCI2AUDIO_LICENSES"])
ICONS = ROOT / "packaging" / "icons"

datas, binaries, hidden = [], [], []
# packages with data files, plugins found at run time or modules imported by name
for package in (
    "sci2audio",  # templates, static files, fonts, strings
    "misaki",
    "kokoro",
    "espeakng_loader",  # the espeak-ng library and its data
    "phonemizer",
    "spacy",  # the English model, put on sys.path at run time, imports spaCy's parts
    "thinc",
    "curated_tokenizers",
    "num2words",
    "language_tags",
    "pypdfium2",
    "pypdfium2_raw",
):
    try:
        d, b, h = collect_all(package)
    except Exception:  # not installed on this system
        continue
    datas += d
    binaries += b
    hidden += h
# packages that look up their own version or entry points
for package in ("spacy", "thinc", "kokoro", "misaki", "transformers", "torch", "sci2audio"):
    datas += copy_metadata(package)

EXCLUDES = ["tkinter", "matplotlib", "IPython", "pytest", "faster_whisper"]
# entry scripts point IMAGEIO_FFMPEG_EXE here (packaging/app.py, packaging/cli.py)
binaries.append((str(FFMPEG), "ffmpeg"))
datas.append((str(LICENSES), "licenses"))


def without_imageio_ffmpeg(toc):
    """imageio-ffmpeg's own FFmpeg is a GPL build with ~70 libraries whose source the
    installers could not offer (D-798): it never goes into the bundle."""
    return [entry for entry in toc if not Path(entry[0]).as_posix().startswith(DROPPED)]


DROPPED = "imageio_ffmpeg/binaries"
# torch's test programs and protobuf compiler: never run by sci2audio (53 MB, #635 F2);
# only torch_shm_manager stays, which torch looks for at import on Linux and macOS
TORCH_BIN = "torch/bin/"
TORCH_NEEDED = "torch/bin/torch_shm_manager"
TORCH_LIB = "torch/lib/"


def library_home(dest):
    """A folder a package loads its own libraries from: torch/lib, and the `<name>.libs`
    and `.dylibs` folders of wheels repaired by auditwheel, delvewheel or delocate."""
    parts = Path(dest).parts
    if Path(dest).as_posix().startswith(TORCH_LIB):
        return True
    return len(parts) > 1 and any(p.endswith(".libs") or p == ".dylibs" for p in parts[:-1])


def one_copy(toc, everything, top_level=not sys.platform.startswith("darwin")):
    """Each library once (#635 F2). The binary analysis also files the libraries of
    torch/lib and of numpy.libs (and other wheels' library folders) at the top of the
    folder, as real copies (about 475 MB of torch on Linux, 20 MB of OpenBLAS on Windows);
    each package finds them in its own folder (RUNPATH $ORIGIN on Linux, @loader_path on
    macOS, the DLL directory torch and delvewheel's patch add on Windows), so the
    top-level copies go. Not on macOS (`top_level` false): there PyInstaller points every
    binary's @rpath at the top of the folder, so the top-level copy is the one loaded.
    torch/bin goes everywhere, except torch_shm_manager."""
    nested = {os.path.realpath(source) for dest, source, kind in everything if library_home(dest)}
    kept = []
    for dest, source, kind in toc:
        name = Path(dest).as_posix()
        if name.startswith(TORCH_BIN) and name != TORCH_NEEDED:
            continue
        if top_level and len(Path(dest).parts) == 1 and os.path.realpath(source) in nested:
            continue
        kept.append((dest, source, kind))
    return kept


def analysis(script):
    found = Analysis(
        [str(ROOT / "packaging" / script)],
        pathex=[str(ROOT / "src")],
        binaries=binaries,
        datas=datas,
        hiddenimports=hidden + ["sci2audio.web.window"],
        excludes=EXCLUDES,
        noarchive=False,
    )
    everything = list(found.binaries) + list(found.datas)
    found.binaries = one_copy(without_imageio_ffmpeg(found.binaries), everything)
    found.datas = one_copy(without_imageio_ffmpeg(found.datas), everything)
    return found


app_a = analysis("app.py")
cli_a = analysis("cli.py")
icon = {
    "darwin": ICONS / "sci2audio.icns",
    "win32": ICONS / "sci2audio.ico",
}.get(sys.platform)
icon = [str(icon)] if icon is not None and icon.exists() else None

app_exe = EXE(
    PYZ(app_a.pure),
    app_a.scripts,
    [],
    exclude_binaries=True,
    name="sci2audio-app",
    console=sys.platform == "linux",  # a window on macOS and Windows
    icon=icon,
    codesign_identity=None,
    entitlements_file=None,
)
cli_exe = EXE(
    PYZ(cli_a.pure),
    cli_a.scripts,
    [],
    exclude_binaries=True,
    name="sci2audio",
    console=True,
    icon=icon,
)
folder = COLLECT(
    app_exe,
    cli_exe,
    app_a.binaries + cli_a.binaries,
    app_a.datas + cli_a.datas,
    name="sci2audio",
)
if sys.platform == "darwin":
    app = BUNDLE(
        folder,
        name="sci2audio.app",
        icon=icon[0] if icon else None,
        bundle_identifier="io.github.dubidu22.sci2audio",
        version=VERSION,
        info_plist={
            "CFBundleName": "sci2audio",
            "CFBundleDisplayName": "sci2audio",
            "CFBundleShortVersionString": VERSION,
            "CFBundleVersion": VERSION,
            "LSMinimumSystemVersion": "14.0",  # torch and onnxruntime wheels: macosx_14_0_arm64
            "NSHighResolutionCapable": True,
            "LSApplicationCategoryType": "public.app-category.education",
        },
    )
