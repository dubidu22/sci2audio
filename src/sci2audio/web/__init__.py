"""Web: the local server and its pages (D-45, D-101).

`create_app(config)` makes the FastAPI app of one server run; `run()` is `sci2audio ui`:
it binds 127.0.0.1 on a port the system picks, prints the start link and opens the
browser. Only this package imports the web framework (D-205); it never imports
`sci2audio.testing` (D-114).
"""

from sci2audio.web.config import ServerConfig, new_token, server_config
from sci2audio.web.launch import bind, run, serve
from sci2audio.web.server import create_app

__all__ = ["ServerConfig", "bind", "create_app", "new_token", "run", "serve", "server_config"]
