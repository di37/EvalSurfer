"""Framework metadata.

The framework name and version string.
Data only -- no behavior, no imports beyond typing helpers.
"""

from __future__ import annotations

from typing import Final

# --------------------------------------------------------------------------- #
# Framework metadata
# --------------------------------------------------------------------------- #
FRAMEWORK_NAME: Final = "EvalSurfer"
FRAMEWORK_VERSION: Final = "0.1.3"

__all__ = [
    "FRAMEWORK_NAME",
    "FRAMEWORK_VERSION",
]
