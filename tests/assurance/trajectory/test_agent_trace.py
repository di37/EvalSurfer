from __future__ import annotations

import copy
import unittest

import evalsurfer.constants as constants
from evalsurfer.assurance.trajectory.agent_trace import (
    Finding,
    ToolCall,
    TrajectoryEvaluator,
)


def _types(result: dict) -> list[str]:
    """Return the finding types of a result, in order."""

    return [finding["type"] for finding in result["findings"]]


def _by_type(result: dict, finding_type: str) -> dict:
    """Return the single finding of ``finding_type`` in a result."""

    matches = [f for f in result["findings"] if f["type"] == finding_type]
    if len(matches) != 1:
        raise AssertionError(f"expected exactly one {finding_type} finding, got {matches}")
    return matches[0]


class EvaluateHappyPathTest(unittest.TestCase):
    def test_fully_compliant_trajectory_has_no_findings(self) -> None:
        actual = {
            "tool_calls": [
                {"name": "search", "arguments": {"query": "cats"}},
                {"name": "read", "arguments": {"id": "1"}},
            ],
            "final_answer": "Cats are mammals.",
        }
        expected = {
            "tool_sequence": ["search", "read"],
            "required_tools": ["search"],
            "forbidden_tools": ["delete"],
            "tool_parameters": {"search": {"required": ["query"]}},
        }
        result = TrajectoryEvaluator.evaluate(actual, expected)
        self.assertEqual(result["findings"], [])
        self.assertIsNone(result["recovered_after_error"])
        self.assertEqual(result["final_answer_consistency"], {"needs_judgment": True})

    def test_final_answer_consistency_always_deferred(self) -> None:
        # No answer, no tools -- consistency is still flagged for judgment.
        result = TrajectoryEvaluator.evaluate({}, {})
        self.assertEqual(result["final_answer_consistency"], {"needs_judgment": True})

    def test_result_has_exactly_the_three_top_level_keys(self) -> None:
        result = TrajectoryEvaluator.evaluate({}, {})
        self.assertEqual(
            set(result), {"findings", "recovered_after_error", "final_answer_consistency"}
        )


class MissingToolTest(unittest.TestCase):
    def test_required_tool_absent_is_missing(self) -> None:
        result = TrajectoryEvaluator.evaluate(
            {"tool_calls": [{"name": "read"}]},
            {"required_tools": ["search", "read"]},
        )
        finding = _by_type(result, constants.TRAJECTORY_MISSING_TOOL)
        self.assertEqual(finding["tools"], ["search"])
        self.assertIn("search", finding["detail"])

    def test_sequenced_tool_absent_is_missing(self) -> None:
        result = TrajectoryEvaluator.evaluate(
            {"tool_calls": [{"name": "a"}, {"name": "c"}]},
            {"tool_sequence": ["a", "b", "c"]},
        )
        self.assertEqual(
            _by_type(result, constants.TRAJECTORY_MISSING_TOOL)["tools"], ["b"]
        )

    def test_sequence_then_required_order_and_dedup(self) -> None:
        result = TrajectoryEvaluator.evaluate(
            {"tool_calls": []},
            {"tool_sequence": ["b", "a"], "required_tools": ["a", "c"]},
        )
        # sequence order first (b, a), then new required tools (c); a not repeated.
        self.assertEqual(
            _by_type(result, constants.TRAJECTORY_MISSING_TOOL)["tools"], ["b", "a", "c"]
        )

    def test_present_required_tool_is_not_missing(self) -> None:
        result = TrajectoryEvaluator.evaluate(
            {"tool_calls": [{"name": "search"}]},
            {"required_tools": ["search"]},
        )
        self.assertEqual(result["findings"], [])


