"""A plugin module whose import raises a BaseException subclass (review S1 of #676)."""

from broken_text_plugins import Boom

raise Boom("at import")
