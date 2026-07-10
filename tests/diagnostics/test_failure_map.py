from __future__ import annotations

import copy
import unittest

import evalsurfer.constants as constants
from evalsurfer.analysis.diagnostics.failure_map import FailureMap, StageDiagnosis


def _crit(cid: str, score: object) -> dict:
    return {"id": cid, "name": cid, "score": score}


def _report(criteria_by_pillar: dict | None = None, **extra: object) -> dict:
    report: dict = {}
    if criteria_by_pillar is not None:
        report["pillars"] = {
            pillar: {"criteria": crits} for pillar, crits in criteria_by_pillar.items()
        }
    report.update(extra)
    return report


def _render(report: object, threshold: int | None = None) -> dict:
    failure_map = FailureMap() if threshold is None else FailureMap(threshold=threshold)
    return failure_map.render(report)


def _stages(result: dict) -> dict:
    return {entry["stage"]: entry for entry in result["stages"]}


def _mermaid_class_line(result: dict) -> str | None:
    for line in result["mermaid"].splitlines():
        if line.strip().startswith("class "):  # not "classDef"
            return line.strip()
    return None


class FailureMapShapeTest(unittest.TestCase):
    def test_default_pipeline_is_expected(self) -> None:
        self.assertEqual(
            constants.PIPELINE_STAGES,
            ("Prompt", "Retriever", "Ranker", "Generator", "Tool", "Response"),
        )

    def test_result_shape(self) -> None:
        result = _render({})
        self.assertEqual(set(result), {"stages", "mermaid", "text"})
        self.assertEqual(
            [s["stage"] for s in result["stages"]], list(constants.PIPELINE_STAGES)
        )
        for entry in result["stages"]:
            self.assertEqual(set(entry), {"stage", "status", "weak_criteria"})
            self.assertIn(
                entry["status"],
                {
                    constants.STAGE_STATUS_OK,
                    constants.STAGE_STATUS_FAIL,
                    constants.STAGE_STATUS_NA,
                },
            )
            self.assertIsInstance(entry["weak_criteria"], list)

    def test_stage_criteria_mapping(self) -> None:
        stage_criteria = FailureMap.STAGE_CRITERIA
        # RAG criteria drive both retriever and ranker.
        self.assertEqual(stage_criteria["Retriever"], stage_criteria["Ranker"])
        self.assertIn("context_relevance", stage_criteria["Retriever"])
        self.assertIn("citation_accuracy", stage_criteria["Ranker"])
        # Generator covers core generation, multi-turn, and the whole safety pillar.
        self.assertIn("correctness_accuracy", stage_criteria["Generator"])
        self.assertIn("context_retention", stage_criteria["Generator"])
        self.assertIn("toxicity", stage_criteria["Generator"])
        self.assertIn("pii_leakage", stage_criteria["Generator"])
        # Tool covers agent tool-use.
        self.assertIn("tool_selection", stage_criteria["Tool"])
        self.assertIn("error_recovery", stage_criteria["Tool"])
        # Prompt and Response carry no criteria.
        self.assertEqual(stage_criteria["Prompt"], ())
        self.assertEqual(stage_criteria["Response"], ())
        # Operational criteria are not mapped to any stage.
        for ids in stage_criteria.values():
            self.assertNotIn("end_to_end_latency", ids)


class FailureMapEmptyTest(unittest.TestCase):
    def test_empty_report_is_all_na(self) -> None:
        result = _render({})
        for entry in result["stages"]:
            self.assertEqual(entry["status"], constants.STAGE_STATUS_NA)
            self.assertEqual(entry["weak_criteria"], [])
        self.assertEqual(
            result["text"],
            "Prompt -> Retriever -> Ranker -> Generator -> Tool -> Response",
        )
        # No stage is styled as failing.
        self.assertIsNone(_mermaid_class_line(result))
        self.assertIn("flowchart LR", result["mermaid"])
        self.assertIn("classDef fail", result["mermaid"])

    def test_missing_pillars_key_is_all_na(self) -> None:
        result = _render({"metadata": {"model": "x"}})
        self.assertTrue(
            all(s["status"] == constants.STAGE_STATUS_NA for s in result["stages"])
        )

    def test_non_mapping_pillars_tolerated(self) -> None:
        result = _render({"pillars": ["not", "a", "mapping"]})
        self.assertTrue(
            all(s["status"] == constants.STAGE_STATUS_NA for s in result["stages"])
        )


