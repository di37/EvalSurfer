"""Golden dataset tools — versioned cases and contamination controls."""

from __future__ import annotations

from evalsurfer.dataset.dataset import Dataset
from evalsurfer.mcp.instance import mcp


@mcp.tool()
def dataset_from_traces(traces: list[dict], name: str = "dataset", version: str = "v1") -> dict:
    """Harvest a versioned golden dataset from request traces (dedup by content hash)."""
    return Dataset.from_traces(traces, name=name, version=version).to_dict()


@mcp.tool()
def dataset_diff(before: dict, after: dict) -> dict:
    """Diff two dataset versions: added / removed / unchanged / changed case ids."""
    return Dataset.from_mapping(after).diff(Dataset.from_mapping(before))


@mcp.tool()
def dataset_contamination(
    dataset: dict, blocklist: list[str] | None = None, canaries: list[str] | None = None
) -> dict:
    """Contamination report: duplicate-content groups, blocklist hits, and canary hits."""
    return Dataset.from_mapping(dataset).contamination_report(
        blocklist=tuple(blocklist or ()), canaries=tuple(canaries or ())
    )


@mcp.tool()
def dataset_coverage(dataset: dict) -> dict:
    """Coverage summary: case counts per tag, held-out/eval split, and unique hashes."""
    return Dataset.from_mapping(dataset).coverage_summary()