class UnnecessaryToolTest(unittest.TestCase):
    def test_forbidden_tool_present_is_unnecessary(self) -> None:
        result = TrajectoryEvaluator.evaluate(
            {"tool_calls": [{"name": "delete"}, {"name": "safe"}]},
            {"forbidden_tools": ["delete"]},
        )
        finding = _by_type(result, constants.TRAJECTORY_UNNECESSARY_TOOL)
        self.assertEqual(finding["tools"], ["delete"])

    def test_tool_outside_declared_toolset_is_unnecessary(self) -> None:
        result = TrajectoryEvaluator.evaluate(
            {"tool_calls": [{"name": "a"}, {"name": "b"}]},
            {"required_tools": ["a"]},
        )
        self.assertEqual(
            _by_type(result, constants.TRAJECTORY_UNNECESSARY_TOOL)["tools"], ["b"]
        )

    def test_no_declared_toolset_means_extras_are_not_flagged(self) -> None:
        # Only tool_parameters given -> no positive toolset declaration.
        result = TrajectoryEvaluator.evaluate(
            {"tool_calls": [{"name": "a", "arguments": {"x": 1}}, {"name": "b"}]},
            {"tool_parameters": {"a": {"required": ["x"]}}},
        )
        self.assertEqual(result["findings"], [])

    def test_parameter_constrained_tool_counts_as_expected(self) -> None:
        # A tool with a param spec is part of the expected toolset even when it
        # is not listed in required_tools, so it is not flagged as unnecessary.
        result = TrajectoryEvaluator.evaluate(
            {"tool_calls": [{"name": "a"}, {"name": "b", "arguments": {"x": 1}}]},
            {"required_tools": ["a"], "tool_parameters": {"b": {"required": ["x"]}}},
        )
        self.assertEqual(result["findings"], [])

    def test_unnecessary_tools_are_deduped_in_order(self) -> None:
        result = TrajectoryEvaluator.evaluate(
            {"tool_calls": [{"name": "z"}, {"name": "y"}, {"name": "z"}]},
            {"required_tools": ["a"]},
        )
        # 'a' is missing; 'z' and 'y' are unnecessary, first-occurrence order.
        self.assertEqual(
            _by_type(result, constants.TRAJECTORY_UNNECESSARY_TOOL)["tools"], ["z", "y"]
        )


class OutOfOrderTest(unittest.TestCase):
    def test_reversed_sequence_is_out_of_order(self) -> None:
        result = TrajectoryEvaluator.evaluate(
            {"tool_calls": [{"name": "c"}, {"name": "a"}, {"name": "b"}]},
            {"tool_sequence": ["a", "b", "c"]},
        )
        finding = _by_type(result, constants.TRAJECTORY_OUT_OF_ORDER)
        self.assertEqual(finding["tools"], ["a", "b", "c"])
        self.assertIn("a -> b -> c", finding["detail"])
        self.assertIn("c -> a -> b", finding["detail"])

    def test_correct_order_produces_no_finding(self) -> None:
        result = TrajectoryEvaluator.evaluate(
            {"tool_calls": [{"name": "a"}, {"name": "x"}, {"name": "b"}]},
            {"tool_sequence": ["a", "b"]},
        )
        self.assertNotIn(constants.TRAJECTORY_OUT_OF_ORDER, _types(result))

    def test_missing_sequenced_tool_is_not_treated_as_disorder(self) -> None:
        # 'b' is absent; the present tools a, c keep expected order -> only missing.
        result = TrajectoryEvaluator.evaluate(
            {"tool_calls": [{"name": "a"}, {"name": "c"}]},
            {"tool_sequence": ["a", "b", "c"]},
        )
        self.assertEqual(_types(result), [constants.TRAJECTORY_MISSING_TOOL])

    def test_no_sequence_means_no_order_check(self) -> None:
        result = TrajectoryEvaluator.evaluate(
            {"tool_calls": [{"name": "b"}, {"name": "a"}]},
            {"required_tools": ["a", "b"]},
        )
        self.assertNotIn(constants.TRAJECTORY_OUT_OF_ORDER, _types(result))

    def test_repeated_tools_do_not_trigger_disorder(self) -> None:
        result = TrajectoryEvaluator.evaluate(
            {"tool_calls": [{"name": "a"}, {"name": "b"}, {"name": "a"}]},
            {"tool_sequence": ["a", "b"]},
        )
        self.assertNotIn(constants.TRAJECTORY_OUT_OF_ORDER, _types(result))


