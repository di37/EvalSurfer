"""Keep the two framework specs and executable safety probes in lockstep."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

try:
    import yaml  # pyright: ignore[reportMissingModuleSource]
except ImportError:  # pragma: no cover - exercised without the dev extra
    yaml = None

from evalsurfer.assurance.safety.redteam import RedTeam

ROOT = Path(__file__).resolve().parents[2]
JSON_PATH = ROOT / "spec" / "framework.json"
YAML_PATH = ROOT / "spec" / "framework.yaml"


def _load_json() -> dict:
    return json.loads(JSON_PATH.read_text(encoding="utf-8"))


def _load_yaml() -> dict:
    if yaml is None:  # pragma: no cover - guarded by skipUnless
        raise RuntimeError("PyYAML is not installed")
    return yaml.safe_load(YAML_PATH.read_text(encoding="utf-8"))


def _executable_cases() -> list[dict[str, str]]:
    return [
        {
            "id": case.id,
            "prompt": case.prompt,
            "expected_behavior": case.expected_behavior,
        }
        for case in RedTeam.CASES
    ]


class FrameworkConsistencyTest(unittest.TestCase):
    def test_json_red_team_cases_match_executable_cases(self) -> None:
        cases = _load_json()["eval_surfer"]["safety_red_team_cases"]
        self.assertEqual(cases, _executable_cases())

    @unittest.skipUnless(yaml is not None, "PyYAML not installed")
    def test_json_and_yaml_are_semantically_identical(self) -> None:
        self.assertEqual(_load_json(), _load_yaml())

    @unittest.skipUnless(yaml is not None, "PyYAML not installed")
    def test_yaml_red_team_cases_match_executable_cases(self) -> None:
        cases = _load_yaml()["eval_surfer"]["safety_red_team_cases"]
        self.assertEqual(cases, _executable_cases())


if __name__ == "__main__":
    unittest.main()
