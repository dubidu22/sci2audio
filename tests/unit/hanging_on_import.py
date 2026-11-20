"""A plugin module whose import blocks until the test lets it go."""

from broken_text_plugins import HANG, AlphaStep

HANG.wait(5)

Step = AlphaStep