class BadParametersTest(unittest.TestCase):
    def test_missing_required_argument_is_flagged(self) -> None:
        result = TrajectoryEvaluator.evaluate(
            {"tool_calls": [{"name": "search", "arguments": {"query": "x"}}]},
            {"tool_parameters": {"search": {"required": ["query", "limit"]}}},
        )
        finding = _by_type(result, constants.TRAJECTORY_BAD_PARAMETERS)
        self.assertEqual(finding["tools"], ["search"])
        self.assertIn("limit", finding["detail"])
        self.assertNotIn("query", finding["detail"])

    def test_absent_arguments_mapping_means_all_required_missing(self) -> None:
        result = TrajectoryEvaluator.evaluate(
            {"tool_calls": [{"name": "search"}]},
            {"tool_parameters": {"search": {"required": ["query"]}}},
        )
        self.assertEqual(
            _by_type(result, constants.TRAJECTORY_BAD_PARAMETERS)["tools"], ["search"]
        )

    def test_all_required_present_is_not_flagged(self) -> None:
        result = TrajectoryEvaluator.evaluate(
            {"tool_calls": [{"name": "search", "arguments": {"query": "x", "limit": 5}}]},
            {"tool_parameters": {"search": {"required": ["query", "limit"]}}},
        )
        self.assertEqual(result["findings"], [])

    def test_constrained_tool_never_called_is_not_flagged(self) -> None:
        result = TrajectoryEvaluator.evaluate(
            {"tool_calls": [{"name": "other"}]},
            {"tool_parameters": {"search": {"required": ["query"]}}},
        )
        self.assertNotIn(constants.TRAJECTORY_BAD_PARAMETERS, _types(result))

    def test_empty_required_list_never_flags(self) -> None:
        result = TrajectoryEvaluator.evaluate(
            {"tool_calls": [{"name": "search"}]},
            {"tool_parameters": {"search": {"required": []}}},
        )
        self.assertEqual(result["findings"], [])


