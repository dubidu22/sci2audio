"""Local-only security: the start-up token, Host and Origin checks, response headers.

One pure ASGI middleware, the outermost layer of the app, so it covers every route,
static files, error pages and the OpenAPI document (D-193, D-194). The attacks it stops
are other web pages in the same browser: cross-site requests, DNS rebinding, and a page
of another program on 127.0.0.1 at a different port (the same *site*, so `SameSite`
cookies alone do not stop it, but a different *origin*).

Order of checks for every HTTP request:

1. `Host` must be `127.0.0.1:<port>` or `localhost:<port>`, else 421 (DNS rebinding).
2. `Origin`, when present, must be the server's own, else 403.
3. `Sec-Fetch-Site`, when present, must be `same-origin` or `none`, else 403; but for
   `/start`, `cross-site` too: the start page on disk (#117) comes from a `file:` page,
   which every browser sends as cross-site, and the token is the check there.
4. `/start?token=…` trades the token for the cookie and redirects to `/`. From the start
   page it answers with a page that goes on to `/` itself: after a redirect the request
   would stay cross-site, and the browser would not send the Strict cookie with it.
5. Every other path needs the token: the cookie or `Authorization: Bearer <token>`,
   else 401. A cookie-authenticated request that is not GET or HEAD must carry a
   matching `Origin` (browsers always send one there), else 403.

There is no CORS: no response ever carries Access-Control headers, so the browser keeps
other origins from reading anything.
"""

from __future__ import annotations

import html
import json
import secrets
from collections.abc import Callable, Iterable
from urllib.parse import parse_qs

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from sci2audio.web.config import ServerConfig
from sci2audio.web.i18n import COOKIE, language_from, strings

SAFE_METHODS = frozenset({"GET", "HEAD"})
# what `/start` answers the start page with: on to "/" from the server's own page (#117)
_STEP_PAGE = (
    b'<!doctype html>\n<html><head><meta charset="utf-8">'
    b'<meta http-equiv="refresh" content="0;url=/"><title>sci2audio</title></head>'
    b'<body><a href="/">sci2audio</a></body></html>\n'
)
FETCH_SITES = frozenset({"same-origin", "none"})

CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
    "media-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; "
    "form-action 'self'"
)
# Every feature the interface does not use is off (#172, ZAP 10063); playing audio stays,
# and the player starts the next chapter by itself. Copy on the Captures page writes to
# the clipboard (#1048); nothing reads it. Only names Chromium knows, so the browser logs
# no "unrecognized feature".
_OWN = frozenset({"autoplay", "clipboard-write"})
PERMISSIONS_POLICY = ", ".join(
    f"{feature}=(self)" if feature in _OWN else f"{feature}=()"
    for feature in (
        "accelerometer",
        "autoplay",
        "camera",
        "clipboard-read",
        "clipboard-write",
        "display-capture",
        "encrypted-media",
        "fullscreen",
        "geolocation",
        "gyroscope",
        "magnetometer",
        "microphone",
        "midi",
        "payment",
        "picture-in-picture",
        "publickey-credentials-get",
        "screen-wake-lock",
        "serial",
        "sync-xhr",
        "usb",
        "xr-spatial-tracking",
    )
)
SECURITY_HEADERS: tuple[tuple[bytes, bytes], ...] = (
    (b"content-security-policy", CSP.encode()),
    (b"x-content-type-options", b"nosniff"),
    (b"referrer-policy", b"no-referrer"),
    (b"x-frame-options", b"DENY"),
    (b"cache-control", b"no-store"),
    (b"cross-origin-opener-policy", b"same-origin"),
    (b"cross-origin-resource-policy", b"same-origin"),
    # every resource is the server's own or a data: image, so none needs CORP (ZAP 90004)
    (b"cross-origin-embedder-policy", b"require-corp"),
    (b"permissions-policy", PERMISSIONS_POLICY.encode()),
)
_REPLACED = frozenset(name for name, _ in SECURITY_HEADERS)


def _headers(scope: Scope) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for name, value in scope.get("headers", ()):
        found.setdefault(name.decode("latin-1").lower(), []).append(value.decode("latin-1"))
    return found


def _one(headers: dict[str, list[str]], name: str) -> str | None:
    """The header's value; None when missing. Sent twice counts as wrong ("" never matches)."""
    values = headers.get(name)
    if not values:
        return None
    return values[0] if len(values) == 1 else ""


def _cookies(headers: dict[str, list[str]], name: str) -> list[str]:
    """Every value of the cookie `name`. Cookies ignore ports, so a page on another local
    port can set a second one with that name (sent first when its path is longer): the
    real one must still count."""
    found: list[str] = []
    for header in headers.get("cookie", ()):
        for part in header.split(";"):
            key, _, value = part.strip().partition("=")
            if key == name:
                found.append(value)
    return found


