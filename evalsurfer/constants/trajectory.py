"""Agent trajectory findings.

The finding types emitted when auditing an agent's tool-call trajectory.
Data only -- no behavior, no imports beyond typing helpers.
"""

from __future__ import annotations

from typing import Final

# --------------------------------------------------------------------------- #
# Agent trajectory findings
# --------------------------------------------------------------------------- #
TRAJECTORY_MISSING_TOOL: Final = "missing_tool"
TRAJECTORY_UNNECESSARY_TOOL: Final = "unnecessary_tool"
TRAJECTORY_OUT_OF_ORDER: Final = "out_of_order"
TRAJECTORY_BAD_PARAMETERS: Final = "bad_parameters"
TRAJECTORY_NO_RECOVERY: Final = "no_recovery"

__all__ = [
    "TRAJECTORY_MISSING_TOOL",
    "TRAJECTORY_UNNECESSARY_TOOL",
    "TRAJECTORY_OUT_OF_ORDER",
    "TRAJECTORY_BAD_PARAMETERS",
    "TRAJECTORY_NO_RECOVERY",
]