class RecoveryTest(unittest.TestCase):
    def test_error_then_later_success_is_recovered(self) -> None:
        result = TrajectoryEvaluator.evaluate(
            {"tool_calls": [{"name": "api", "error": "timeout"}, {"name": "api"}]},
            {},
        )
        self.assertTrue(result["recovered_after_error"])
        self.assertEqual(result["findings"], [])

    def test_error_without_success_yields_no_recovery(self) -> None:
        result = TrajectoryEvaluator.evaluate(
            {"tool_calls": [{"name": "api", "error": "boom"}]},
            {},
        )
        self.assertFalse(result["recovered_after_error"])
        finding = _by_type(result, constants.TRAJECTORY_NO_RECOVERY)
        self.assertEqual(finding["tools"], ["api"])

    def test_no_errors_means_recovered_is_none(self) -> None:
        result = TrajectoryEvaluator.evaluate(
            {"tool_calls": [{"name": "api"}]},
            {},
        )
        self.assertIsNone(result["recovered_after_error"])

    def test_success_of_different_tool_does_not_recover(self) -> None:
        result = TrajectoryEvaluator.evaluate(
            {"tool_calls": [{"name": "api", "error": "x"}, {"name": "other"}]},
            {},
        )
        self.assertFalse(result["recovered_after_error"])
        self.assertEqual(
            _by_type(result, constants.TRAJECTORY_NO_RECOVERY)["tools"], ["api"]
        )

    def test_partial_recovery_reports_only_unrecovered_tools(self) -> None:
        result = TrajectoryEvaluator.evaluate(
            {
                "tool_calls": [
                    {"name": "a", "error": 1},
                    {"name": "a"},  # a recovers
                    {"name": "b", "error": 1},  # b never recovers
                ]
            },
            {},
        )
        self.assertFalse(result["recovered_after_error"])
        self.assertEqual(
            _by_type(result, constants.TRAJECTORY_NO_RECOVERY)["tools"], ["b"]
        )

    def test_error_recovered_then_errored_again_at_end_is_not_recovered(self) -> None:
        result = TrajectoryEvaluator.evaluate(
            {
                "tool_calls": [
                    {"name": "a", "error": 1},
                    {"name": "a"},
                    {"name": "a", "error": 1},  # trailing error, no later success
                ]
            },
            {},
        )
        self.assertFalse(result["recovered_after_error"])
        self.assertEqual(
            _by_type(result, constants.TRAJECTORY_NO_RECOVERY)["tools"], ["a"]
        )

    def test_falsy_error_value_is_not_an_error(self) -> None:
        result = TrajectoryEvaluator.evaluate(
            {"tool_calls": [{"name": "a", "error": False}, {"name": "b", "error": None}]},
            {},
        )
        self.assertIsNone(result["recovered_after_error"])
        self.assertEqual(result["findings"], [])

    def test_failure_detected_via_alternate_failure_key(self) -> None:
        # Error detection reuses constants.TOOL_FAILURE_KEYS ("error"/"failed"/...).
        result = TrajectoryEvaluator.evaluate(
            {"tool_calls": [{"name": "a", "failed": True}]},
            {},
        )
        self.assertFalse(result["recovered_after_error"])
        self.assertIn(constants.TRAJECTORY_NO_RECOVERY, _types(result))


class FindingOrderAndCombinationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.expected = {
            "tool_sequence": ["a", "b"],
            "required_tools": ["a", "b", "never_called"],
            "forbidden_tools": ["danger"],
            "tool_parameters": {"a": {"required": ["x"]}},
        }
        self.actual = {
            "tool_calls": [
                {"name": "b"},  # b before a -> out of order
                {"name": "a"},  # missing required arg x -> bad parameters
                {"name": "danger"},  # forbidden -> unnecessary
                {"name": "flaky", "error": "boom"},  # unnecessary + no recovery
            ]
        }
        self.result = TrajectoryEvaluator.evaluate(self.actual, self.expected)

    def test_findings_appear_in_canonical_order(self) -> None:
        self.assertEqual(
            _types(self.result),
            [
                constants.TRAJECTORY_MISSING_TOOL,
                constants.TRAJECTORY_UNNECESSARY_TOOL,
                constants.TRAJECTORY_OUT_OF_ORDER,
                constants.TRAJECTORY_BAD_PARAMETERS,
                constants.TRAJECTORY_NO_RECOVERY,
            ],
        )

    def test_each_finding_carries_the_right_tools(self) -> None:
        self.assertEqual(
            _by_type(self.result, constants.TRAJECTORY_MISSING_TOOL)["tools"],
            ["never_called"],
        )
        self.assertEqual(
            _by_type(self.result, constants.TRAJECTORY_UNNECESSARY_TOOL)["tools"],
            ["danger", "flaky"],
        )
        self.assertEqual(
            _by_type(self.result, constants.TRAJECTORY_OUT_OF_ORDER)["tools"],
            ["a", "b"],
        )
        self.assertEqual(
            _by_type(self.result, constants.TRAJECTORY_BAD_PARAMETERS)["tools"], ["a"]
        )
        self.assertEqual(
            _by_type(self.result, constants.TRAJECTORY_NO_RECOVERY)["tools"], ["flaky"]
        )

    def test_recovered_after_error_is_false(self) -> None:
        self.assertFalse(self.result["recovered_after_error"])


