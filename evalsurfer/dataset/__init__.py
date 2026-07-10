"""The golden dataset artifact: versioned cases with contamination controls.

Content-addressed :class:`DatasetCase` items collected into an immutable,
versioned :class:`Dataset` that supports deterministic splitting, content-hash
dedupe, version-to-version diffing, trace harvesting, coverage summaries, and
contamination reports -- all pure and standard-library only, with zero model
calls.
"""

from evalsurfer.dataset.case import DatasetCase
from evalsurfer.dataset.dataset import CHANGE_CHANGED, Dataset

__all__ = [
    "DatasetCase",
    "Dataset",
    "CHANGE_CHANGED",
]
