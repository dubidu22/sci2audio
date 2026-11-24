"""Smoke tests of an installed sci2audio (#13, #215, D-797): run by the installers workflow on
macOS, Windows and Linux after installing the installer as a person does.

    python scripts/installer_smoke.py cli PROGRAM VERSION --models FOLDER --work FOLDER [--offline]
    python scripts/installer_smoke.py window APP REPORT
    python scripts/installer_smoke.py browser APP REPORT
    python scripts/installer_smoke.py launch BUNDLE [--log FILE] [--timeout SECONDS]

`cli` checks the command line of the installed copy: its version, a listening script of a
corpus PDF and, with the voice files in FOLDER, a short English and a short German audiobook
(this is where a data file missing from the bundle shows). With --offline it first checks
that nothing outside the computer can be reached (the workflow runs it in a network
namespace without a network).

`window` starts the app with `--selftest`: the window opens on 127.0.0.1, the interface
loads, and the app writes what it saw to REPORT and quits (macOS, Windows).

`browser` starts the app where it has no window (Linux): a stand-in browser (this script,
named in BROWSER) gets the start link, opens the library, finds Quit, presses it and writes
REPORT; the app must then stop by itself.

`launch` starts the macOS bundle as Finder does, through Launch Services (`open -a`, no
program path, no arguments), waits for the app's start line "running in a window" in its
app.log (#716: 1.4.0's bundle started the command line, which quit at once), quits it with
the quit Apple Event as the Dock does, and checks that app.log then ends with "stopped"
(#717: such a quit ended the process before the app could say so).

Only the standard library: it runs on the runner's Python, outside the installed program.
"""

from __future__ import annotations

import argparse
import http.cookiejar
import json
import os
import plistlib
import re
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Sequence
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
PDF = ROOT / "tests" / "corpus" / "papers" / "joss2021-waskom-seaborn.pdf"
TEXTS = {
    "en": "# A short test\n\nThis is the installed sci2audio. It reads two sentences aloud.\n",
    "de": "# Ein kurzer Test\n\nDas ist das installierte sci2audio. Es liest zwei Sätze vor.\n",
}
LOCAL = re.compile(r"^http://127\.0\.0\.1:\d+$")
START_LINE = "running in a window"  # sci2audio.web.window.run_window
STOP_LINE = "INFO stopped"  # its last line, as "<time> INFO stopped"
MAC_LOG = Path.home() / "Library" / "Logs" / "sci2audio" / "app.log"


class Failed(Exception):
    pass


def check(condition: object, message: str) -> None:
    if not condition:
        raise Failed(message)


def say(text: str) -> None:
    print(f"installer_smoke: {text}", flush=True)


def call(program: Path, *args: str | Path, timeout: float = 900) -> str:
    command = [str(program), *(str(a) for a in args)]
    say("$ " + " ".join(command))
    done = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
    output = done.stdout + done.stderr
    print(output, flush=True)
    check(done.returncode == 0, f"{command[1:]} ended with {done.returncode}")
    return output


# ---- the files ----------------------------------------------------------------------------


def is_m4b(path: Path) -> bool:
    """An MPEG-4 file (ftyp box first) of more than 10 kB: a few seconds of AAC at least."""
    with path.open("rb") as file:
        head = file.read(12)
    return path.stat().st_size > 10_000 and head[4:8] == b"ftyp"


def is_mp3(path: Path) -> bool:
    with path.open("rb") as file:
        head = file.read(3)
    frame = len(head) >= 2 and head[0] == 0xFF and head[1] & 0xE0 == 0xE0
    return path.stat().st_size > 10_000 and (head == b"ID3" or frame)


def no_network() -> bool:
    """True when nothing outside this computer answers (no route, no name lookup)."""
    for host, port in (("1.1.1.1", 443), ("pypi.org", 443), ("huggingface.co", 443)):
        try:
            with socket.create_connection((host, port), timeout=5):
                return False
        except OSError:
            continue
    return True


