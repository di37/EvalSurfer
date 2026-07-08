"""Validate the sample report against the EvalSurfer report schema.

Keeps ``examples/report.json`` and ``report.schema.json`` from drifting apart.
The test needs the optional ``jsonschema`` dependency; it skips (rather than
fails) when that package is not installed, so the zero-dependency core test run
still passes.
"""

from __future__ import annotations

import json
import os
import unittest

try:
    import jsonschema
    from jsonschema import Draft202012Validator
except ImportError:  # pragma: no cover - exercised only without the dev extra
    jsonschema = None

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA_PATH = os.path.join(HERE, "report.schema.json")
EXAMPLE_PATH = os.path.join(HERE, "examples", "report.json")


def load_json(path: str) -> dict:
    with open(path, encoding="utf-8") as file:
        return json.load(file)


@unittest.skipUnless(jsonschema is not None, "jsonschema not installed")
class ReportSchemaTest(unittest.TestCase):
    def setUp(self) -> None:
        self.schema = load_json(SCHEMA_PATH)

    def test_schema_is_itself_valid(self) -> None:
        # Raises SchemaError if the schema document is malformed.
        Draft202012Validator.check_schema(self.schema)

    def test_example_report_matches_schema(self) -> None:
        report = load_json(EXAMPLE_PATH)
        errors = sorted(
            Draft202012Validator(self.schema).iter_errors(report),
            key=lambda error: error.path,
        )
        messages = "\n".join(f"  - {error.message}" for error in errors)
        self.assertEqual(errors, [], f"example/report.json is invalid:\n{messages}")

    def test_invalid_report_is_rejected(self) -> None:
        # A report missing the required "pillars"/"decision"/"top_issues" keys
        # and with an out-of-range score must not validate.
        invalid = {"overall": {"score": 42, "decision": "excellent"}}
        with self.assertRaises(jsonschema.ValidationError):
            Draft202012Validator(self.schema).validate(invalid)


if __name__ == "__main__":
    unittest.main()
