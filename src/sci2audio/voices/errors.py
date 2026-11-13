# Copied from Abogen (https://github.com/denizsafak/abogen), file abogen/tts_plugin/errors.py,
# revision 1807822f5871d1c92740cb470c5c6e8328b8f851, under the MIT licence below (D-52).
# Changes for sci2audio: none, apart from this header and the module docstring.
#
# MIT License
#
# Copyright (c) 2025 Deniz Şafak
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
"""Error hierarchy of the voice plugin contract (D-52).

This module defines typed exceptions that engines raise.
Engines should never raise raw exceptions; they must use EngineError or its subtypes.
"""

from __future__ import annotations


class EngineError(Exception):
    """Base exception for all engine errors.

    All engine operations that can fail should raise EngineError or one of its subtypes.
    After dispose(), all methods except dispose() raise EngineError.
    """

    pass


class ModelNotFoundError(EngineError):
    """Raised when a required model is not found."""

    pass


class ModelLoadError(EngineError):
    """Raised when a model fails to load."""

    pass


class NetworkError(EngineError):
    """Raised when a network operation fails."""

    pass


class InvalidInputError(EngineError):
    """Raised when invalid input is provided to the engine."""

    pass


class ConfigurationError(EngineError):
    """Raised when there is a configuration error."""

    pass


class CancelledError(EngineError):
    """Raised when an operation is cancelled.

    This is raised by synthesize() when cancel() is called during synthesis.
    """

    pass


class InternalError(EngineError):
    """Raised when an internal engine error occurs."""

    pass