# ---- cli ----------------------------------------------------------------------------------


def smoke_cli(program: Path, version: str, models: Path, work: Path, offline: bool) -> None:
    if offline:
        check(no_network(), "--offline, but the network can be reached")
        say("offline: no address outside this computer can be reached")
    work.mkdir(parents=True, exist_ok=True)
    shown = call(program, "--version").strip()
    check(shown == f"sci2audio {version}", f"version {shown!r}, expected {version}")

    out = work / "script"
    call(program, "script", PDF, "-o", out, "--work-folder", work / "w-script", "--ignore-settings")
    for suffix in ("script.txt", "report.json", "report.md"):
        made = out / f"{PDF.stem}.{suffix}"
        check(made.is_file() and made.stat().st_size > 0, f"{made.name} was not written")

    for language, text in TEXTS.items():
        source = work / f"{language}.md"
        source.write_text(text, encoding="utf-8")
        out = work / f"audio-{language}"
        call(
            program, "convert", source, "-o", out, "--work-folder", work / f"w-{language}",
            "--ignore-settings", "--models-folder", models, "--language", language, "-q",
        )  # fmt: skip
        m4b = out / f"{language}.m4b"
        check(m4b.is_file() and is_m4b(m4b), f"{m4b.name} is missing or holds no audio")
        mp3s = sorted(out.glob("*.mp3"))
        check(mp3s and all(is_mp3(p) for p in mp3s), f"no MP3 of the {language} text")
        say(f"{language}: {m4b.name} {m4b.stat().st_size} bytes, {len(mp3s)} MP3")
    say(f"the command line works{' offline' if offline else ''}: sci2audio {version}")


# ---- window -------------------------------------------------------------------------------


def window_problems(report: dict[str, Any]) -> list[str]:
    """What is wrong with the app's self-test report: empty when the window showed the
    library, served from 127.0.0.1."""
    problems = []
    page = report.get("page") or {}
    if report.get("launched_as") != "window":
        problems.append(f"launched as {report.get('launched_as')!r}, not in a window")
    origin = str(report.get("origin", ""))
    if not LOCAL.match(origin):
        problems.append(f"the server is at {origin!r}, not on 127.0.0.1")
    if page.get("host") != origin.removeprefix("http://"):
        problems.append(f"the window shows {page.get('host')!r}, not the app's server")
    if page.get("path") != "/":
        problems.append(f"the window shows {page.get('path')!r}, not the library")
    if "sci2audio" not in str(page.get("title", "")):
        problems.append(f"the page title is {page.get('title')!r}")
    if page.get("lang") not in ("en", "de"):
        problems.append(f"the page language is {page.get('lang')!r}")
    if page.get("rail") is not True:
        problems.append("the rail is not drawn")
    if "token" in json.dumps(report).lower():
        problems.append("the report names the start-up token")
    return problems


def smoke_window(app: Path, report: Path, timeout: float = 300) -> None:
    report.unlink(missing_ok=True)
    say(f"$ {app} --selftest {report}")
    done = subprocess.run([str(app), "--selftest", str(report)], timeout=timeout, check=False)
    check(report.is_file(), f"the app wrote no report (exit code {done.returncode})")
    found = json.loads(report.read_text(encoding="utf-8"))
    print(json.dumps(found, indent=2), flush=True)
    problems = window_problems(found)
    check(not problems, "; ".join(problems))
    check(done.returncode == 0, f"the app ended with {done.returncode}")
    say("the window opened the interface on 127.0.0.1")


# ---- launch -------------------------------------------------------------------------------


def log_size(log: Path) -> int:
    return log.stat().st_size if log.is_file() else 0


def new_lines(log: Path, offset: int) -> str:
    """What the log got after its first `offset` bytes, with "\\n" line ends."""
    if not log.is_file():
        return ""
    with log.open("rb") as file:
        file.seek(offset)
        return file.read().decode("utf-8", errors="replace").replace("\r\n", "\n")