class FailureMapDiagnosisTest(unittest.TestCase):
    def test_rag_failure_hits_retriever_and_ranker(self) -> None:
        report = _report({"quality": [_crit("context_relevance", 2)]})
        stages = _stages(_render(report))
        self.assertEqual(stages["Retriever"]["status"], constants.STAGE_STATUS_FAIL)
        self.assertEqual(stages["Ranker"]["status"], constants.STAGE_STATUS_FAIL)
        self.assertEqual(stages["Retriever"]["weak_criteria"], ["context_relevance"])
        self.assertEqual(stages["Ranker"]["weak_criteria"], ["context_relevance"])
        # Stages without assessed criteria stay na.
        self.assertEqual(stages["Generator"]["status"], constants.STAGE_STATUS_NA)
        self.assertEqual(stages["Tool"]["status"], constants.STAGE_STATUS_NA)
        self.assertEqual(stages["Prompt"]["status"], constants.STAGE_STATUS_NA)

    def test_rag_all_pass_is_ok(self) -> None:
        report = _report(
            {"quality": [_crit("context_relevance", 4), _crit("retrieval_recall", 5)]}
        )
        stages = _stages(_render(report))
        self.assertEqual(stages["Retriever"]["status"], constants.STAGE_STATUS_OK)
        self.assertEqual(stages["Retriever"]["weak_criteria"], [])

    def test_safety_failure_hits_generator(self) -> None:
        report = _report({"safety": [_crit("toxicity", 1)]})
        stages = _stages(_render(report))
        self.assertEqual(stages["Generator"]["status"], constants.STAGE_STATUS_FAIL)
        self.assertEqual(stages["Generator"]["weak_criteria"], ["toxicity"])
        self.assertEqual(stages["Retriever"]["status"], constants.STAGE_STATUS_NA)

    def test_core_generation_failure_hits_generator(self) -> None:
        report = _report({"quality": [_crit("correctness_accuracy", 2)]})
        stages = _stages(_render(report))
        self.assertEqual(stages["Generator"]["status"], constants.STAGE_STATUS_FAIL)
        self.assertEqual(stages["Generator"]["weak_criteria"], ["correctness_accuracy"])

    def test_multi_turn_failure_hits_generator(self) -> None:
        report = _report({"quality": [_crit("context_retention", 2)]})
        stages = _stages(_render(report))
        self.assertEqual(stages["Generator"]["status"], constants.STAGE_STATUS_FAIL)
        self.assertEqual(stages["Generator"]["weak_criteria"], ["context_retention"])

    def test_tool_use_failure_hits_tool(self) -> None:
        report = _report({"quality": [_crit("tool_selection", 1)]})
        stages = _stages(_render(report))
        self.assertEqual(stages["Tool"]["status"], constants.STAGE_STATUS_FAIL)
        self.assertEqual(stages["Tool"]["weak_criteria"], ["tool_selection"])

    def test_weak_criteria_in_canonical_order(self) -> None:
        # relevance appears after correctness_accuracy in the catalog; the weak
        # list must follow that order regardless of report order.
        report = _report(
            {"quality": [_crit("relevance", 2), _crit("correctness_accuracy", 1)]}
        )
        stages = _stages(_render(report))
        self.assertEqual(
            stages["Generator"]["weak_criteria"],
            ["correctness_accuracy", "relevance"],
        )

    def test_generator_ok_when_assessed_and_none_weak(self) -> None:
        report = _report(
            {
                "quality": [_crit("correctness_accuracy", 4)],
                "safety": [_crit("toxicity", 5)],
            }
        )
        stages = _stages(_render(report))
        self.assertEqual(stages["Generator"]["status"], constants.STAGE_STATUS_OK)
        self.assertEqual(stages["Generator"]["weak_criteria"], [])


class FailureMapScoreHandlingTest(unittest.TestCase):
    def test_none_score_is_not_assessed(self) -> None:
        report = _report({"quality": [_crit("context_relevance", None)]})
        stages = _stages(_render(report))
        self.assertEqual(stages["Retriever"]["status"], constants.STAGE_STATUS_NA)

    def test_bool_score_is_not_a_number(self) -> None:
        report = _report({"quality": [_crit("context_relevance", True)]})
        stages = _stages(_render(report))
        self.assertEqual(stages["Retriever"]["status"], constants.STAGE_STATUS_NA)

    def test_non_numeric_score_ignored(self) -> None:
        report = _report({"quality": [_crit("context_relevance", "low")]})
        stages = _stages(_render(report))
        self.assertEqual(stages["Retriever"]["status"], constants.STAGE_STATUS_NA)

    def test_unknown_criterion_is_not_mapped(self) -> None:
        report = _report({"quality": [_crit("totally_made_up", 1)]})
        result = _render(report)
        self.assertTrue(
            all(s["status"] == constants.STAGE_STATUS_NA for s in result["stages"])
        )

    def test_missing_id_is_skipped(self) -> None:
        report = {"pillars": {"quality": {"criteria": [{"score": 1}]}}}
        result = _render(report)
        self.assertTrue(
            all(s["status"] == constants.STAGE_STATUS_NA for s in result["stages"])
        )


