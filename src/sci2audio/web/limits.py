"""Request size limits, checked before a body is read (D-198).

A request body must state its length (`Content-Length`); a chunked body without one gets
411, and a stated length over the limit gets 413 before a byte is read. The upload route
allows one opened file plus the multipart framing; every other route allows the pasted
text limit plus room for the JSON around it. The document store counts the bytes of the
file itself again while copying (`documents.py`).
"""

from __future__ import annotations

import json

from starlette.types import ASGIApp, Receive, Scope, Send

UPLOAD_PATH = "/api/v1/documents"
FRAMING = 1024 * 1024  # multipart boundaries and part headers
JSON_ROOM = 64 * 1024  # the JSON keys and quoting around pasted text


class BodyLimit:
    def __init__(self, app: ASGIApp, *, upload_limit: int, text_limit: int) -> None:
        self.app = app
        self.upload_limit = upload_limit + FRAMING
        self.other_limit = text_limit + JSON_ROOM

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = {
            name.decode("latin-1").lower(): value.decode("latin-1")
            for name, value in scope.get("headers", ())
        }
        limit = self.upload_limit if scope.get("path") == UPLOAD_PATH else self.other_limit
        length = headers.get("content-length")
        if length is None:
            if "transfer-encoding" in headers:
                await _refuse(send, 411, "length-required", "send the length of the request")
                return
        elif not length.isdigit() or int(length) > limit:
            if length.isdigit():
                message = f"the request is larger than {limit // (1024 * 1024)} MB"
                await _refuse(send, 413, "too-large", message)
            else:
                await _refuse(send, 400, "bad-request", "the request's length is not a number")
            return
        await self.app(scope, receive, send)


async def _refuse(send: Send, status: int, kind: str, message: str) -> None:
    body = json.dumps({"error": kind, "message": message}).encode()
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
                (b"connection", b"close"),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})
