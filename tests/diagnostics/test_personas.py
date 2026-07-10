from __future__ import annotations

import copy
import unittest

import evalsurfer.constants as constants
from evalsurfer.analysis.diagnostics.personas import PersonaAggregator


def _report(score: float | int | None) -> dict:
    """A minimal report carrying an explicit overall score."""

    return {"overall": {"score": score, "decision": "pass", "summary": ""}}


class PersonasConstantTest(unittest.TestCase):
    def test_reference_personas(self) -> None:
        self.assertEqual(
            PersonaAggregator.REFERENCE_PERSONAS, constants.DEFAULT_PERSONAS
        )
        self.assertEqual(
            PersonaAggregator.REFERENCE_PERSONAS,
            ("engineer", "lawyer", "doctor", "beginner", "ceo"),
        )


class AggregatePersonasHappyPathTest(unittest.TestCase):
    def test_aggregates_explicit_overall_scores(self) -> None:
        result = PersonaAggregator.aggregate(
            {
                "engineer": _report(8.5),
                "lawyer": _report(7.0),
                "doctor": _report(5.0),
            }
        )
        self.assertEqual(result["scores"], {"engineer": 8.5, "lawyer": 7.0, "doctor": 5.0})
        self.assertEqual(result["mean"], 6.8)  # mean(8.5, 7.0, 5.0) = 6.833 -> 6.8
        self.assertEqual(result["max"], {"persona": "engineer", "score": 8.5})
        self.assertEqual(result["min"], {"persona": "doctor", "score": 5.0})
        self.assertEqual(result["range"], 3.5)
        self.assertEqual(result["most_served"], "engineer")
        self.assertEqual(result["least_served"], "doctor")

    def test_score_rounded_to_one_decimal(self) -> None:
        result = PersonaAggregator.aggregate({"engineer": _report(8.46)})
        self.assertEqual(result["scores"]["engineer"], 8.5)

    def test_single_persona_has_zero_range(self) -> None:
        result = PersonaAggregator.aggregate({"ceo": _report(9.0)})
        self.assertEqual(result["range"], 0.0)
        self.assertEqual(result["min"], {"persona": "ceo", "score": 9.0})
        self.assertEqual(result["max"], {"persona": "ceo", "score": 9.0})
        self.assertEqual(result["most_served"], "ceo")
        self.assertEqual(result["least_served"], "ceo")

    def test_integer_scores_become_floats(self) -> None:
        result = PersonaAggregator.aggregate(
            {"engineer": _report(6), "lawyer": _report(8)}
        )
        self.assertEqual(result["scores"], {"engineer": 6.0, "lawyer": 8.0})
        self.assertEqual(result["mean"], 7.0)


class AggregatePersonasFallbackTest(unittest.TestCase):
    def test_recomputes_when_overall_score_missing(self) -> None:
        report = {
            "pillars": {
                "quality": {"criteria": [{"id": "a", "score": 4}, {"id": "b", "score": 2}]},
                "safety": {"criteria": [{"id": "c", "score": 5}]},
            }
        }  # quality 6.0, safety 10.0 -> overall 8.0
        result = PersonaAggregator.aggregate({"engineer": report})
        self.assertEqual(result["scores"]["engineer"], 8.0)
        self.assertEqual(result["mean"], 8.0)

    def test_recomputes_when_overall_score_is_none(self) -> None:
        report = {
            "overall": {"score": None},
            "pillars": {"quality": {"criteria": [{"id": "a", "score": 5}]}},
        }  # quality 10.0 -> overall 10.0
        result = PersonaAggregator.aggregate({"lawyer": report})
        self.assertEqual(result["scores"]["lawyer"], 10.0)


