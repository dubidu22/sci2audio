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
    found.binaries = without_imageio_ffmpeg(found.binaries)
    found.datas = without_imageio_ffmpeg(found.datas)
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
            "LSMinimumSystemVersion": "12.0",
            "NSHighResolutionCapable": True,
            "LSApplicationCategoryType": "public.app-category.education",
        },
    )
