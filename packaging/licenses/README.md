# Licence texts the bundles carry for parts whose packages ship none

`scripts/build_installer.py` copies these into each bundle's `licenses/` folder (#635 F4);
`check_bundle` fails a bundle without them. Each file is the project's own text, unchanged:

| File | Part | Licence | Taken from |
|---|---|---|---|
| `espeakng-loader-LICENSE` | espeakng-loader 0.2.4 (every system) | MIT | https://github.com/thewh1teagle/espeakng-loader/blob/0ddc87adf77e5850d7eeb542ac8a87d421b64daa/LICENSE (the author added it on 2025-11-01, after the 0.2.4 release at 146599e, whose package names no licence) |
| `clr-loader-LICENSE` | clr-loader 0.3.1 (Windows, through pywebview) | MIT | https://github.com/pythonnet/clr-loader/blob/v0.3.1/LICENSE |
| `winpthreads-COPYING` | MinGW-w64 winpthreads, linked statically into the Windows `ffmpeg.exe` | MIT and BSD-3-Clause | https://github.com/mingw-w64/mingw-w64/blob/9720fc6261659c87c425f836b8b613d76eebac9b/mingw-w64-libraries/winpthreads/COPYING |
