from __future__ import annotations

import unittest

from evalsurfer.diagnostics.evidence import Evidence


class NormalizeEvidenceStringTest(unittest.TestCase):
    def test_plain_string_becomes_claim(self) -> None:
        self.assertEqual(Evidence.normalize("cited the SLA doc"), {"claim": "cited the SLA doc"})

    def test_empty_string_is_kept_as_claim(self) -> None:
        self.assertEqual(Evidence.normalize(""), {"claim": ""})

    def test_string_input_is_not_treated_as_confidence(self) -> None:
        # A bare string never has optional fields.
        self.assertEqual(Evidence.normalize("x"), {"claim": "x"})


class NormalizeEvidenceMappingTest(unittest.TestCase):
    def test_full_mapping_round_trips(self) -> None:
        result = Evidence.normalize(
            {
                "claim": "answer matches source",
                "supporting_context": "para 3 of the doc",
                "mismatch": "date is off by a year",
                "confidence": 0.8,
            }
        )
        self.assertEqual(
            result,
            {
                "claim": "answer matches source",
                "supporting_context": "para 3 of the doc",
                "mismatch": "date is off by a year",
                "confidence": 0.8,
            },
        )

    def test_empty_optional_fields_are_omitted(self) -> None:
        result = Evidence.normalize(
            {"claim": "c", "supporting_context": "", "mismatch": "", "confidence": None}
        )
        self.assertEqual(result, {"claim": "c"})

    def test_missing_keys_default_gracefully(self) -> None:
        self.assertEqual(Evidence.normalize({}), {"claim": ""})
        self.assertEqual(
            Evidence.normalize({"supporting_context": "ctx"}),
            {"claim": "", "supporting_context": "ctx"},
        )

    def test_confidence_zero_is_kept(self) -> None:
        # 0.0 is a real confidence, distinct from an omitted None.
        self.assertEqual(
            Evidence.normalize({"claim": "c", "confidence": 0.0}),
            {"claim": "c", "confidence": 0.0},
        )

    def test_confidence_one_is_kept(self) -> None:
        self.assertEqual(
            Evidence.normalize({"claim": "c", "confidence": 1}),
            {"claim": "c", "confidence": 1.0},
        )

    def test_confidence_is_rounded_to_three_decimals(self) -> None:
        result = Evidence.normalize({"claim": "c", "confidence": 0.123456})
        self.assertEqual(result["confidence"], 0.123)

    def test_unknown_keys_are_ignored(self) -> None:
        result = Evidence.normalize({"claim": "c", "severity": "major", "notes": "x"})
        self.assertEqual(result, {"claim": "c"})

    def test_input_mapping_is_not_mutated(self) -> None:
        original = {"claim": "c", "confidence": 0.5}
        snapshot = dict(original)
        Evidence.normalize(original)
        self.assertEqual(original, snapshot)


class NormalizeEvidenceValidationTest(unittest.TestCase):
    def test_confidence_out_of_range_raises(self) -> None:
        with self.assertRaises(ValueError):
            Evidence.normalize({"claim": "c", "confidence": 1.5})
        with self.assertRaises(ValueError):
            Evidence.normalize({"claim": "c", "confidence": -0.1})

    def test_confidence_nan_raises(self) -> None:
        with self.assertRaises(ValueError):
            Evidence.normalize({"claim": "c", "confidence": float("nan")})

    def test_confidence_bool_raises(self) -> None:
        # True/False must not be silently coerced to 1.0/0.0.
        with self.assertRaises(ValueError):
            Evidence.normalize({"claim": "c", "confidence": True})

    def test_confidence_string_raises(self) -> None:
        with self.assertRaises(ValueError):
            Evidence.normalize({"claim": "c", "confidence": "0.5"})

    def test_non_string_claim_raises(self) -> None:
        with self.assertRaises(ValueError):
            Evidence.normalize({"claim": 123})

    def test_non_string_text_field_raises(self) -> None:
        with self.assertRaises(ValueError):
            Evidence.normalize({"claim": "c", "supporting_context": ["a"]})

    def test_non_string_non_mapping_raises_type_error(self) -> None:
        for bad in (123, 4.5, None, ["a"], ("a",), True):
            with self.assertRaises(TypeError):
                Evidence.normalize(bad)


class EvidenceToDictTest(unittest.TestCase):
    def test_defaults_serialize_to_claim_only(self) -> None:
        self.assertEqual(Evidence.to_dict(Evidence(claim="c")), {"claim": "c"})

    def test_full_evidence_serializes_all_fields(self) -> None:
        ev = Evidence(
            claim="c",
            supporting_context="ctx",
            mismatch="m",
            confidence=0.6,
        )
        self.assertEqual(
            Evidence.to_dict(ev),
            {"claim": "c", "supporting_context": "ctx", "mismatch": "m", "confidence": 0.6},
        )

    def test_confidence_none_is_omitted(self) -> None:
        ev = Evidence(claim="c", confidence=None)
        self.assertNotIn("confidence", Evidence.to_dict(ev))

    def test_confidence_zero_is_included(self) -> None:
        ev = Evidence(claim="c", confidence=0.0)
        self.assertEqual(Evidence.to_dict(ev), {"claim": "c", "confidence": 0.0})

    def test_empty_text_fields_are_omitted(self) -> None:
        ev = Evidence(claim="c", supporting_context="", mismatch="ok")
        self.assertEqual(Evidence.to_dict(ev), {"claim": "c", "mismatch": "ok"})

    def test_result_matches_equivalent_mapping(self) -> None:
        ev = Evidence(claim="c", supporting_context="ctx", confidence=0.25)
        mapping_form = Evidence.normalize(
            {"claim": "c", "supporting_context": "ctx", "confidence": 0.25}
        )
        self.assertEqual(Evidence.to_dict(ev), mapping_form)

    def test_invalid_confidence_on_dataclass_raises(self) -> None:
        # The dataclass is frozen but does not type-check; serialization does.
        with self.assertRaises(ValueError):
            Evidence.to_dict(Evidence(claim="c", confidence=9.0))

    def test_non_evidence_argument_raises_type_error(self) -> None:
        with self.assertRaises(TypeError):
            Evidence.to_dict({"claim": "c"})  # type: ignore[arg-type]


class EvidenceDataclassTest(unittest.TestCase):
    def test_is_frozen_and_immutable(self) -> None:
        ev = Evidence(claim="c")
        with self.assertRaises(Exception):
            ev.claim = "other"  # type: ignore[misc]

    def test_defaults(self) -> None:
        ev = Evidence(claim="c")
        self.assertEqual(ev.supporting_context, "")
        self.assertEqual(ev.mismatch, "")
        self.assertIsNone(ev.confidence)


if __name__ == "__main__":
    unittest.main()
