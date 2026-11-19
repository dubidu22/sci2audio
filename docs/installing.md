# Installing sci2audio

sci2audio 1.4.0 comes as an installer for each system, with everything it needs inside: Python, sci2audio and an audio-only ffmpeg. Download the file for your system from the [release page](https://github.com/dubidu22/sci2audio/releases/latest).

| Your computer | File | Size |
|---|---|---|
| Mac with an Apple chip (M1 or newer), macOS 12 or newer | `sci2audio-1.4.0-macos-arm64.dmg` | about 385 MB |
| Windows 10 (version 1809 or newer) or Windows 11, 64-bit | `sci2audio-1.4.0-windows-x64-setup.exe` | about 340 MB |
| Linux, 64-bit (x86_64), glibc 2.35 or newer (Ubuntu 22.04, Debian 12, Fedora 36 and later) | `sci2audio-1.4.0-linux-x86_64.AppImage` | about 445 MB |

Intel Macs are not supported: PyTorch, which runs the voice, no longer publishes builds for them.

The installers are not signed with a paid certificate, so macOS and Windows warn the first time. The steps below get past that warning once. To check that a download is the file the release workflow built, see [Checking a download](#checking-a-download).

## macOS

1. Open the `.dmg` and drag **sci2audio** onto **Applications**.
2. Open sci2audio from Applications. macOS says it "cannot verify" the app; click **Done** (not "Move to Bin").
3. Open **System Settings → Privacy & Security**, scroll down to the line about sci2audio and click **Open Anyway**, then confirm with your password or Touch ID.
4. From then on sci2audio opens normally.

In Terminal instead of steps 2 and 3: `xattr -dr com.apple.quarantine /Applications/sci2audio.app`

sci2audio opens in a window of its own. Closing the window stops it; while an audiobook is being made, it asks first.

The command line is inside the app: `/Applications/sci2audio.app/Contents/MacOS/sci2audio --help`.

## Windows

1. Run `sci2audio-1.4.0-windows-x64-setup.exe`. If Windows says "Windows protected your PC", click **More info**, then **Run anyway**.
2. The installer needs no administrator rights: it installs sci2audio for you alone, in `%LOCALAPPDATA%\Programs\sci2audio`, and adds it to the Start menu.
3. Start **sci2audio** from the Start menu. It opens in a window of its own (Microsoft Edge WebView2, part of Windows 11 and current Windows 10). Where WebView2 is missing, sci2audio opens in your default browser instead, with a **Quit sci2audio** item in its menu.

The command line: `"%LOCALAPPDATA%\Programs\sci2audio\sci2audio.exe" --help`.

To remove it: **Settings → Apps → Installed apps → sci2audio → Uninstall**.

## Linux

1. Make the file executable: `chmod +x sci2audio-1.4.0-linux-x86_64.AppImage` (or tick "Allow executing file as program" in its properties).
2. Run it: `./sci2audio-1.4.0-linux-x86_64.AppImage`. It needs FUSE, which most desktops have. Without FUSE, run it with `--appimage-extract-and-run` as the first argument.

On Linux sci2audio opens in your default browser. The menu has **Quit sci2audio**; sci2audio also stops by itself after 15 minutes in which nothing asked for anything while no audiobook is being made.

With arguments, the same file is the command line: `./sci2audio-1.4.0-linux-x86_64.AppImage --help`.

## The voices: the one download

The first time you make an audiobook, sci2audio asks to download the voices: the Kokoro model with its English voices and a spaCy English model (about 355 MB, from huggingface.co and github.com), and the German voice Thorsten (about 330 MB, from huggingface.co). It lists every file with its size and licence and downloads only after you agree. You can fetch one language only. This is the only time sci2audio uses the internet, and only when you ask; everything else, the reading and the speaking, happens on your computer.

## Where your files are

| What | macOS | Windows | Linux |
|---|---|---|---|
| Audiobooks (unless you choose another folder) | `~/Documents/sci2audio` | `Documents\sci2audio` | `~/Documents/sci2audio` |
| Voice files, the library, speech caches | `~/Library/Application Support/sci2audio` | `%LOCALAPPDATA%\sci2audio` | `~/.local/share/sci2audio` |
| Settings | `~/Library/Application Support/sci2audio` | `%APPDATA%\sci2audio` | `~/.config/sci2audio` |
| The app's start-up log | `~/Library/Logs/sci2audio/app.log` | `%LOCALAPPDATA%\sci2audio\Logs\app.log` | `~/.local/state/sci2audio/log/app.log` |
| Temporary job files | `~/Library/Caches/sci2audio` | `%LOCALAPPDATA%\sci2audio\Cache` | `~/.cache/sci2audio` |

The privacy page in sci2audio lists the folders on your computer. Uninstalling removes the program only and keeps all of these; delete the folders by hand to remove them too.

The start-up log holds when the app started and stopped, its version, whether it opened a window or the browser, and why it could not start. It holds no file names, no text and no requests. Attach it to a tester report if sci2audio does not start.

## Checking a download

Each release lists `SHA256SUMS.txt`. Compare the file's checksum with the line for it:

- macOS and Linux: `shasum -a 256 <file>` (or `sha256sum <file>`)
- Windows (PowerShell): `Get-FileHash <file>`

With the GitHub command line you can also check that the release workflow built the file from this repository: `gh attestation verify <file> --repo dubidu22/sci2audio`.

## The source

sci2audio is free software under the GNU General Public License, version 3 or later. Each installer has a `licenses` folder with the licence of every part. The release page holds the complete source: `sci2audio-1.4.0.tar.gz`, and `sci2audio-1.4.0-sources.tar` with FFmpeg, LAME and espeak-ng and the script that builds the bundled ffmpeg.

## With uv instead

For the command line on its own, or to follow development, install sci2audio with [uv](https://docs.astral.sh/uv/) as the README describes. That install and an installer can live side by side; they share the voice files, the library and the settings.

## Feedback

Tell us what worked and what did not: [open a tester report](https://github.com/dubidu22/sci2audio/issues/new?template=tester-report.yml). Say which installer and system you used, and attach the start-up log if sci2audio did not start.