def running(bundle: Path) -> bool:
    pattern = f"{bundle}/Contents/MacOS/"
    found = subprocess.run(
        ["/usr/bin/pgrep", "-f", pattern], stdout=subprocess.DEVNULL, check=False
    )
    return found.returncode == 0


def kill(bundle: Path) -> None:
    subprocess.run(["/usr/bin/pkill", "-f", f"{bundle}/Contents/MacOS/"], check=False)


def quit_app(bundle: Path, identifier: str, timeout: float, poll: float) -> str | None:
    """Quits the app as the Dock does; a problem when it is still running after `timeout`.
    Nothing is sent to an app that is not running: the Apple Event would start it."""
    if not running(bundle):
        return None
    quit_it = f'tell application id "{identifier}" to quit'
    try:
        subprocess.run(["/usr/bin/osascript", "-e", quit_it], timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        # an app that never answers the event is a failed quit, said as one, not a
        # traceback; it is ended so the steps after this one start clean
        kill(bundle)
        return f"the quit Apple Event got no answer within {timeout:.0f} s"
    deadline = time.monotonic() + timeout
    while running(bundle):
        if time.monotonic() > deadline:
            kill(bundle)
            return f"the app was still running {timeout:.0f} s after it was asked to quit"
        time.sleep(poll)
    return None


def ends_stopped(lines: str) -> bool:
    """True when the last line written is the app's "stopped" (#717)."""
    written = lines.rstrip("\n").splitlines()
    return bool(written) and written[-1].endswith(" " + STOP_LINE)


def smoke_launch(bundle: Path, log: Path, timeout: float = 30, poll: float = 0.5) -> None:
    info = plistlib.loads((bundle / "Contents" / "Info.plist").read_bytes())
    offset = log_size(log)  # the window self test writes the same line: only new ones count
    say(f"$ open -a {bundle}")
    try:
        opened = subprocess.run(["/usr/bin/open", "-a", str(bundle)], timeout=60, check=False)
    except subprocess.TimeoutExpired as error:
        raise Failed("open -a did not return within 60 s") from error
    deadline = time.monotonic() + timeout
    while START_LINE not in new_lines(log, offset) and time.monotonic() < deadline:
        time.sleep(poll)
    written = new_lines(log, offset)
    problem = quit_app(bundle, info["CFBundleIdentifier"], timeout, poll)
    check(opened.returncode == 0, f"open -a ended with {opened.returncode}")
    check(
        START_LINE in written,
        f"no start line ({START_LINE!r}) in {log} within {timeout:.0f} s of open -a;"
        f" new lines: {written.strip() or 'none'}",
    )
    check(problem is None, str(problem))
    written = new_lines(log, offset)
    check(
        ends_stopped(written),
        f"{log} does not end with the line 'stopped' after the quit Apple Event;"
        f" new lines: {written.strip() or 'none'}",
    )
    say("Launch Services started the app in a window; the quit Apple Event stopped it")


# ---- browser ------------------------------------------------------------------------------


def visit(start: str, report: Path) -> None:
    """The stand-in browser: open the start link, the library and Quit, as a person would."""
    found: dict[str, Any] = {"start": start.split("?")[0]}  # never the token
    try:
        origin = re.match(r"^(http://127\.0\.0\.1:\d+)/", start)
        check(origin, "the start link is not on 127.0.0.1")
        origin_text = origin.group(1)  # type: ignore[union-attr]
        jar = http.cookiejar.CookieJar()
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
        with opener.open(start, timeout=30) as answer:  # 303 to the library, with the cookie
            library = answer.read().decode("utf-8")
            found["library"] = answer.url.removeprefix(origin_text)
        found["quit_in_rail"] = 'id="quit"' in library
        with opener.open(f"{origin_text}/quit", timeout=30) as answer:
            found["quit_page"] = answer.status
        ask = urllib.request.Request(  # noqa: S310 - http://127.0.0.1 only, checked above
            f"{origin_text}/quit", method="POST", data=b"", headers={"Origin": origin_text}
        )
        with opener.open(ask, timeout=30) as answer:
            found["quit"] = answer.status
    except (OSError, Failed, urllib.error.URLError) as error:
        found["error"] = f"{type(error).__name__}: {error}"
    report.write_text(json.dumps(found, indent=2), encoding="utf-8")


def smoke_browser(app: Path, report: Path, timeout: float = 300) -> None:
    report.unlink(missing_ok=True)
    stand_in = f'"{sys.executable}" "{Path(__file__).resolve()}" stand-in "{report}" %s'
    env = {**os.environ, "BROWSER": stand_in}
    say(f"$ BROWSER=<stand-in> {app}")
    started = time.monotonic()
    done = subprocess.run([str(app)], env=env, timeout=timeout, check=False)
    check(report.is_file(), f"the stand-in browser was never opened (exit code {done.returncode})")
    found = json.loads(report.read_text(encoding="utf-8"))
    print(json.dumps(found, indent=2), flush=True)
    check("error" not in found, f"the stand-in browser failed: {found.get('error')}")
    check(found.get("library") == "/", f"the start link led to {found.get('library')!r}")
    check(found.get("quit_in_rail"), "the rail has no Quit item")
    check(found.get("quit") == 202, f"Quit answered {found.get('quit')}")
    check(done.returncode == 0, f"the app ended with {done.returncode} after Quit")
    say(f"the browser path works; Quit stopped the app after {time.monotonic() - started:.0f} s")


def stand_in(report: Path, url: str) -> None:
    """Named in BROWSER: returns at once (the server waits for its browser to start) and
    visits the link from a process of its own."""
    subprocess.Popen(
        [sys.executable, str(Path(__file__).resolve()), "visit", str(report), url],
        start_new_session=True,
    )


def record(path: Path, url: str) -> None:
    """Named in BROWSER for the Playwright step: writes the start link down for the tests
    and returns at once."""
    path.write_text(url, encoding="utf-8")


# ---- the program --------------------------------------------------------------------------


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="action", required=True)
    cli = sub.add_parser("cli")
    cli.add_argument("program", type=Path)
    cli.add_argument("version")
    cli.add_argument("--models", type=Path, required=True)
    cli.add_argument("--work", type=Path, required=True)
    cli.add_argument("--offline", action="store_true")
    for name in ("window", "browser"):
        part = sub.add_parser(name)
        part.add_argument("app", type=Path)
        part.add_argument("report", type=Path)
    launch = sub.add_parser("launch")
    launch.add_argument("bundle", type=Path)
    launch.add_argument("--log", type=Path, default=MAC_LOG)
    launch.add_argument("--timeout", type=float, default=30)
    helper = sub.add_parser("stand-in")
    helper.add_argument("report", type=Path)
    helper.add_argument("url")
    helper = sub.add_parser("record")
    helper.add_argument("report", type=Path)
    helper.add_argument("url")
    helper = sub.add_parser("visit")
    helper.add_argument("report", type=Path)
    helper.add_argument("url")
    args = parser.parse_args(argv)
    try:
        if args.action == "cli":
            smoke_cli(args.program, args.version, args.models, args.work, args.offline)
        elif args.action == "window":
            smoke_window(args.app, args.report)
        elif args.action == "browser":
            smoke_browser(args.app, args.report)
        elif args.action == "launch":
            smoke_launch(args.bundle, args.log, args.timeout)
        elif args.action == "stand-in":
            stand_in(args.report, args.url)
        elif args.action == "record":
            record(args.report, args.url)
        else:
            visit(args.url, args.report)
    except Failed as failure:
        say(f"FAILED: {failure}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
