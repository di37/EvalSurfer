"""Validate a built dataset against the EvalSurfer dataset schema.

Keeps ``dataset.schema.json`` in step with :class:`Dataset.to_dict`. Needs the
optional ``jsonschema`` dependency; it skips (rather than fails) when the package
is absent, so the zero-dependency core test run still passes.
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

from evalsurfer.dataset.case import DatasetCase
from evalsurfer.dataset.dataset import Dataset

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCHEMA_PATH = os.path.join(HERE, "spec", "dataset.schema.json")


def _load_schema() -> dict:
    with open(SCHEMA_PATH, encoding="utf-8") as file:
        return json.load(file)


def _sample_dataset() -> Dataset:
    return Dataset(
        name="golden",
        version="v1",
        cases=(
            DatasetCase.create("What is 2+2?", gold_answer="4", tags=("normal",)),
            DatasetCase.create(
                "Classify sentiment.", gold_label="positive", tags=("difficult", "edge")
            ),
            DatasetCase.create("Rate this.", gold_score=4.0, held_out=True),
        ),
    )


@unittest.skipUnless(jsonschema is not None, "jsonschema not installed")
class DatasetSchemaTest(unittest.TestCase):
    def setUp(self) -> None:
        self.schema = _load_schema()

    def test_schema_is_itself_valid(self) -> None:
        Draft202012Validator.check_schema(self.schema)

    def test_built_dataset_matches_schema(self) -> None:
        jsonschema.validate(_sample_dataset().to_dict(), self.schema)

    def test_from_traces_output_matches_schema(self) -> None:
        built = Dataset.from_traces(
            [{"query": "q1"}, {"prompt": "q2"}], name="d", version="v1"
        )
        jsonschema.validate(built.to_dict(), self.schema)


if __name__ == "__main__":
    unittest.main()
