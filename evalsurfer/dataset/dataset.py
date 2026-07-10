"""The versioned golden dataset: an immutable collection of cases.

A :class:`Dataset` is a named, versioned tuple of
:class:`~evalsurfer.dataset.case.DatasetCase` objects with the operations a
golden set needs: content-hash :meth:`~Dataset.dedupe`, a deterministic
(RNG-free) eval/held-out :meth:`~Dataset.split`, a version-to-version
:meth:`~Dataset.diff`, harvesting fresh cases from raw traces
(:meth:`~Dataset.from_traces`), a :meth:`~Dataset.coverage_summary`, and a
:meth:`~Dataset.contamination_report`. Every "mutating" operation returns a new
dataset; inputs are never mutated.

Everything is pure and standard-library only. Magic values come from
:mod:`evalsurfer.constants`; a few output-shape labels with no home in the
shared constants live here as module constants.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from hashlib import sha256
from typing import Any, Final, Iterable, Mapping, Sequence

import evalsurfer.constants as constants
from evalsurfer.dataset.case import DatasetCase
from evalsurfer.dataset.contamination import report as _contamination_report

__all__ = ["Dataset", "CHANGE_CHANGED"]

# Fourth diff bucket: a shared id whose content changed between versions. The
# constants module ships added / removed / unchanged, but no "changed" label.
CHANGE_CHANGED: Final = "changed"

# Deterministic split resolution: ids are hashed into this many buckets.
HELD_OUT_BUCKETS: Final = 10_000

# Trace fields tried, in order, when harvesting a case input from a raw trace.
TRACE_INPUT_KEYS: Final = ("query", "input", "prompt", "question")

# coverage_summary() meta keys (reported alongside one entry per coverage tag).
COVERAGE_TOTAL: Final = "total"
COVERAGE_HELD_OUT: Final = "held_out"
COVERAGE_EVAL: Final = "eval"
COVERAGE_UNIQUE_HASHES: Final = "unique_hashes"


def _held_out_flag(case_id: str, held_out_fraction: float, salt: str) -> bool:
    """Deterministically decide whether an id falls in the held-out split.

    The decision is a pure function of the (salted) id, so a split is fully
    reproducible with no random state: the same id and salt always land the same
    way, and raising the fraction can only move ids into the held-out set.

    Args:
        case_id: The case id being placed.
        held_out_fraction: The target held-out fraction in ``[0, 1]``.
        salt: A salt mixed into the hash so independent splits do not correlate.

    Returns:
        ``True`` when the id's hash bucket falls below the target fraction.
    """
    digest = sha256(f"{salt}{case_id}".encode("utf-8")).hexdigest()
    bucket = int(digest, 16) % HELD_OUT_BUCKETS
    return bucket / HELD_OUT_BUCKETS < held_out_fraction


def _extract_trace_input(trace: Any) -> str | None:
    """Extract the first usable input string from a raw trace mapping.

    Args:
        trace: A trace record; non-mappings yield ``None``.

    Returns:
        The first non-blank string among :data:`TRACE_INPUT_KEYS`, or ``None``
        when no usable input is present.
    """
    if not isinstance(trace, Mapping):
        return None
    for key in TRACE_INPUT_KEYS:
        value = trace.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


@dataclass(frozen=True)
class Dataset:
    """An immutable, named, versioned collection of golden cases."""

    name: str
    version: str
    cases: tuple[DatasetCase, ...]

    def __post_init__(self) -> None:
        """Validate dataset invariants and freeze ``cases`` to a tuple.

        Raises:
            TypeError: If ``cases`` contains a non-:class:`DatasetCase`.
            ValueError: If ``name`` or ``version`` is blank, or two cases share
                an id.
        """
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("dataset name must be a non-empty string")
        if not isinstance(self.version, str) or not self.version.strip():
            raise ValueError("dataset version must be a non-empty string")
        object.__setattr__(self, "cases", tuple(self.cases))
        for case in self.cases:
            if not isinstance(case, DatasetCase):
                raise TypeError("every case must be a DatasetCase")
        ids = [case.id for case in self.cases]
        if len(ids) != len(set(ids)):
            raise ValueError("case ids must be unique within a dataset")

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "Dataset":
        """Build a dataset from ``{"name", "version", "cases": [...]}``.

        Args:
            data: The dataset mapping. Each entry of ``cases`` is parsed with
                :meth:`DatasetCase.from_mapping`.

        Returns:
            The parsed :class:`Dataset`.

        Raises:
            TypeError: If ``data`` is not a mapping or ``cases`` is not a list.
            ValueError: If a required field is missing/blank or a case is
                invalid.
        """
        if not isinstance(data, Mapping):
            raise TypeError("dataset must be a mapping")
        raw_cases = data.get("cases", ())
        if isinstance(raw_cases, (str, bytes)) or not isinstance(raw_cases, Sequence):
            raise TypeError("cases must be a list")
        return cls(
            name=data.get("name"),
            version=data.get("version"),
            cases=tuple(DatasetCase.from_mapping(case) for case in raw_cases),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialise the dataset to a JSON-ready dict.

        Returns:
            A dict ``{"name", "version", "cases"}`` where ``cases`` is a list of
            :meth:`DatasetCase.to_dict` results.
        """
        return {
            "name": self.name,
            "version": self.version,
            "cases": [case.to_dict() for case in self.cases],
        }

    def add(self, case: DatasetCase) -> "Dataset":
        """Return a new dataset with ``case`` appended.

        Args:
            case: The case to add.

        Returns:
            A new :class:`Dataset`; the original is unchanged.

        Raises:
            TypeError: If ``case`` is not a :class:`DatasetCase`.
            ValueError: If ``case.id`` already exists in the dataset.
        """
        if not isinstance(case, DatasetCase):
            raise TypeError("case must be a DatasetCase")
        return Dataset(name=self.name, version=self.version, cases=self.cases + (case,))

    def dedupe(self) -> "Dataset":
        """Return a new dataset with content-hash duplicates removed.

        The first case seen for each content hash is kept; later cases carrying
        the same content (for example under a different explicit id) are dropped.

        Returns:
            A new deduplicated :class:`Dataset`; the original is unchanged.
        """
        seen: set[str] = set()
        kept: list[DatasetCase] = []
        for case in self.cases:
            if case.content_hash in seen:
                continue
            seen.add(case.content_hash)
            kept.append(case)
        return Dataset(name=self.name, version=self.version, cases=tuple(kept))

    def split(self, held_out_fraction: float, salt: str = "") -> "Dataset":
        """Return a new dataset with a deterministic held-out assignment.

        Each case's ``held_out`` flag is recomputed from a salted hash of its id
        (see :func:`_held_out_flag`) -- no random state -- so the same fraction
        and salt always produce the same partition.

        Args:
            held_out_fraction: The target held-out fraction in ``[0, 1]``.
            salt: A salt so independent splits do not correlate.

        Returns:
            A new :class:`Dataset` with updated flags; ids and content hashes are
            preserved. The original is unchanged.

        Raises:
            TypeError: If ``held_out_fraction`` is not a real number or ``salt``
                is not a string.
            ValueError: If ``held_out_fraction`` is outside ``[0, 1]``.
        """
        if isinstance(held_out_fraction, bool) or not isinstance(
            held_out_fraction, (int, float)
        ):
            raise TypeError("held_out_fraction must be a number")
        if not 0 <= held_out_fraction <= 1:
            raise ValueError("held_out_fraction must be between 0 and 1")
        if not isinstance(salt, str):
            raise TypeError("salt must be a string")
        new_cases = tuple(
            replace(case, held_out=_held_out_flag(case.id, held_out_fraction, salt))
            for case in self.cases
        )
        return Dataset(name=self.name, version=self.version, cases=new_cases)

    def eval_cases(self) -> tuple[DatasetCase, ...]:
        """Return the eval-visible cases (those not held out).

        Returns:
            The cases whose ``held_out`` flag is ``False``, in dataset order.
        """
        return tuple(case for case in self.cases if not case.held_out)

    def heldout_cases(self) -> tuple[DatasetCase, ...]:
        """Return the held-out cases.

        Returns:
            The cases whose ``held_out`` flag is ``True``, in dataset order.
        """
        return tuple(case for case in self.cases if case.held_out)

    def diff(self, other: "Dataset") -> dict[str, list[str]]:
        """Compare this dataset against ``other`` by case id and content.

        Treat ``self`` as the newer version and ``other`` as the older one: this
        is what lets a v1 and a v2 of the same set be reconciled.

        Args:
            other: The dataset to compare against (the older version).

        Returns:
            A dict with four sorted id lists keyed by
            :data:`~evalsurfer.constants.CHANGE_ADDED` (ids only in ``self``),
            :data:`~evalsurfer.constants.CHANGE_REMOVED` (ids only in ``other``),
            :data:`~evalsurfer.constants.CHANGE_UNCHANGED` (shared id, same
            content hash), and :data:`CHANGE_CHANGED` (shared id, different
            content hash).

        Raises:
            TypeError: If ``other`` is not a :class:`Dataset`.
        """
        if not isinstance(other, Dataset):
            raise TypeError("other must be a Dataset")
        self_by_id = {case.id: case for case in self.cases}
        other_by_id = {case.id: case for case in other.cases}
        self_ids = set(self_by_id)
        other_ids = set(other_by_id)
        common = self_ids & other_ids
        return {
            constants.CHANGE_ADDED: sorted(self_ids - other_ids),
            constants.CHANGE_REMOVED: sorted(other_ids - self_ids),
            constants.CHANGE_UNCHANGED: sorted(
                cid
                for cid in common
                if self_by_id[cid].content_hash == other_by_id[cid].content_hash
            ),
            CHANGE_CHANGED: sorted(
                cid
                for cid in common
                if self_by_id[cid].content_hash != other_by_id[cid].content_hash
            ),
        }

    @classmethod
    def from_traces(
        cls, traces: Iterable[Any], *, name: str, version: str
    ) -> "Dataset":
        """Harvest a fresh, deduplicated dataset from raw traces.

        Each trace contributes an input-only case tagged
        :data:`~evalsurfer.constants.TAG_RANDOM`. Because cases are
        content-addressed and deduplicated by content hash, overlapping trace
        batches yield stable, non-duplicated ids. Traces with no usable input
        are skipped.

        Args:
            traces: An iterable of trace mappings.
            name: The dataset name.
            version: The dataset version.

        Returns:
            The harvested :class:`Dataset`.

        Raises:
            ValueError: If ``name`` or ``version`` is blank.
        """
        seen: set[str] = set()
        cases: list[DatasetCase] = []
        for trace in traces:
            text = _extract_trace_input(trace)
            if text is None:
                continue
            case = DatasetCase.create(text, tags=(constants.TAG_RANDOM,))
            if case.content_hash in seen:
                continue
            seen.add(case.content_hash)
            cases.append(case)
        return cls(name=name, version=version, cases=tuple(cases))

    def coverage_summary(self) -> dict[str, int]:
        """Summarise coverage tags and split composition.

        Returns:
            A dict with one count per :data:`~evalsurfer.constants.COVERAGE_TAGS`
            entry (a case with several tags counts under each), plus
            :data:`COVERAGE_TOTAL`, :data:`COVERAGE_HELD_OUT`,
            :data:`COVERAGE_EVAL`, and :data:`COVERAGE_UNIQUE_HASHES`.
        """
        summary: dict[str, int] = {tag: 0 for tag in constants.COVERAGE_TAGS}
        for case in self.cases:
            for tag in case.tags:
                if tag in summary:
                    summary[tag] += 1
        held_out = sum(1 for case in self.cases if case.held_out)
        summary[COVERAGE_TOTAL] = len(self.cases)
        summary[COVERAGE_HELD_OUT] = held_out
        summary[COVERAGE_EVAL] = len(self.cases) - held_out
        summary[COVERAGE_UNIQUE_HASHES] = len(
            {case.content_hash for case in self.cases}
        )
        return summary

    def contamination_report(
        self, blocklist: Iterable[str] = (), canaries: Iterable[str] = ()
    ) -> dict[str, list]:
        """Run the contamination checks over this dataset's cases.

        Args:
            blocklist: Terms that must not appear (case-insensitive).
            canaries: Canary strings to detect leakage (exact match).

        Returns:
            The contamination report from
            :func:`evalsurfer.dataset.contamination.report`.
        """
        return _contamination_report(self.cases, blocklist, canaries)
