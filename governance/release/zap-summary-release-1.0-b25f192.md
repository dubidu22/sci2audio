**Passed.** 2026-11-14 01:29 UTC, image `ghcr.io/zaproxy/zaproxy@sha256:9624669db72f54d86c4b46a7064518bd9bf79d8c61a4c31befa9923489f328af`, 270 requests seen through ZAP, server 127.0.0.1 (#12, D-364 to D-372).

## Failing

None.

## Accepted (Low)

None.

## Informational (never fails)

| Risk | Rule | Where | Note |
|---|---|---|---|
| Informational | 10024 Information Disclosure - Sensitive Information in URL | GET `/start?token=<token>` (token) | D-193: The start link carries the start-up token once: /start trades it for the HttpOnly, SameSite=Strict cookie and redirects to / without it, and Referrer-Policy: no-referrer keeps it out of every Referer. Taking it off the browser's command line is #117. |
| Informational | 10027 Information Disclosure - Suspicious Comments | GET `/static/app.js` | D-367: Ordinary code comments in app.js and player.js that contain words like 'address' or 'where'; they name no secret, host, user or bug. |
| Informational | 10027 Information Disclosure - Suspicious Comments | GET `/static/player.js` | D-367: Ordinary code comments in app.js and player.js that contain words like 'address' or 'where'; they name no secret, host, user or bug. |
| Informational | 10027 Information Disclosure - Suspicious Comments | GET `/static/player.js` | D-367: Ordinary code comments in app.js and player.js that contain words like 'address' or 'where'; they name no secret, host, user or bug. |
| Informational | 10029 Cookie Poisoning | GET `/language?back=%2Fprivacy&language=de` (language) | D-288: The language cookie is only ever 'en' or 'de' (known_language(), never the request's text), and the start cookie only ever holds the server's own token after a constant-time compare; no parameter can put its own text into a cookie. |
| Informational | 10029 Cookie Poisoning | GET `/language?back=https%3A%2F%2Fzap.example.com&language=en` (language) | D-288: The language cookie is only ever 'en' or 'de' (known_language(), never the request's text), and the start cookie only ever holds the server's own token after a constant-time compare; no parameter can put its own text into a cookie. |
| Informational | 10029 Cookie Poisoning | GET `/language?language=en&back=https://elsewhere.example/` (language) | D-288: The language cookie is only ever 'en' or 'de' (known_language(), never the request's text), and the start cookie only ever holds the server's own token after a constant-time compare; no parameter can put its own text into a cookie. |
| Informational | 10029 Cookie Poisoning | GET `/start?token=<token>` (token) | D-288: The language cookie is only ever 'en' or 'de' (known_language(), never the request's text), and the start cookie only ever holds the server's own token after a constant-time compare; no parameter can put its own text into a cookie. |
| Informational | 10031 User Controllable HTML Element Attribute (Potential XSS) | GET `/documents/24fae20ec9fdf62b?category=page-furniture&chapter=0` (category) | D-194: The document page echoes the preview form's query values into attributes; Jinja2 autoescaping escapes them and the CSP (script-src 'self', no inline script) would stop a script even if one got through. |
| Informational | 10031 User Controllable HTML Element Attribute (Potential XSS) | GET `/documents/24fae20ec9fdf62b?category=page-furniture&chapter=0&text=This+is+how+this+voice+reads+your+text.+The+results+in+the+second+table+were+measured+over+three+years.` (category) | D-194: The document page echoes the preview form's query values into attributes; Jinja2 autoescaping escapes them and the CSP (script-src 'self', no inline script) would stop a script even if one got through. |
| Informational | 10031 User Controllable HTML Element Attribute (Potential XSS) | GET `/documents/67aa0e72ab3f2f0d?category=page-furniture&chapter=0` (category) | D-194: The document page echoes the preview form's query values into attributes; Jinja2 autoescaping escapes them and the CSP (script-src 'self', no inline script) would stop a script even if one got through. |
| Informational | 10031 User Controllable HTML Element Attribute (Potential XSS) | GET `/documents/67aa0e72ab3f2f0d?category=page-furniture&chapter=0&text=This+is+how+this+voice+reads+your+text.+The+results+in+the+second+table+were+measured+over+three+years.` (category) | D-194: The document page echoes the preview form's query values into attributes; Jinja2 autoescaping escapes them and the CSP (script-src 'self', no inline script) would stop a script even if one got through. |
| Informational | 10112 Session Management Response Identified | GET `/start?token=<token>` (sci2audio-39407) | D-193: ZAP noting that /start sets the session cookie: that is the start-up token's cookie, HttpOnly and SameSite=Strict, named after the port. |

