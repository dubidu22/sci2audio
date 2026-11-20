"""A plugin module whose import raises a BaseException subclass."""

from broken_text_plugins import Boom

raise Boom("at import")
