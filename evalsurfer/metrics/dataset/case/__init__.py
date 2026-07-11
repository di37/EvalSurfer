"""The golden dataset case: one immutable, content-addressed evaluation item.

A :class:`DatasetCase` pairs an input with optional gold references (answer,
label, score) and coverage metadata (tags, held-out flag). Its identity is
content-derived: :func:`~evalsurfer.metrics.dataset.contamination.content_hash` hashes
the content fields, the id is a short prefix of that hash, and both are recomputed
from content -- never trusted from untrusted input -- so the same content always
yields the same id across versions and machines.

Everything here is pure and standard-library only. Cases are frozen; validation
is fail-fast at construction. Magic values come from :mod:`evalsurfer.constants`.

The implementation is split across two focused modules -- :mod:`.helpers` (the
fail-fast validators) and :mod:`.models` (the :class:`DatasetCase` value object)
-- and re-exported here so that ``from evalsurfer.metrics.dataset.case import
DatasetCase`` keeps working.
"""

from evalsurfer.metrics.dataset.case.models import DatasetCase

__all__ = ["DatasetCase"]
