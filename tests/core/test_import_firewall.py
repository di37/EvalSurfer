"""Enforce Core's one-way CIMAA dependency boundary."""

from __future__ import annotations

import ast
import unittest
from importlib.util import resolve_name
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "evalsurfer" / "core"
FORBIDDEN = (
    "evalsurfer.interface",
    "evalsurfer.metrics",
    "evalsurfer.analysis",
    "evalsurfer.assurance",
)


def _forbidden_imports(path: Path) -> list[tuple[int, str]]:
    """Return forbidden imports from executable syntax, ignoring docstrings."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    package = ".".join(path.relative_to(ROOT).with_suffix("").parts[:-1])
    violations: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            targets = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            relative_name = "." * node.level + (node.module or "")
            base = resolve_name(relative_name, package) if node.level else relative_name
            targets = [base]
            targets.extend(
                f"{base}.{alias.name}" for alias in node.names if alias.name != "*"
            )
        else:
            continue
        for name in targets:
            if any(
                name == prefix or name.startswith(f"{prefix}.") for prefix in FORBIDDEN
            ):
                violations.append((node.lineno, name))
    return violations


class CoreImportFirewallTest(unittest.TestCase):
    def test_core_does_not_import_outer_cimaa_layers(self) -> None:
        violations = {}
        for path in sorted(CORE.rglob("*.py")):
            imports = _forbidden_imports(path)
            if imports:
                violations[str(path.relative_to(ROOT))] = imports
        self.assertEqual(violations, {})


if __name__ == "__main__":
    unittest.main()