class FailureMapThresholdTest(unittest.TestCase):
    def test_score_equal_to_threshold_is_ok(self) -> None:
        report = _report({"quality": [_crit("context_relevance", 3)]})
        stages = _stages(_render(report, threshold=3))
        self.assertEqual(stages["Retriever"]["status"], constants.STAGE_STATUS_OK)

    def test_default_threshold_is_from_constants(self) -> None:
        # The constructor default matches the framework's configured threshold.
        report = _report({"quality": [_crit("context_relevance", 3)]})
        default_stages = _stages(_render(report))
        explicit_stages = _stages(
            _render(report, threshold=constants.FAILURE_MAP_THRESHOLD)
        )
        self.assertEqual(
            default_stages["Retriever"]["status"],
            explicit_stages["Retriever"]["status"],
        )

    def test_custom_threshold_flags_more(self) -> None:
        report = _report({"quality": [_crit("context_relevance", 3)]})
        stages = _stages(_render(report, threshold=4))
        self.assertEqual(stages["Retriever"]["status"], constants.STAGE_STATUS_FAIL)

    def test_invalid_threshold_type(self) -> None:
        with self.assertRaises(TypeError):
            FailureMap(threshold=True)
        with self.assertRaises(TypeError):
            FailureMap(threshold=3.0)  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            FailureMap(threshold="3")  # type: ignore[arg-type]

    def test_out_of_range_threshold(self) -> None:
        with self.assertRaises(ValueError):
            FailureMap(threshold=constants.CRITERION_MIN_SCORE - 1)
        with self.assertRaises(ValueError):
            FailureMap(threshold=constants.CRITERION_MAX_SCORE + 1)


class FailureMapResponseTest(unittest.TestCase):
    def test_response_ok_on_pass(self) -> None:
        stages = _stages(_render(_report(decision=constants.DECISION_PASS)))
        self.assertEqual(stages["Response"]["status"], constants.STAGE_STATUS_OK)

    def test_response_fail_on_non_pass(self) -> None:
        stages = _stages(_render(_report(decision=constants.DECISION_FAIL)))
        self.assertEqual(stages["Response"]["status"], constants.STAGE_STATUS_FAIL)
        stages = _stages(
            _render(_report(decision=constants.DECISION_PASS_WITH_FIXES))
        )
        self.assertEqual(stages["Response"]["status"], constants.STAGE_STATUS_FAIL)

    def test_response_na_without_decision(self) -> None:
        stages = _stages(_render(_report()))
        self.assertEqual(stages["Response"]["status"], constants.STAGE_STATUS_NA)

    def test_response_prefers_overall_decision(self) -> None:
        report = {
            "overall": {"decision": constants.DECISION_PASS},
            "decision": constants.DECISION_FAIL,
        }
        stages = _stages(_render(report))
        self.assertEqual(stages["Response"]["status"], constants.STAGE_STATUS_OK)

    def test_response_falls_back_to_top_level_decision(self) -> None:
        report = {
            "overall": {"summary": "no decision here"},
            "decision": constants.DECISION_FAIL,
        }
        stages = _stages(_render(report))
        self.assertEqual(stages["Response"]["status"], constants.STAGE_STATUS_FAIL)


class FailureMapRenderingTest(unittest.TestCase):
    def test_text_marks_failing_stages(self) -> None:
        report = _report(
            {"quality": [_crit("context_relevance", 1)]},
            decision=constants.DECISION_FAIL,
        )
        result = _render(report)
        self.assertEqual(
            result["text"],
            "Prompt -> Retriever[FAIL] -> Ranker[FAIL] -> Generator -> Tool -> Response[FAIL]",
        )

    def test_mermaid_styles_failing_stages(self) -> None:
        report = _report({"safety": [_crit("toxicity", 1)]})
        result = _render(report)
        self.assertIn("flowchart LR", result["mermaid"])
        self.assertIn(
            "Prompt --> Retriever --> Ranker --> Generator --> Tool --> Response",
            result["mermaid"],
        )
        self.assertIn("classDef fail", result["mermaid"])
        self.assertEqual(_mermaid_class_line(result), "class Generator fail")

    def test_mermaid_lists_multiple_failing_stages_in_order(self) -> None:
        report = _report(
            {"quality": [_crit("context_relevance", 1)]},
            decision=constants.DECISION_FAIL,
        )
        result = _render(report)
        self.assertEqual(
            _mermaid_class_line(result), "class Retriever,Ranker,Response fail"
        )


class FailureMapImmutabilityTest(unittest.TestCase):
    def test_report_is_not_mutated(self) -> None:
        report = _report(
            {
                "quality": [_crit("context_relevance", 2)],
                "safety": [_crit("toxicity", 5)],
            },
            decision=constants.DECISION_FAIL,
        )
        snapshot = copy.deepcopy(report)
        _render(report)
        self.assertEqual(report, snapshot)

    def test_stage_diagnosis_is_frozen(self) -> None:
        diagnosis = StageDiagnosis(
            stage=constants.STAGE_PROMPT,
            status=constants.STAGE_STATUS_NA,
            weak_criteria=(),
        )
        with self.assertRaises(Exception):
            diagnosis.status = constants.STAGE_STATUS_OK  # type: ignore[misc]
        self.assertEqual(
            diagnosis.to_dict(),
            {"stage": "Prompt", "status": "na", "weak_criteria": []},
        )


class FailureMapValidationTest(unittest.TestCase):
    def test_report_must_be_mapping(self) -> None:
        with self.assertRaises(TypeError):
            FailureMap().render(None)  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            FailureMap().render(["not", "a", "mapping"])  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
