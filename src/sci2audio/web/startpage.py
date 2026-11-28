"""The start page: the start link behind a file only the person can read (#117).

The browser is opened at this file, not at the start link: a link on the command line of
`open`, `xdg-open` or the browser process is there for every user of the computer to read
(`ps`), and the start-up token in it is the one thing between them and the server. The file
is in the person's runtime folder, readable by them alone (mode 0600 in a 0700 folder; on
Windows inside their profile), and sends the browser on to the start link. It goes once the
token has been traded for the cookie, or when the server stops. The terminal still prints
the link, for when no browser opens.
"""

from __future__ import annotations

import html
import os
import secrets
import threading
from pathlib import Path

import platformdirs


def default_folder() -> Path:
    """The person's runtime folder for sci2audio (`platformdirs`)."""
    return platformdirs.user_runtime_path("sci2audio", appauthor=False, ensure_exists=False)


class StartPage:
    """One server's start page; `write` makes it, `remove` takes it away again."""

    def __init__(self, folder: Path | None = None) -> None:
        self.folder = folder
        self.path: Path | None = None
        self._lock = threading.Lock()  # the server thread removes it as the launcher may

    def write(self, start_url: str) -> str:
        """Write the page for `start_url` and return its `file:` address. Raises OSError if
        the folder cannot be made or the file not written."""
        folder = self.folder or default_folder()
        folder.mkdir(mode=0o700, parents=True, exist_ok=True)
        if os.name == "posix":
            os.chmod(folder, 0o700)  # an older folder may have been made with more
        path = folder / f"start-{secrets.token_hex(8)}.html"
        link = html.escape(start_url, quote=True)
        page = (
            '<!doctype html>\n<html><head><meta charset="utf-8">'
            f'<meta http-equiv="refresh" content="0;url={link}">'
            f'<title>sci2audio</title></head><body><a href="{link}">sci2audio</a></body></html>\n'
        )
        # created for the owner alone, never over another file
        handle = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(handle, "wb") as stream:  # closed before a removal (Windows)
                stream.write(page.encode("utf-8"))
        except OSError:
            path.unlink(missing_ok=True)
            raise
        with self._lock:
            self.path = path
        return path.as_uri()

    def remove(self) -> None:
        """Take the page away; nothing happens if there is none or it is gone already."""
        with self._lock:
            path, self.path = self.path, None
        if path is not None:
            path.unlink(missing_ok=True)