def _same(given: str | None, token: str) -> bool:
    if given is None:
        return False
    return secrets.compare_digest(given.encode("utf-8", "replace"), token.encode())


class LocalOnly:
    """The middleware; `config` gives the port, the token and the cookie name, and
    `on_start` is called once the token has been traded for the cookie (the start page
    goes then, #117)."""

    def __init__(
        self, app: ASGIApp, config: ServerConfig, on_start: Callable[[], None] = lambda: None
    ) -> None:
        self.app = app
        self.config = config
        self.on_start = on_start

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "websocket":  # the server has none; never accept one
            await send({"type": "websocket.close", "code": 1008})
            return
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        refusal = self._refusal(scope)
        if refusal is not None:
            await refusal(scope, receive, self._with_headers(send))
            return
        await self.app(scope, receive, self._with_headers(send))

    def _with_headers(self, send: Send) -> Send:
        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                kept = [
                    (name, value)
                    for name, value in message.get("headers", ())
                    if name.lower() not in _REPLACED
                ]
                message = {**message, "headers": [*kept, *SECURITY_HEADERS]}
            await send(message)

        return send_with_headers

    def _refusal(self, scope: Scope) -> ASGIApp | None:
        headers = _headers(scope)
        config = self.config
        if _one(headers, "host") not in config.hosts:
            return _error(421, "wrong-host", "this server answers only on 127.0.0.1")
        origin = _one(headers, "origin")
        if origin is not None and origin not in config.origins:
            return _error(403, "wrong-origin", "requests from other pages are refused")
        site = _one(headers, "sec-fetch-site")
        path = scope.get("path", "")
        from_start_page = path == "/start" and site == "cross-site"
        if site is not None and site not in FETCH_SITES and not from_start_page:
            return _error(403, "wrong-origin", "requests from other pages are refused")
        method = scope.get("method", "GET")
        if path == "/start":
            return self._start(scope, method, step=from_start_page)
        authorization = _one(headers, "authorization") or ""
        scheme, _, bearer = authorization.partition(" ")
        if scheme.lower() == "bearer" and _same(bearer.strip(), config.token):
            return None
        if any(_same(value, config.token) for value in _cookies(headers, config.cookie_name)):
            if method not in SAFE_METHODS and origin is None:
                return _error(403, "wrong-origin", "requests from other pages are refused")
            return None
        return _unauthorised(path, headers)

    def _start(self, scope: Scope, method: str, *, step: bool = False) -> ASGIApp:
        if method not in SAFE_METHODS:
            return _error(405, "method-not-allowed", "open the link shown in the terminal")
        query = parse_qs(scope.get("query_string", b"").decode("latin-1"))
        tokens = query.get("token", [])
        if len(tokens) != 1 or not _same(tokens[0], self.config.token):
            return _unauthorised("/start", _headers(scope))
        self.on_start()
        cookie = f"{self.config.cookie_name}={self.config.token}; HttpOnly; SameSite=Strict; Path=/"
        if step:
            return _respond(200, _STEP_PAGE, "text/html; charset=utf-8", [("set-cookie", cookie)])
        return _respond(
            303, b"", "text/plain; charset=utf-8", [("location", "/"), ("set-cookie", cookie)]
        )


def _respond(
    status: int, body: bytes, content_type: str, extra: Iterable[tuple[str, str]] = ()
) -> ASGIApp:
    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        headers = [
            (b"content-type", content_type.encode()),
            (b"content-length", str(len(body)).encode()),
            *((name.encode(), value.encode("latin-1")) for name, value in extra),
        ]
        await send({"type": "http.response.start", "status": status, "headers": headers})
        await send({"type": "http.response.body", "body": body})

    return app


def _error(status: int, kind: str, message: str) -> ASGIApp:
    body = json.dumps({"error": kind, "message": message}).encode()
    return _respond(status, body, "application/json")


def _unauthorised(path: str, headers: dict[str, list[str]]) -> ASGIApp:
    """401: for programs the API's error in the app's words; for a browser a page in its
    language (the switch's cookie, else `Accept-Language`; D-288), from the table."""
    message = "open the link sci2audio showed in the terminal when it started"
    if path.startswith("/api/") or path == "/openapi.json":
        return _error(401, "no-token", message)
    s = strings(language_from(_cookies(headers, COOKIE), _one(headers, "accept-language")))
    page = (
        f'<!doctype html><html lang="{s.language}"><head><meta charset="utf-8">'
        f"<title>{html.escape(s('common.app'))}</title></head><body><main>"
        f"<h1>{html.escape(s('common.app'))}</h1>"
        f"<p>{html.escape(s('error.no-token'))}</p></main></body></html>"
    )
    return _respond(401, page.encode(), "text/html; charset=utf-8")