class AggregatePersonasNoneScoreTest(unittest.TestCase):
    def test_none_score_kept_but_excluded_from_aggregates(self) -> None:
        result = PersonaAggregator.aggregate(
            {
                "engineer": _report(8.0),
                "lawyer": {},  # no overall, no criteria -> None
                "doctor": _report(6.0),
            }
        )
        self.assertEqual(
            result["scores"], {"engineer": 8.0, "lawyer": None, "doctor": 6.0}
        )
        self.assertEqual(result["mean"], 7.0)  # None persona ignored
        self.assertEqual(result["max"], {"persona": "engineer", "score": 8.0})
        self.assertEqual(result["min"], {"persona": "doctor", "score": 6.0})
        self.assertEqual(result["most_served"], "engineer")
        self.assertEqual(result["least_served"], "doctor")

    def test_all_scores_none_yields_null_aggregates(self) -> None:
        result = PersonaAggregator.aggregate(
            {"engineer": {}, "lawyer": {"overall": {"score": None}}}
        )
        self.assertEqual(result["scores"], {"engineer": None, "lawyer": None})
        self.assertIsNone(result["mean"])
        self.assertIsNone(result["min"])
        self.assertIsNone(result["max"])
        self.assertIsNone(result["range"])
        self.assertIsNone(result["most_served"])
        self.assertIsNone(result["least_served"])


class AggregatePersonasEmptyTest(unittest.TestCase):
    def test_empty_reports(self) -> None:
        result = PersonaAggregator.aggregate({})
        self.assertEqual(result["scores"], {})
        self.assertIsNone(result["mean"])
        self.assertIsNone(result["min"])
        self.assertIsNone(result["max"])
        self.assertIsNone(result["range"])
        self.assertIsNone(result["most_served"])
        self.assertIsNone(result["least_served"])


class AggregatePersonasDeterminismTest(unittest.TestCase):
    def test_max_tie_breaks_to_alphabetically_first_persona(self) -> None:
        result = PersonaAggregator.aggregate(
            {
                "zoe": _report(9.0),
                "alice": _report(9.0),
                "bob": _report(5.0),
            }
        )
        self.assertEqual(result["most_served"], "alice")
        self.assertEqual(result["max"], {"persona": "alice", "score": 9.0})
        self.assertEqual(result["least_served"], "bob")

    def test_min_tie_breaks_to_alphabetically_first_persona(self) -> None:
        result = PersonaAggregator.aggregate(
            {
                "yara": _report(3.0),
                "amir": _report(3.0),
                "carol": _report(8.0),
            }
        )
        self.assertEqual(result["least_served"], "amir")
        self.assertEqual(result["min"], {"persona": "amir", "score": 3.0})
        self.assertEqual(result["most_served"], "carol")

    def test_result_independent_of_input_ordering(self) -> None:
        forward = PersonaAggregator.aggregate(
            {"engineer": _report(7.0), "lawyer": _report(9.0), "doctor": _report(4.0)}
        )
        reversed_ = PersonaAggregator.aggregate(
            {"doctor": _report(4.0), "lawyer": _report(9.0), "engineer": _report(7.0)}
        )
        self.assertEqual(forward["mean"], reversed_["mean"])
        self.assertEqual(forward["min"], reversed_["min"])
        self.assertEqual(forward["max"], reversed_["max"])
        self.assertEqual(forward["most_served"], reversed_["most_served"])
        self.assertEqual(forward["least_served"], reversed_["least_served"])


class AggregatePersonasValidationTest(unittest.TestCase):
    def test_reports_must_be_mapping(self) -> None:
        with self.assertRaises(TypeError):
            PersonaAggregator.aggregate([("engineer", _report(8.0))])  # type: ignore[arg-type]

    def test_persona_keys_must_be_strings(self) -> None:
        with self.assertRaises(TypeError):
            PersonaAggregator.aggregate({1: _report(8.0)})  # type: ignore[dict-item]

    def test_report_must_be_mapping(self) -> None:
        with self.assertRaises(TypeError):
            PersonaAggregator.aggregate({"engineer": [1, 2, 3]})  # type: ignore[dict-item]

    def test_non_numeric_score_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            PersonaAggregator.aggregate({"engineer": {"overall": {"score": "high"}}})

    def test_boolean_score_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            PersonaAggregator.aggregate({"engineer": {"overall": {"score": True}}})


class AggregatePersonasImmutabilityTest(unittest.TestCase):
    def test_inputs_are_not_mutated(self) -> None:
        reports = {"engineer": _report(8.0), "lawyer": {}}
        snapshot = copy.deepcopy(reports)
        PersonaAggregator.aggregate(reports)
        self.assertEqual(reports, snapshot)

    def test_scores_dict_is_a_new_object(self) -> None:
        reports = {"engineer": _report(8.0)}
        result = PersonaAggregator.aggregate(reports)
        self.assertIsNot(result["scores"], reports)


if __name__ == "__main__":
    unittest.main()