class EdgeCaseAndValidationTest(unittest.TestCase):
    def test_non_mapping_actual_raises_type_error(self) -> None:
        with self.assertRaises(TypeError):
            TrajectoryEvaluator.evaluate(["not", "a", "mapping"], {})

    def test_non_mapping_expected_raises_type_error(self) -> None:
        with self.assertRaises(TypeError):
            TrajectoryEvaluator.evaluate({}, ["not", "a", "mapping"])

    def test_empty_inputs_produce_clean_result(self) -> None:
        result = TrajectoryEvaluator.evaluate({}, {})
        self.assertEqual(
            result,
            {
                "findings": [],
                "recovered_after_error": None,
                "final_answer_consistency": {"needs_judgment": True},
            },
        )

    def test_none_and_missing_keys_are_tolerated(self) -> None:
        actual = {"tool_calls": None, "final_answer": None}
        expected = {
            "tool_sequence": None,
            "required_tools": None,
            "forbidden_tools": None,
            "tool_parameters": None,
        }
        result = TrajectoryEvaluator.evaluate(actual, expected)
        self.assertEqual(result["findings"], [])
        self.assertIsNone(result["recovered_after_error"])

    def test_tool_calls_not_a_list_is_treated_as_empty(self) -> None:
        result = TrajectoryEvaluator.evaluate(
            {"tool_calls": "search()"}, {"required_tools": ["search"]}
        )
        # A string is not a call list; 'search' is therefore missing.
        self.assertEqual(
            _by_type(result, constants.TRAJECTORY_MISSING_TOOL)["tools"], ["search"]
        )

    def test_non_mapping_call_entries_are_skipped(self) -> None:
        result = TrajectoryEvaluator.evaluate(
            {"tool_calls": ["bad", 42, {"name": "a"}]},
            {"required_tools": ["a"]},
        )
        self.assertEqual(result["findings"], [])

    def test_non_string_tool_name_is_ignored(self) -> None:
        result = TrajectoryEvaluator.evaluate(
            {"tool_calls": [{"name": 123}, {"name": "a"}]},
            {"required_tools": ["a"]},
        )
        self.assertEqual(result["findings"], [])

    def test_malformed_parameter_spec_is_tolerated(self) -> None:
        result = TrajectoryEvaluator.evaluate(
            {"tool_calls": [{"name": "a"}]},
            {"tool_parameters": {"a": "not-a-mapping", 5: {"required": ["x"]}}},
        )
        # 'a' has no usable required list; the non-string key is ignored.
        self.assertEqual(result["findings"], [])

    def test_inputs_are_not_mutated(self) -> None:
        actual = {
            "tool_calls": [
                {"name": "a", "error": "x"},
                {"name": "b", "arguments": {"q": 1}},
            ]
        }
        expected = {
            "tool_sequence": ["b", "a"],
            "required_tools": ["c"],
            "forbidden_tools": ["b"],
            "tool_parameters": {"b": {"required": ["q", "r"]}},
        }
        before_actual = copy.deepcopy(actual)
        before_expected = copy.deepcopy(expected)
        TrajectoryEvaluator.evaluate(actual, expected)
        self.assertEqual(actual, before_actual)
        self.assertEqual(expected, before_expected)


class ToolCallTest(unittest.TestCase):
    def test_tool_call_is_frozen(self) -> None:
        call = ToolCall(name="a", argument_names=frozenset({"x"}), errored=False)
        with self.assertRaises(Exception):
            call.name = "b"  # type: ignore[misc]


class FindingTest(unittest.TestCase):
    def test_to_dict_shape(self) -> None:
        finding = Finding(type="t", detail="d", tools=("x", "y"))
        self.assertEqual(
            finding.to_dict(), {"type": "t", "detail": "d", "tools": ["x", "y"]}
        )

    def test_tools_default_to_empty(self) -> None:
        finding = Finding(type="t", detail="d")
        self.assertEqual(finding.to_dict()["tools"], [])

    def test_finding_is_frozen(self) -> None:
        finding = Finding(type="t", detail="d")
        with self.assertRaises(Exception):
            finding.type = "u"  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
