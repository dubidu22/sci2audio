"""Checks that plugins and built-in parts must pass, as plain functions (#6, Q11).

`check_text_step` is the conformance suite for text steps (D-57); `check_voice_engine` is
the one for voices (D-52, D-125); `make_document` builds small valid documents for tests;
`regression` loads and renders the English regression cases (#4). Tests wrap these
functions; nothing here imports pytest or Hypothesis, so they never become run-time
dependencies. Sits beside `sci2audio.app` in the layers: it may use the pipeline stages
and core, and nothing in the program imports it.
"""

from sci2audio.testing.documents import make_document, rebuilt_from_script
from sci2audio.testing.text_steps import (
    SAMPLE_DOCUMENTS,
    ConformanceError,
    NetworkUsedError,
    check_text_step,
    no_network,
    text_step_problems,
)
from sci2audio.testing.voices import check_voice_engine

__all__ = [
    "SAMPLE_DOCUMENTS",
    "ConformanceError",
    "NetworkUsedError",
    "check_text_step",
    "check_voice_engine",
    "make_document",
    "no_network",
    "rebuilt_from_script",
    "text_step_problems",
]
